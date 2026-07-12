"""Full, uncapped detail-file writers for the source-impact report.

While ``src.reports.source_impact`` renders the human-readable markdown (and a summary
JSON capped at a few samples), this module writes the *complete* detail files an SME
reviews in a PR — one subdirectory (``<output-stem>/``) beside the markdown report:

- ``new-cliques.csv`` — every pure-new clique the source introduces (the common case is a
  brand-new single-identifier clique; multi-member pure-new cliques carry ``member_count``).
- ``modified-cliques.json`` / ``modified-cliques.csv`` — every existing clique the source
  expands or merges. The JSON keeps the full before/after structure; the CSV has one row
  per source identifier landing in the clique, flagged ``added`` (structurally new) or
  ``preexisting`` (already pulled in via another source's xref, now a typed identifier).
- ``new-xrefs.tsv`` — every cross-reference row touching a source CURIE, with the predicate
  (which for SSSOM-style sources distinguishes exact/close match) and the concord file that
  asserted it.

All files are deterministically sorted so re-running the tool yields byte-identical output
(clean git diffs). The tool cannot see downstream Biolink-class prefix filtering directly,
so the clique/xref *counts* are an *upper bound* of what could land in the build — but the
``new-cliques.csv`` / ``modified-cliques.csv`` rows carry per-identifier survival columns
(``would_be_added`` / ``needs_biolink_registration``) that predict that filtering by
checking each identifier's prefix against the Biolink Model ``id_prefixes`` for the
*clique's* assigned biolink type (the single ``node_type`` ``NodeFactory.create_node()``
filters every member against), so a reviewer can see which "added" identifiers would
actually be emitted and which require a Biolink Model registration first.
"""

from __future__ import annotations

import csv
import json
import pathlib
from collections.abc import Iterable
from dataclasses import dataclass

from src.model.glom_diff import SourceImpactDiff
from src.model.source import SourceContribution, scan_concords_for_curies
from src.reports.source_impact import (
    LookupContext,
    biolink_registration_note,
    clique_leader,
    curie_label,
    preferred_curie,
    prefix_of,
    prefix_survives,
    sort_clique_for_display,
)

# Detail-file names, written inside the report's per-source subdirectory.
NEW_CLIQUES_CSV = "new-cliques.csv"
MODIFIED_CLIQUES_JSON = "modified-cliques.json"
MODIFIED_CLIQUES_CSV = "modified-cliques.csv"
NEW_XREFS_TSV = "new-xrefs.tsv"

PIPE = "|"


@dataclass(frozen=True)
class _ModifiedClique:
    """Normalised view of one expanded-or-merged clique for the detail writers."""

    pipeline: str
    change_kind: str  # "expanded" | "merged"
    biolink_type: str | None
    after_clique: frozenset[str]
    before_cliques: tuple[frozenset[str], ...]
    added: frozenset[str]
    preexisting: frozenset[str]
    after_preferred: str
    before_preferred: str | None


def _biolink_type_for(clique, st, lookup: LookupContext) -> str | None:
    classifier = lookup.clique_classifier.get(st)
    types = lookup.types_by_pipeline.get(st, {})
    return classifier(clique, types) if classifier else None


def _modified_cliques(
    diffs: dict[str, SourceImpactDiff],
    lookup: LookupContext,
) -> list[_ModifiedClique]:
    """Flatten every expanded and merged clique across pipelines, sorted for output."""
    out: list[_ModifiedClique] = []
    for st in sorted(diffs):
        diff = diffs[st]
        for ec in diff.expanded_cliques:
            biolink_type = _biolink_type_for(ec.after_clique, st, lookup)
            out.append(
                _ModifiedClique(
                    pipeline=st,
                    change_kind="expanded",
                    biolink_type=biolink_type,
                    after_clique=ec.after_clique,
                    before_cliques=(ec.before_clique,),
                    added=ec.added_source_curies,
                    preexisting=ec.preexisting_source_curies,
                    after_preferred=preferred_curie(ec.after_clique, biolink_type, lookup.prefix_priority_by_type),
                    before_preferred=preferred_curie(ec.before_clique, biolink_type, lookup.prefix_priority_by_type),
                )
            )
        for mc in diff.merged_cliques:
            biolink_type = _biolink_type_for(mc.after_clique, st, lookup)
            before_union: frozenset[str] = frozenset().union(*mc.before_cliques)
            out.append(
                _ModifiedClique(
                    pipeline=st,
                    change_kind="merged",
                    biolink_type=biolink_type,
                    after_clique=mc.after_clique,
                    before_cliques=mc.before_cliques,
                    added=mc.source_curies_involved - before_union,
                    preexisting=mc.source_curies_involved & before_union,
                    after_preferred=preferred_curie(mc.after_clique, biolink_type, lookup.prefix_priority_by_type),
                    before_preferred=None,
                )
            )
    out.sort(key=lambda m: (m.pipeline, clique_leader(m.after_clique)))
    return out


