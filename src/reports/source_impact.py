"""Renderers for the source-impact report.

``render_markdown`` produces the human-readable report committed to
``docs/sources/<SOURCE>/impact-report.md``. ``render_json`` produces the same data as a
structured payload for downstream consumers.

Both inputs are the output of:
- ``src.model.source.discover_source(name, intermediate_root)`` (the source's filesystem
  contribution), and
- ``src.model.clique_diff.diff_cliques(before, after, source_curies, ...)`` (one diff per
  semantic type the source touches).

The ``LookupContext`` aggregates the per-semantic-type helpers the renderer needs to turn
bare CURIEs into linked, labelled lines: a Biolink CURIE→IRI converter for the OBO PURL,
a per-prefix CURIE→label map sourced from ``babel_downloads/<PREFIX>/labels``, and a
``clique_classifier`` that picks each clique's biolink type so the renderer can apply the
right prefix-priority list when marking the preferred identifier.
"""

from __future__ import annotations

import json
import logging
import pathlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from src.model.clique_diff import ExpandedClique, SourceImpactDiff
from src.model.source import SourceContribution

logger = logging.getLogger(__name__)

SAMPLE_LIMIT = 3
PURE_NEW_SAMPLE_LIMIT = 3
EXPANDED_SAMPLE_LIMIT = 3


@dataclass
class LookupContext:
    """Bundle of per-semantic-type helpers the renderer uses to enrich CURIE listings.

    Anything that needs filesystem or network access (label files, Biolink prefix map)
    or per-semantic-type knowledge (which biolink type a clique should be classified as,
    which prefix-priority list to apply) is plumbed in here instead of being looked up
    inside the renderer. This keeps the renderer pure and testable.
    """

    # CURIE -> declared biolink type, per semantic type, as captured at ids-file load time.
    types_by_semantic_type: dict[str, dict[str, str]] = field(default_factory=dict)
    # Per-prefix CURIE -> label map (e.g. ``{"EMAPA": {"EMAPA:1": "...", ...}}``).
    labels_by_prefix: dict[str, dict[str, str]] = field(default_factory=dict)
    # Optional CURIE -> IRI expander (e.g. a ``curies.Converter`` with ``.expand``).
    curie_expander: Callable[[str], str | None] | None = None
    # Pick a biolink type for one clique given the types map for its semantic type.
    clique_classifier: dict[str, Callable[[frozenset[str], dict[str, str]], str | None]] = field(
        default_factory=dict,
    )
    # Biolink-type -> list of prefixes in priority order, used to pick the preferred CURIE.
    prefix_priority_by_type: dict[str, list[str]] = field(default_factory=dict)


def _fmt(n: int) -> str:
    return f"{n:,}"


def _percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "n/a"
    return f"{(100.0 * numerator / denominator):.2f}%"


def _normalize_markdown(lines: list[str]) -> list[str]:
    """Insert a blank line before each list block and strip trailing blank lines.

    The section renderers append headings directly before their lists; without this the
    output trips the repository markdown linter (MD032 lists-need-blank-lines, MD012
    trailing-blank-lines). Centralising it here keeps the per-section code uncluttered.
    """
    out: list[str] = []
    for line in lines:
        is_list_item = line.lstrip().startswith("- ")
        prev = out[-1] if out else ""
        if is_list_item and prev.strip() and not prev.lstrip().startswith("- "):
            out.append("")
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


def _clique_leader(clique: frozenset[str]) -> str:
    return sorted(clique)[0]


def _prefix_of(curie: str) -> str:
    return curie.split(":", 1)[0]


def _curie_url(curie: str, expander: Callable[[str], str | None] | None) -> str | None:
    if expander is None:
        return None
    try:
        return expander(curie)
    except Exception as exc:
        logger.debug("could not expand %s: %s", curie, exc)
        return None


def _curie_label(curie: str, labels_by_prefix: dict[str, dict[str, str]]) -> str | None:
    prefix = _prefix_of(curie)
    return labels_by_prefix.get(prefix, {}).get(curie)


