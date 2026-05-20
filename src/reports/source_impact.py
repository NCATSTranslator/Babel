"""Renderers for the source-impact report.

``render_markdown`` produces the human-readable report committed to
``docs/sources/<SOURCE>/impact-report.md``. ``render_json`` produces the same data as a
structured payload for downstream consumers.

Both inputs are the output of:
- ``src.model.source.discover_source(name, intermediate_root)`` (the source's filesystem
  contribution), and
- ``src.model.clique_diff.diff_cliques(before, after, source_curies, ...)`` (one diff per
  semantic type the source touches).
"""

from __future__ import annotations

import json
from collections import defaultdict

from src.model.clique_diff import SourceImpactDiff
from src.model.source import SourceContribution

SAMPLE_LIMIT = 10


def _fmt(n: int) -> str:
    return f"{n:,}"


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
) -> str:
    name = contribution.name
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

    lines.append("## 4. Clique impact")
    lines.append("")
    if not diffs_by_semantic_type:
        lines.append(
            "(No clique diffs available — synthetic mode did not run for any semantic "
            "type. See report header for the mode used.)"
        )
        lines.append("")
    else:
        for st in sorted(diffs_by_semantic_type):
            diff = diffs_by_semantic_type[st]
            lines.append(f"### {st}")
            lines.append("")
            lines.append(
                f"- {_fmt(len(diff.pure_new_cliques))} new cliques composed only of "
                f"{name} identifiers"
            )
            lines.append(
                f"- {_fmt(len(diff.expanded_cliques))} existing cliques will gain "
                f"{name} identifiers"
            )
            lines.append(
                f"- {_fmt(len(diff.merged_cliques))} existing cliques will be merged "
                f"because of new {name} cross-references"
            )
            lines.append("")

            if diff.merged_cliques:
                lines.append(f"#### Sample merges (up to {SAMPLE_LIMIT})")
                for mc in diff.merged_cliques[:SAMPLE_LIMIT]:
                    bridge_curie = sorted(mc.source_curies_involved)[0]
                    leaders = ", ".join(_clique_leader(bc) for bc in mc.before_cliques)
                    lines.append(f"- {bridge_curie} bridges {leaders}")
                lines.append("")

            if diff.pure_new_cliques:
                lines.append(f"#### Sample pure-new cliques (up to {SAMPLE_LIMIT})")
                for clique in diff.pure_new_cliques[:SAMPLE_LIMIT]:
                    lines.append(f"- {', '.join(sorted(clique))}")
                lines.append("")

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
            "pure_new_clique_count": len(diff.pure_new_cliques),
            "expanded_clique_count": len(diff.expanded_cliques),
            "merged_clique_count": len(diff.merged_cliques),
            "merged_samples": [
                {
                    "before_clique_leaders": [_clique_leader(bc) for bc in mc.before_cliques],
                    "source_curies_involved": sorted(mc.source_curies_involved),
                }
                for mc in diff.merged_cliques[:SAMPLE_LIMIT]
            ],
            "pure_new_samples": [sorted(c) for c in diff.pure_new_cliques[:SAMPLE_LIMIT]],
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
        "by_semantic_type": by_semantic_type,
        "final_compendium_breakdown": final_compendium_breakdown,
        "clique_diffs": diffs_serialised,
        "remote_summary": remote_summary or {},
    }
    return json.dumps(payload, indent=2, sort_keys=True)
