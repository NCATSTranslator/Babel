# CLAUDE.md — src/tools/source_impact_report/

`source-impact-report` answers "what does adding this source do to the cliques?" Full reference:
[`docs/tools/SourceImpactReport.md`](../../../docs/tools/SourceImpactReport.md), including the
`PIPELINE_CONFIG` registry (what each entry needs and what breaks if you omit a key) and what the
report cannot see (split/shrunk/dropped cliques — use `babel-clique-diff` for those).

`PIPELINE_CONFIG` in `cli.py` is the registry mapping each pipeline to its hooks; the diffing
logic itself lives in [`src/model/glom_diff.py`](../../model/glom_diff.py) (not
`compendium_diff.py`, which backs `babel-clique-diff`) and
[`src/model/source.py`](../../model/source.py). To register a new pipeline, extract a
`compute_cliques_for_impact_report` helper from that pipeline's `build_compendia()` — see
`src/createcompendia/anatomy.py` for the template — and route the real build through the same
wrapper so the report's reglom provably matches the build. `docs/AddingNewSources.md` step 8 has
the full walkthrough.