def _render_curie_entry(
    curie: str,
    ctx: LookupContext,
    *,
    bullet: str = "- ",
    marker: str = "",
) -> str:
    """Render one CURIE as a bullet line with OBO PURL + preferred label, if available.

    Mirrors the documentation convention from CLAUDE.md:
    ``[`PREFIX:NNN`](http://purl.obolibrary.org/obo/PREFIX_NNN) "preferred label"``.
    Falls back gracefully when the expander or label is missing so the renderer doesn't
    break for prefixes that aren't in the Biolink prefix map or for terms that have no
    downloaded label.
    """
    url = _curie_url(curie, ctx.curie_expander)
    label = _curie_label(curie, ctx.labels_by_prefix)
    if url:
        head = f"[`{curie}`]({url})"
    else:
        head = f"`{curie}`"
    parts = [head]
    if label:
        parts.append(f'"{label}"')
    if marker:
        parts.append(marker)
    return f"{bullet}{' '.join(parts)}"


def _sort_clique_for_display(
    curies: Iterable[str],
    biolink_type: str | None,
    prefix_priority_by_type: dict[str, list[str]],
) -> list[str]:
    """Order CURIEs the way ``NodeFactory.create_node()`` lists them on a clique.

    Within a clique the compendium writer iterates the biolink prefix-priority list for
    the type and, for each prefix, sorts the matching CURIEs lexicographically. We mirror
    that here so the first CURIE in the returned list is the preferred one and CURIEs
    sharing a prefix stay adjacent in their compendium order. CURIEs whose prefix is not
    in the priority list (which ``create_node`` would silently drop) are appended at the
    end, sorted lexicographically, so the report still shows them.
    """
    priority = prefix_priority_by_type.get(biolink_type, []) if biolink_type else []
    priority_index = {p.upper(): i for i, p in enumerate(priority)}
    tail = len(priority_index)

    def sort_key(curie: str) -> tuple[int, str]:
        return (priority_index.get(_prefix_of(curie).upper(), tail), curie)

    return sorted(curies, key=sort_key)


def _preferred_curie(
    clique: frozenset[str],
    biolink_type: str | None,
    prefix_priority_by_type: dict[str, list[str]],
) -> str:
    """Pick the highest-priority CURIE in a clique using the biolink prefix-priority list
    for its type. Falls back to alphabetical sort when no prefix in the priority list is
    present (mirrors NodeFactory's behaviour of warning + skipping prefixes not in the
    list, but here we still have to choose *something* for the sample, so we settle on
    the lexicographically smallest CURIE)."""
    return _sort_clique_for_display(clique, biolink_type, prefix_priority_by_type)[0]


def prefix_survives(
    curie: str,
    biolink_type: str | None,
    prefix_priority_by_type: dict[str, list[str]],
) -> tuple[bool | None, bool]:
    """Predict whether ``curie`` would survive ``write_compendium``'s prefix filtering.

    ``NodeFactory.create_node`` keeps only CURIEs whose prefix is in the Biolink Model's
    ``id_prefixes`` for the clique's biolink type and silently drops the rest; a clique
    with no surviving prefix is skipped entirely. We mirror that here using
    ``prefix_priority_by_type`` (populated from the same ``id_prefixes`` lists the build
    filters against), judging each identifier on **its own** biolink type.

    Returns ``(would_be_added, needs_biolink_registration)``:

    - ``would_be_added`` is ``True``/``False`` when the type's prefix list is known, or
      ``None`` when it is unknown (no declared type, or ``--no-biolink-lookup`` left
      ``prefix_priority_by_type`` empty) — callers should render ``None`` as blank/unknown
      rather than as a negative.
    - ``needs_biolink_registration`` is ``True`` only when we positively know the prefix
      is absent from the type's ``id_prefixes`` (i.e. someone must add it to the Biolink
      Model before Babel can emit this identifier). It is ``False`` whenever survival is
      unknown, to avoid false alarms.
    """
    if not biolink_type:
        return None, False
    priority = prefix_priority_by_type.get(biolink_type)
    if priority is None:
        return None, False
    allowed = {p.upper() for p in priority}
    survives = _prefix_of(curie).upper() in allowed
    return survives, not survives


