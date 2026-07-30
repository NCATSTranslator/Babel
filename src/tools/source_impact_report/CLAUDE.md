# CLAUDE.md — src/tools/source_impact_report/

`source-impact-report` answers "what does adding this source do to the cliques?" Full reference:
[`docs/tools/SourceImpactReport.md`](../../../docs/tools/SourceImpactReport.md), including the
`PIPELINE_CONFIG` registry (what each entry needs and what breaks if you omit a key) and what the
report cannot see (split/shrunk/dropped cliques — use `babel-clique-diff` for those).

## Reading the detail files it writes

Parse `new-cliques-top-100.csv` / `modified-cliques.csv` with `csv.DictReader` (or `pandas`), never
`awk -F,` or `cut -d,`. Ontology labels contain commas and are therefore quoted — e.g.
`"nephric duct, mesonephric portion"` — so a comma split silently shifts every column after
`preferred_label`, and the result still looks like a valid table. The failure mode is a
confidently-wrong number: a non-zero `needs_biolink_registration` count that is really fragments of
a label. Read the columns by name; do not index by position. (`equivalent_ids` is a *pipe*-joined
CURIE list — `PIPE` in `src/reports/source_impact_details.py` — so split it on `|`, not `,`.)

`new-xrefs.tsv` is tab-separated and safe for `awk -F'\t'`, but its CURIE columns are
`subject`/`object`, which are not the first two fields.

## The new-cliques file is a capped sample — never commit the full list

`new-cliques-top-100.csv` is the one detail file the writer truncates. Sources produce thousands of
pure-new cliques (3,753 for EMAPA, 14,750 for MP), almost all clean single-identifier cliques, and
the full list goes stale on the next build; committing it added megabytes that no SME read. The
committed file is a permanent record of the ingest's output shape, not an inventory.

`NEW_CLIQUES_TOP_N` in
[`src/reports/source_impact_details.py`](../../reports/source_impact_details.py) sets the cap and
the filename derives from it, so both move together — and `write_new_cliques_csv`
**ranks before truncating**: rows whose preferred identifier the Biolink prefix filter would drop
come first, then the largest cliques, then CURIE order for a stable diff. If you change either the
cap or the ranking, keep that property. A blind `rows[:N]` on CURIE order would keep an arbitrary
`EMAPA:16*` prefix and could hide the survival failures the report exists to surface, which is what
`test_new_cliques_csv_cap_keeps_unsurvivable_and_largest_rows` guards.

## Registry and diffing internals

`PIPELINE_CONFIG` in `cli.py` is the registry mapping each pipeline to its hooks; the diffing
logic itself lives in [`src/model/glom_diff.py`](../../model/glom_diff.py) (not
`compendium_diff.py`, which backs `babel-clique-diff`) and
[`src/model/source.py`](../../model/source.py). To register a new pipeline, extract a
`compute_cliques_for_impact_report` helper from that pipeline's `build_compendia()` — see
`src/createcompendia/anatomy.py` for the template — and route the real build through the same
wrapper so the report's reglom provably matches the build. `docs/AddingNewSources.md` step 8 has
the full walkthrough.
