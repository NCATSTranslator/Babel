# CLAUDE.md — src/tools/source_impact_report/

`source-impact-report` answers "what does adding this source do to the cliques?" Full reference:
[`docs/tools/SourceImpactReport.md`](../../../docs/tools/SourceImpactReport.md), including the
`PIPELINE_CONFIG` registry (what each entry needs and what breaks if you omit a key) and what the
report cannot see (split/shrunk/dropped cliques — use `babel-clique-diff` for those).

## Reading the detail files it writes

Parse `new-cliques.csv` / `modified-cliques.csv` with `csv.DictReader` (or `pandas`), never
`awk -F,` or `cut -d,`. `equivalent_ids` is a comma-joined CURIE list inside a single quoted
field, so a comma split silently shifts every column after it — and the result still looks like
a valid table. The failure mode is a confidently-wrong number: a non-zero
`needs_biolink_registration` count that is really fragments of a CURIE list. Read the columns by
name; do not index by position.

`new-xrefs.tsv` is tab-separated and safe for `awk -F'\t'`, but its CURIE columns are
`subject`/`object`, which are not the first two fields.

## Registry and diffing internals

`PIPELINE_CONFIG` in `cli.py` is the registry mapping each pipeline to its hooks; the diffing
logic itself lives in [`src/model/glom_diff.py`](../../model/glom_diff.py) (not
`compendium_diff.py`, which backs `babel-clique-diff`) and
[`src/model/source.py`](../../model/source.py). To register a new pipeline, extract a
`compute_cliques_for_impact_report` helper from that pipeline's `build_compendia()` — see
`src/createcompendia/anatomy.py` for the template — and route the real build through the same
wrapper so the report's reglom provably matches the build. `docs/AddingNewSources.md` step 8 has
the full walkthrough.