def biolink_registration_note(curie: str, biolink_type: str | None) -> str:
    """Short reminder for an identifier whose prefix is not registered for its type."""
    if not biolink_type:
        return ""
    return (
        f"prefix {_prefix_of(curie)} not in id_prefixes for {biolink_type} — "
        "register in the Biolink Model before Babel can emit this identifier"
    )


def _distinct_label_count(curies: Iterable[str], labels_by_prefix: dict[str, dict[str, str]]) -> int:
    """Count the distinct (case-folded) preferred labels among a clique's members.

    A clique whose members carry many *different* labels is the most worth a human's
    eyes — it's the likeliest place a bad cross-reference has fused unrelated concepts —
    so the renderer ranks samples by this descending. Members with no downloaded label
    contribute nothing.
    """
    labels: set[str] = set()
    for curie in curies:
        label = _curie_label(curie, labels_by_prefix)
        if label:
            labels.add(label.casefold())
    return len(labels)


def _pure_new_rank(clique: frozenset[str], labels_by_prefix: dict[str, dict[str, str]]) -> tuple:
    """Deterministic review-worthiness sort key for a pure-new clique (most first)."""
    return (-_distinct_label_count(clique, labels_by_prefix), -len(clique), _clique_leader(clique))


def _expanded_rank(ec: ExpandedClique, labels_by_prefix: dict[str, dict[str, str]]) -> tuple:
    """Deterministic review-worthiness sort key for an expanded clique (most first)."""
    return (
        -_distinct_label_count(ec.after_clique, labels_by_prefix),
        -len(ec.after_clique),
        _clique_leader(ec.after_clique),
    )


def _render_remote_section(remote_summary: dict[str, dict[str, int]]) -> str:
    lines: list[str] = ["", "## 5. Remote comparison summary", ""]
    for st in sorted(remote_summary):
        s = remote_summary[st]
        lines.append(f"### {st}")
        lines.append("")
        lines.append(f"- Remote total cliques (compendia): {s.get('remote_total_cliques', 0):,}")
        lines.append(
            "- Remote cliques containing source CURIEs: "
            f"{s.get('remote_cliques_with_source_curies', 0):,}"
        )
        lines.append(
            "- Current cliques containing source CURIEs: "
            f"{s.get('current_cliques_with_source_curies', 0):,}"
        )
        lines.append(
            "- Cliques with source CURIEs in current but not in remote: "
            f"{s.get('current_only_with_source_curies', 0):,}"
        )
        lines.append("")
    return "\n".join(lines)


def _detail_link(details_dirname: str | None, filename: str, text: str) -> str | None:
    """Render a bullet linking to one of the full detail files, or None if not emitted."""
    if not details_dirname:
        return None
    return f"- {text}: [`{details_dirname}/{filename}`]({details_dirname}/{filename})"


