# CLAUDE.md — src/tools/overused_xrefs/

`babel-overused-xrefs` audits one concord file for xref targets claimed by many subjects — the
merge hazard `remove_overused_xrefs` drops and `OVERUSE_FILTERED_CONCORDS` opts a source into.
User-facing docs: [`docs/tools/OverusedXrefs.md`](../../../docs/tools/OverusedXrefs.md).

- **The logic is not here.** Detection is `find_overused_xref_targets()` in
  [`src/model/concords.py`](../../model/concords.py); labels come from
  `load_labels_for_prefixes()` in `src/reports/source_impact.py` and, for prefixes Babel never
  ingests, `load_mrconso_labels()` back in `src/model/concords.py`. `cli.py` is argparse plus a
  CSV writer. Keep it that way — the source-impact report and the pipeline both have reason to
  ask the same question.

- **The MRCONSO fallback is a heuristic, deliberately.** A CURIE matches an MRCONSO row when the
  row's `CODE` equals the local id and the row's `SAB` *starts with* the CURIE prefix's first
  underscore-delimited token — so `ICD10:` matches `SAB=ICD10CM` and DOID's version-stamped
  `SNOMEDCT_US_2025_09_01:` matches `SAB=SNOMEDCT_US`, with no curated SAB table to maintain. It
  can attach a label from a sibling vocabulary that shares a code space. That is an accepted
  trade for an audit artifact; do not reuse it anywhere a label is authoritative.

- **Two filters on MRCONSO are load-bearing**, both learned the hard way while generating
  `docs/sources/DOID/overused-xrefs/overused-targets.csv`:
  - `LAT == language` (default `ENG`) — MRCONSO is multilingual and a Dutch string wins the TTY
    race for many ICD-10 codes. The first CSV generated was in Dutch.
  - `SUPPRESS == "N"` — DOID xrefs retired SNOMED concepts whose only strings are `SUPPRESS=O`
    obsolete forms. An empty cell beats an obsolete string presented as the current label.

- **Output is long format** (one row per target/subject pair), so it sorts and filters in a
  spreadsheet without unpacking a delimited cell. If you change the columns, regenerate the
  committed DOID CSV in the same commit.