def _fmt_bool(value: bool | None) -> str:
    """Render a tri-state survival flag for a CSV cell ("" when unknown)."""
    if value is None:
        return ""
    return "true" if value else "false"


def _write_rows(path: pathlib.Path, header: list[str], rows: Iterable[list], *, delimiter: str = ",") -> None:
    # lineterminator="\n" overrides csv's default "\r\n" so committed files use LF and stay
    # byte-identical across re-runs regardless of the platform's git autocrlf setting.
    with path.open("w", newline="") as f:
        writer = csv.writer(f, delimiter=delimiter, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_new_cliques_csv(
    path: pathlib.Path,
    diffs: dict[str, SourceImpactDiff],
    lookup: LookupContext,
) -> int:
    """Write one row per pure-new clique. Returns the number of cliques written.

    Survival columns predict downstream Biolink prefix filtering. ``preferred_id_would_survive``
    judges the preferred (highest-priority) identifier; ``needs_biolink_registration`` is set
    when that prefix is positively absent from the clique type's ``id_prefixes``. Because
    ``create_node`` keeps a clique as long as *any* member's prefix survives,
    ``unsupported_prefixes`` lists the member prefixes that would be dropped even if the clique
    itself survives — for a single-identifier pure-new clique (the common case) an unsupported
    prefix means the whole clique is dropped.
    """
    header = [
        "pipeline",
        "preferred_id",
        "preferred_label",
        "biolink_type",
        "member_count",
        "equivalent_ids",
        "preferred_id_would_survive",
        "needs_biolink_registration",
        "unsupported_prefixes",
    ]
    rows: list[list] = []
    for st in sorted(diffs):
        for clique in diffs[st].pure_new_cliques:
            biolink_type = _biolink_type_for(clique, st, lookup)
            ordered = sort_clique_for_display(clique, biolink_type, lookup.prefix_priority_by_type)
            preferred = ordered[0]
            would_survive, needs_reg = prefix_survives(preferred, biolink_type, lookup.prefix_priority_by_type)
            unsupported = sorted(
                {prefix_of(c) for c in clique if prefix_survives(c, biolink_type, lookup.prefix_priority_by_type)[1]}
            )
            rows.append(
                [
                    st,
                    preferred,
                    curie_label(preferred, lookup.labels_by_prefix) or "",
                    biolink_type or "",
                    len(clique),
                    PIPE.join(ordered),
                    _fmt_bool(would_survive),
                    _fmt_bool(needs_reg) if would_survive is not None else "",
                    PIPE.join(unsupported),
                ]
            )
    rows.sort(key=lambda r: (r[0], r[1]))
    _write_rows(path, header, rows)
    return len(rows)


def write_modified_cliques_csv(
    path: pathlib.Path,
    diffs: dict[str, SourceImpactDiff],
    lookup: LookupContext,
) -> int:
    """Write one row per source identifier landing in a modified clique.

    Returns the number of (identifier) rows written. ``added_kind`` is ``added`` for a
    structurally-new identifier and ``preexisting`` for one that was already pulled into the
    clique via another source's cross-reference and is now a typed identifier.
    """
    header = [
        "pipeline",
        "clique_preferred_id",
        "clique_preferred_label",
        "clique_biolink_type",
        "change_kind",
        "added_kind",
        "added_id",
        "added_id_label",
        "added_id_biolink_type",
        "would_be_added",
        "needs_biolink_registration",
        "biolink_registration_note",
        "equivalent_ids",
    ]
    rows: list[list] = []
    for m in _modified_cliques(diffs, lookup):
        types = lookup.types_by_pipeline.get(m.pipeline, {})
        ordered = sort_clique_for_display(m.after_clique, m.biolink_type, lookup.prefix_priority_by_type)
        equivalent_ids = PIPE.join(ordered)
        preferred_label = curie_label(m.after_preferred, lookup.labels_by_prefix) or ""
        for added_kind, curie_set in (("added", m.added), ("preexisting", m.preexisting)):
            for curie in curie_set:
                # Judge survival on the *clique's* assigned biolink type, since that is the
                # single node_type NodeFactory.create_node() filters every member's prefix
                # against (not each identifier's own declared type). When the clique type is
                # unknown (no classifier), prefix_survives returns (None, False) -> blank.
                # added_id_biolink_type still records the identifier's own declared type for
                # context.
                own_type = types.get(curie)
                would_be_added, needs_reg = prefix_survives(curie, m.biolink_type, lookup.prefix_priority_by_type)
                note = biolink_registration_note(curie, m.biolink_type) if needs_reg else ""
                rows.append(
                    [
                        m.pipeline,
                        m.after_preferred,
                        preferred_label,
                        m.biolink_type or "",
                        m.change_kind,
                        added_kind,
                        curie,
                        curie_label(curie, lookup.labels_by_prefix) or "",
                        own_type or "",
                        _fmt_bool(would_be_added),
                        _fmt_bool(needs_reg) if would_be_added is not None else "",
                        note,
                        equivalent_ids,
                    ]
                )
    rows.sort(key=lambda r: (r[0], r[1], r[6]))
    _write_rows(path, header, rows)
    return len(rows)


def write_modified_cliques_json(
    path: pathlib.Path,
    diffs: dict[str, SourceImpactDiff],
    lookup: LookupContext,
) -> int:
    """Write the full before/after structure of every modified clique. Returns the count."""

    def members(clique: frozenset[str]) -> list[dict]:
        return [{"i": curie, "label": curie_label(curie, lookup.labels_by_prefix)} for curie in sorted(clique)]

    entries: list[dict] = []
    for m in _modified_cliques(diffs, lookup):
        types = lookup.types_by_pipeline.get(m.pipeline, {})
        # Per-added-identifier survival, judged on the *clique's* assigned biolink type —
        # the single node_type create_node() filters every member's prefix against. The
        # ``declared_biolink_type`` field records the identifier's own declared type for
        # context. The flat added/preexisting lists are kept for back-compat; this enriches them.
        added_curie_details = []
        for kind, curie_set in (("added", m.added), ("preexisting", m.preexisting)):
            for curie in sorted(curie_set):
                own_type = types.get(curie)
                would_be_added, needs_reg = prefix_survives(curie, m.biolink_type, lookup.prefix_priority_by_type)
                added_curie_details.append(
                    {
                        "i": curie,
                        "added_kind": kind,
                        "declared_biolink_type": own_type,
                        "clique_biolink_type": m.biolink_type,
                        "would_be_added": would_be_added,
                        "needs_biolink_registration": needs_reg if would_be_added is not None else None,
                        "note": biolink_registration_note(curie, m.biolink_type) if needs_reg else None,
                    }
                )
        added_curie_details.sort(key=lambda d: d["i"])
        entries.append(
            {
                "pipeline": m.pipeline,
                "change_kind": m.change_kind,
                "biolink_type": m.biolink_type,
                "preferred_id_before": m.before_preferred,
                "preferred_id_after": m.after_preferred,
                "before_clique_leaders": sorted(clique_leader(bc) for bc in m.before_cliques),
                "before_cliques": [sorted(bc) for bc in m.before_cliques],
                "added_source_curies": sorted(m.added),
                "preexisting_source_curies": sorted(m.preexisting),
                "added_curie_details": added_curie_details,
                "after_members": members(m.after_clique),
            }
        )
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n")
    return len(entries)


def write_new_xrefs_tsv(
    path: pathlib.Path,
    contribution: SourceContribution,
    intermediate_root: pathlib.Path,
    lookup: LookupContext,
) -> int:
    """Write one row per concord row touching a source CURIE, across all concord files.

    ``status`` reflects *which* concord file asserts the row, not before/after novelty
    (this writer does not diff the pre-source glom state, so it cannot tell whether the
    row newly becomes a clique edge): ``added`` means the new source's own concord file
    asserts it (a brand-new bridge), and ``from_other_source`` means another source's
    concord file asserts a row that happens to touch a source CURIE — such a row may have
    already existed before this source was added. Returns the number of rows written.
    """
    header = [
        "pipeline",
        "subject",
        "subject_label",
        "predicate",
        "object",
        "object_label",
        "asserted_by",
        "status",
    ]
    rows: list[list] = []
    source_name = contribution.name
    for st in sorted(contribution.pipelines):
        stc = contribution.by_pipeline[st]
        concords_dir = pathlib.Path(intermediate_root) / st / "concords"
        for subject, predicate, obj, asserted_by in scan_concords_for_curies(concords_dir, stc.all_curies):
            status = "added" if asserted_by == source_name else "from_other_source"
            rows.append(
                [
                    st,
                    subject,
                    curie_label(subject, lookup.labels_by_prefix) or "",
                    predicate,
                    obj,
                    curie_label(obj, lookup.labels_by_prefix) or "",
                    asserted_by,
                    status,
                ]
            )
    rows.sort(key=lambda r: (r[0], r[1], r[4], r[6]))
    _write_rows(path, header, rows, delimiter="\t")
    return len(rows)


def write_detail_files(
    details_dir: pathlib.Path,
    contribution: SourceContribution,
    diffs: dict[str, SourceImpactDiff],
    intermediate_root: pathlib.Path,
    lookup: LookupContext,
) -> dict[str, int]:
    """Write all four detail files into ``details_dir``; return a {filename: row_count} map."""
    details_dir.mkdir(parents=True, exist_ok=True)
    return {
        NEW_CLIQUES_CSV: write_new_cliques_csv(details_dir / NEW_CLIQUES_CSV, diffs, lookup),
        MODIFIED_CLIQUES_CSV: write_modified_cliques_csv(details_dir / MODIFIED_CLIQUES_CSV, diffs, lookup),
        MODIFIED_CLIQUES_JSON: write_modified_cliques_json(details_dir / MODIFIED_CLIQUES_JSON, diffs, lookup),
        NEW_XREFS_TSV: write_new_xrefs_tsv(details_dir / NEW_XREFS_TSV, contribution, intermediate_root, lookup),
    }