def _render_clique_impact(
    name: str,
    diffs_by_semantic_type: dict[str, SourceImpactDiff],
    lookup: LookupContext,
    details_dirname: str | None = None,
) -> list[str]:
    lines: list[str] = ["## 4. Clique impact", ""]
    lines.append(
        "**Worst-case view.** This report is computed from the intermediate identifier "
        "and concord files and cannot see downstream filtering that happens later in the "
        "build — most notably the Biolink Model's per-class prefix restrictions, which "
        "drop identifiers whose prefix is not permitted for a clique's biolink type. The "
        "counts and detail files below are therefore an *upper bound*: they show every "
        "change the source could introduce before that filtering is applied."
    )
    lines.append("")
    if not diffs_by_semantic_type:
        lines.append(
            "(No clique diffs available — synthetic mode did not run for any semantic "
            "type. See report header for the mode used.)"
        )
        return lines

    for st in sorted(diffs_by_semantic_type):
        diff = diffs_by_semantic_type[st]
        types = lookup.types_by_semantic_type.get(st, {})
        classifier = lookup.clique_classifier.get(st)

        before_total = diff.before_clique_count
        pure_new_n = len(diff.pure_new_cliques)
        expanded_n = len(diff.expanded_cliques)
        merged_n = len(diff.merged_cliques)
        truly_grown_n = sum(1 for ec in diff.expanded_cliques if ec.added_source_curies)
        promotion_only_n = expanded_n - truly_grown_n
        # CURIEs added is distinct from cliques modified: one clique can gain several new
        # source identifiers, so the identifier count is usually larger than the clique
        # count. Count structurally-new source CURIEs entering *existing* cliques (via
        # expansion or merge); pure-new cliques are reported separately above.
        curies_added_expanded = sum(len(ec.added_source_curies) for ec in diff.expanded_cliques)
        curies_added_merged = sum(
            len(mc.source_curies_involved - frozenset().union(*mc.before_cliques))
            for mc in diff.merged_cliques
        )
        curies_added_total = curies_added_expanded + curies_added_merged

        lines.append(f"### {st}")
        lines.append("")
        lines.append(
            f"- {_fmt(pure_new_n)} new cliques composed only of {name} identifiers "
            f"(a {_percent(pure_new_n, before_total)} increase over the "
            f"{_fmt(before_total)} pre-existing cliques)"
        )
        lines.append(
            f"- {_fmt(expanded_n)} existing cliques contain {name} identifiers in the "
            f"after state ({_percent(expanded_n, before_total)} of the "
            f"{_fmt(before_total)} pre-existing cliques). Of these, "
            f"{_fmt(truly_grown_n)} cliques gain at least one structurally new "
            f"identifier from {name}, and {_fmt(promotion_only_n)} already contained the "
            f"{name} CURIE via an xref from another source — {name}'s ids file now also "
            "lists those existing CURIEs as first-class typed identifiers."
        )
        lines.append(
            f"- {_fmt(merged_n)} existing cliques will be merged because of new {name} "
            "cross-references"
        )
        lines.append(
            f"- {_fmt(curies_added_total)} structurally-new {name} identifiers are added "
            f"to existing cliques ({_fmt(curies_added_expanded)} via expansion, "
            f"{_fmt(curies_added_merged)} via merges). This is distinct from the "
            f"{_fmt(truly_grown_n + merged_n)} existing cliques that change, since one "
            "clique can gain several identifiers."
        )
        lines.append(
            f"- Total cliques in this semantic type go from {_fmt(before_total)} to "
            f"{_fmt(diff.after_clique_count)}"
        )
        lines.append("")

        link = _detail_link(details_dirname, "new-cliques.csv", "Full list of new cliques")
        if link:
            lines.append(link)
        link = _detail_link(
            details_dirname, "modified-cliques.csv",
            f"Full list of modified cliques (one row per added/promoted {name} identifier)",
        )
        if link:
            lines.append(link)
        link = _detail_link(
            details_dirname, "new-xrefs.tsv", "Full list of new / activated cross-references"
        )
        if link:
            lines.append(link)
        if details_dirname:
            lines.append("")

        if diff.merged_cliques:
            lines.append(f"#### Sample merges (up to {SAMPLE_LIMIT})")
            merged_sorted = sorted(
                diff.merged_cliques,
                key=lambda mc: (
                    -len(mc.before_cliques),
                    -_distinct_label_count(mc.after_clique, lookup.labels_by_prefix),
                    _clique_leader(mc.after_clique),
                ),
            )
            for mc in merged_sorted[:SAMPLE_LIMIT]:
                bridge_curie = sorted(mc.source_curies_involved)[0]
                leaders = ", ".join(_clique_leader(bc) for bc in mc.before_cliques)
                lines.append(f"- {bridge_curie} bridges {leaders}")
            lines.append("")

        if diff.pure_new_cliques:
            lines.append(f"#### Sample pure-new cliques (up to {PURE_NEW_SAMPLE_LIMIT})")
            ordered = sorted(
                diff.pure_new_cliques,
                key=lambda c: _pure_new_rank(c, lookup.labels_by_prefix),
            )
            def _reg_marker(curie: str) -> str:
                # Flag a pure-new identifier whose prefix is not registered in the Biolink
                # Model for its declared type — it cannot be written out (see survival
                # columns in the detail files).
                own_type = types.get(curie)
                _, needs_reg = prefix_survives(curie, own_type, lookup.prefix_priority_by_type)
                return (
                    f"**(NOT emitted — prefix not registered in Biolink Model for `{own_type}`)**"
                    if needs_reg
                    else ""
                )

            for clique in ordered[:PURE_NEW_SAMPLE_LIMIT]:
                if len(clique) == 1:
                    only = next(iter(clique))
                    lines.append(_render_curie_entry(only, lookup, marker=_reg_marker(only)))
                else:
                    biolink_type = classifier(clique, types) if classifier else None
                    ordered_curies = _sort_clique_for_display(
                        clique, biolink_type, lookup.prefix_priority_by_type
                    )
                    for i, c in enumerate(ordered_curies):
                        markers = [m for m in ("**(preferred)**" if i == 0 else "", _reg_marker(c)) if m]
                        bullet = "- " if i == 0 else "  - "
                        lines.append(
                            _render_curie_entry(c, lookup, bullet=bullet, marker=" ".join(markers))
                        )
            lines.append("")

        if diff.expanded_cliques:
            # Bucket samples so the most informative ones surface first: cliques where
            # the preferred identifier changes, then cliques that gained a structurally
            # new member, then promotion-only cliques. Sort each bucket by review-worthiness
            # (most distinct member labels first) so the sample surfaces the cliques most
            # likely to reveal a bad cross-reference, deterministically across rebuilds.
            preferred_change_samples: list[tuple[ExpandedClique, str, str, str | None]] = []
            truly_grown_samples: list[tuple[ExpandedClique, str, str, str | None]] = []
            promotion_only_samples: list[tuple[ExpandedClique, str, str, str | None]] = []
            for ec in diff.expanded_cliques:
                biolink_type = classifier(ec.after_clique, types) if classifier else None
                before_pref = _preferred_curie(
                    ec.before_clique, biolink_type, lookup.prefix_priority_by_type
                )
                after_pref = _preferred_curie(
                    ec.after_clique, biolink_type, lookup.prefix_priority_by_type
                )
                tup = (ec, before_pref, after_pref, biolink_type)
                if before_pref != after_pref:
                    preferred_change_samples.append(tup)
                elif ec.added_source_curies:
                    truly_grown_samples.append(tup)
                else:
                    promotion_only_samples.append(tup)
            preferred_change_samples.sort(key=lambda t: _expanded_rank(t[0], lookup.labels_by_prefix))
            truly_grown_samples.sort(key=lambda t: _expanded_rank(t[0], lookup.labels_by_prefix))
            promotion_only_samples.sort(key=lambda t: _expanded_rank(t[0], lookup.labels_by_prefix))
            preferred_change_n = len(preferred_change_samples)

            lines.append(
                f"#### Sample expanded cliques (up to {EXPANDED_SAMPLE_LIMIT})"
            )
            lines.append("")
            lines.append(
                f"Of the {_fmt(expanded_n)} cliques that contain {name} identifiers "
                f"in the after state, {_fmt(preferred_change_n)} would also see their "
                f"preferred identifier change as a result of adding {name}. The sample "
                f"below leads with preferred-id-change cliques (if any), then "
                f"structurally grown cliques, then cliques where {name} only adds CURIEs "
                f"that were already present via xref. Within each clique, identifiers "
                f"are listed in the same order they would appear in the compendium "
                f"(biolink prefix priority, then lexicographic within prefix)."
            )
            chosen = (
                preferred_change_samples + truly_grown_samples + promotion_only_samples
            )[:EXPANDED_SAMPLE_LIMIT]
            for ec, before_pref, after_pref, biolink_type in chosen:
                markers_for_clique: list[str] = []
                if before_pref != after_pref:
                    markers_for_clique.append("preferred identifier changes")
                if ec.added_source_curies:
                    markers_for_clique.append(
                        f"gains {_fmt(len(ec.added_source_curies))} new "
                        f"member(s) from {name}"
                    )
                else:
                    markers_for_clique.append(f"{name} CURIE already present via xref")
                summary = "; ".join(markers_for_clique)
                type_marker = f" — typed as `{biolink_type}`" if biolink_type else ""
                lines.append(
                    f"- Clique with {_fmt(len(ec.after_clique))} identifiers"
                    f"{type_marker} — {summary}:"
                )
                ordered = _sort_clique_for_display(
                    ec.after_clique, biolink_type, lookup.prefix_priority_by_type
                )
                for c in ordered:
                    markers: list[str] = []
                    if c in ec.added_source_curies:
                        markers.append(f"**(new from {name})**")
                    elif c in ec.promoted_source_curies:
                        markers.append(f"**(existing identifier, also added by {name})**")
                    if c in ec.added_source_curies or c in ec.promoted_source_curies:
                        # Judge survival on the identifier's *own* declared type, since the
                        # clique's final preferred type may not be knowable here.
                        own_type = types.get(c)
                        _, needs_reg = prefix_survives(c, own_type, lookup.prefix_priority_by_type)
                        if needs_reg:
                            markers.append(
                                f"**(NOT emitted — prefix not registered in Biolink Model "
                                f"for `{own_type}`)**"
                            )
                    if c == after_pref:
                        markers.append("**(preferred)**")
                    if before_pref != after_pref and c == before_pref:
                        markers.append("_(was preferred before)_")
                    lines.append(
                        _render_curie_entry(c, lookup, bullet="  - ", marker=" ".join(markers))
                    )
            lines.append("")

    return lines


def render_markdown(
    contribution: SourceContribution,
    diffs_by_semantic_type: dict[str, SourceImpactDiff],
    final_compendium_breakdown: dict[str, dict[str, int]],
    *,
    mode: str,
    generated_at: str,
    babel_commit: str,
    remote_url: str | None = None,
    remote_summary: dict[str, dict[str, int]] | None = None,
    lookup: LookupContext | None = None,
    details_dirname: str | None = None,
) -> str:
    name = contribution.name
    lookup = lookup or LookupContext()
    lines: list[str] = []

    lines.append(f"# Source impact report: {name}")
    lines.append("")
    lines.append(f"- Generated: {generated_at}")
    lines.append(f"- Babel commit: {babel_commit}")
    lines.append(
        "- Source semantic types: "
        f"{', '.join(sorted(contribution.semantic_types)) or '(none discovered)'}"
    )
    lines.append(
        "- Source prefixes: "
        f"{', '.join(sorted(contribution.prefixes)) or '(none discovered)'}"
    )
    mode_label = mode if not remote_url else f"{mode} (vs {remote_url})"
    lines.append(f"- Comparison mode: {mode_label}")
    lines.append("")

    lines.append("## 1. Identifiers added")
    lines.append("")
    total = contribution.total_identifier_count
    lines.append(
        f"Totals: {_fmt(total)} identifiers across {len(contribution.prefixes)} "
        f"prefix(es) in {len(contribution.semantic_types)} semantic type(s)."
    )
    lines.append("")
    lines.append("### By prefix")
    by_prefix: dict[str, int] = defaultdict(int)
    for stc in contribution.by_semantic_type.values():
        for prefix, curies in stc.curies_by_prefix.items():
            by_prefix[prefix] += len(curies)
    if by_prefix:
        for prefix in sorted(by_prefix):
            lines.append(f"- {prefix}: {_fmt(by_prefix[prefix])}")
    else:
        lines.append("- (no identifiers discovered)")
    lines.append("")
    lines.append("### By semantic type")
    if contribution.semantic_types:
        for st in sorted(contribution.semantic_types):
            stc = contribution.by_semantic_type[st]
            lines.append(f"- {st}: {_fmt(len(stc.all_curies))}")
    else:
        lines.append("- (no semantic types discovered)")
    lines.append("")

    lines.append("## 2. Biolink types")
    lines.append("")
    lines.append("### Overall declared type breakdown")
    overall_counts = contribution.declared_type_counts
    if overall_counts:
        for declared_type in sorted(overall_counts):
            label = declared_type if declared_type else "(no declared type)"
            lines.append(f"- {label}: {_fmt(overall_counts[declared_type])}")
    else:
        lines.append("- (no identifiers discovered)")
    lines.append("")
    lines.append("### Source-declared (from each ids file)")
    if contribution.semantic_types:
        for st in sorted(contribution.semantic_types):
            stc = contribution.by_semantic_type[st]
            lines.append(f"- {st} / {name}")
            counts = stc.declared_type_counts
            if not counts:
                lines.append("  - (no ids file)")
                continue
            for declared_type in sorted(counts):
                label = declared_type if declared_type else "(no declared type)"
                lines.append(f"  - {label}: {_fmt(counts[declared_type])}")
    else:
        lines.append("- (no semantic types discovered)")
    lines.append("")

    lines.append("### Final compendium-assigned (after glom)")
    if final_compendium_breakdown:
        any_rows = False
        for st in sorted(final_compendium_breakdown):
            for compendium, count in sorted(final_compendium_breakdown[st].items()):
                if count == 0:
                    continue
                noun = "identifier" if count == 1 else "identifiers"
                lines.append(f"- {st} / {compendium}: {_fmt(count)} {name} {noun}")
                any_rows = True
        if not any_rows:
            lines.append("- (no source identifiers found in any compendium)")
    else:
        lines.append("- (no compendia inspected)")
    lines.append("")

    lines.append("## 3. Cross-references added")
    lines.append("")
    total_concords = contribution.total_concord_row_count
    n_concord_files = sum(
        1 for stc in contribution.by_semantic_type.values() if stc.concords_path is not None
    )
    lines.append(
        f"Totals: {_fmt(total_concords)} cross-reference rows across "
        f"{n_concord_files} concord file(s)."
    )
    lines.append("")
    lines.append("### By semantic type")
    if contribution.semantic_types:
        for st in sorted(contribution.semantic_types):
            stc = contribution.by_semantic_type[st]
            lines.append(f"- {st} / {name}: {_fmt(len(stc.concord_pairs))}")
    else:
        lines.append("- (no semantic types discovered)")
    lines.append("")
    lines.append("### Partner prefix breakdown (per semantic type)")
    if contribution.semantic_types:
        for st in sorted(contribution.semantic_types):
            stc = contribution.by_semantic_type[st]
            lines.append(f"- {st}")
            partner_counts = stc.concord_partner_prefix_counts
            if not partner_counts:
                lines.append("  - (no concord rows)")
                continue
            for prefix in sorted(partner_counts, key=lambda p: (-partner_counts[p], p)):
                lines.append(f"  - {prefix}: {_fmt(partner_counts[prefix])}")
    else:
        lines.append("- (no semantic types discovered)")
    lines.append("")

    lines.extend(_render_clique_impact(name, diffs_by_semantic_type, lookup, details_dirname))

    if remote_summary:
        lines.append(_render_remote_section(remote_summary))
    return "\n".join(_normalize_markdown(lines)) + "\n"


def render_json(
    contribution: SourceContribution,
    diffs_by_semantic_type: dict[str, SourceImpactDiff],
    final_compendium_breakdown: dict[str, dict[str, int]],
    *,
    mode: str,
    generated_at: str,
    babel_commit: str,
    remote_url: str | None = None,
    remote_summary: dict[str, dict[str, int]] | None = None,
) -> str:
    by_semantic_type: dict[str, dict] = {}
    for st, stc in contribution.by_semantic_type.items():
        by_semantic_type[st] = {
            "ids_path": str(stc.ids_path) if stc.ids_path else None,
            "concords_path": str(stc.concords_path) if stc.concords_path else None,
            "curies_by_prefix": {p: len(cs) for p, cs in stc.curies_by_prefix.items()},
            "declared_type_counts": stc.declared_type_counts,
            "concord_row_count": len(stc.concord_pairs),
            "concord_partner_prefix_counts": stc.concord_partner_prefix_counts,
        }

    diffs_serialised: dict[str, dict] = {}
    for st, diff in diffs_by_semantic_type.items():
        diffs_serialised[st] = {
            "source_curie_count": len(diff.source_curies),
            "before_clique_count": diff.before_clique_count,
            "after_clique_count": diff.after_clique_count,
            "pure_new_clique_count": len(diff.pure_new_cliques),
            "expanded_clique_count": len(diff.expanded_cliques),
            "merged_clique_count": len(diff.merged_cliques),
            "merged_samples": [
                {
                    "before_clique_leaders": [_clique_leader(bc) for bc in mc.before_cliques],
                    "source_curies_involved": sorted(mc.source_curies_involved),
                }
                for mc in sorted(
                    diff.merged_cliques,
                    key=lambda mc: (-len(mc.before_cliques), _clique_leader(mc.after_clique)),
                )[:SAMPLE_LIMIT]
            ],
            "pure_new_samples": [
                sorted(c)
                for c in sorted(
                    diff.pure_new_cliques, key=lambda c: (-len(c), _clique_leader(c))
                )[:PURE_NEW_SAMPLE_LIMIT]
            ],
            "truly_grown_clique_count": sum(
                1 for ec in diff.expanded_cliques if ec.added_source_curies
            ),
            "promotion_only_clique_count": sum(
                1 for ec in diff.expanded_cliques if not ec.added_source_curies
            ),
            "expanded_samples": [
                {
                    "before_clique": sorted(ec.before_clique),
                    "added_source_curies": sorted(ec.added_source_curies),
                    "promoted_source_curies": sorted(ec.promoted_source_curies),
                    "after_clique": sorted(ec.after_clique),
                }
                for ec in sorted(
                    diff.expanded_cliques,
                    key=lambda ec: (-len(ec.after_clique), _clique_leader(ec.after_clique)),
                )[:EXPANDED_SAMPLE_LIMIT]
            ],
        }

    payload = {
        "source": contribution.name,
        "generated_at": generated_at,
        "babel_commit": babel_commit,
        "mode": mode,
        "remote_url": remote_url,
        "semantic_types": sorted(contribution.semantic_types),
        "prefixes": sorted(contribution.prefixes),
        "total_identifier_count": contribution.total_identifier_count,
        "total_concord_row_count": contribution.total_concord_row_count,
        "declared_type_counts_overall": contribution.declared_type_counts,
        "by_semantic_type": by_semantic_type,
        "final_compendium_breakdown": final_compendium_breakdown,
        "clique_diffs": diffs_serialised,
        "remote_summary": remote_summary or {},
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def load_labels_for_prefixes(
    prefixes: Iterable[str],
    downloads_root: pathlib.Path | str,
) -> dict[str, dict[str, str]]:
    """Load per-prefix label maps from ``<downloads_root>/<PREFIX>/labels``.

    Each file is tab-separated ``CURIE\\tlabel``. Missing files are skipped quietly so
    the caller can pass the full set of prefixes a semantic type might use without
    having to pre-check which prefixes are available.
    """
    root = pathlib.Path(downloads_root)
    out: dict[str, dict[str, str]] = {}
    for prefix in prefixes:
        path = root / prefix / "labels"
        if not path.exists():
            continue
        labels: dict[str, str] = {}
        with path.open() as f:
            for line in f:
                parts = line.rstrip("\n").split("\t", 1)
                if len(parts) != 2:
                    continue
                labels[parts[0]] = parts[1]
        out[prefix] = labels
        logger.info("loaded %d labels for %s", len(labels), prefix)
    return out
