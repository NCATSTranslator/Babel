# CLAUDE.md — src/tools/source_impact_report/

`source-impact-report` answers "what does adding this source do to the cliques?" Full reference:
[`docs/tools/SourceImpactReport.md`](../../../docs/tools/SourceImpactReport.md), including the
`PIPELINE_CONFIG` registry (what each entry needs and what breaks if you omit a key) and what the
report cannot see (split/shrunk/dropped cliques — use `babel-clique-diff` for those).

## Reading the detail files it writes

Every detail file is CSV. Parse them with `csv.DictReader` (or `pandas`), never
`awk -F,` or `cut -d,`. Ontology labels contain commas and are therefore quoted — e.g.
`"nephric duct, mesonephric portion"` — so a comma split silently shifts every column after
`preferred_label`, and the result still looks like a valid table. The failure mode is a
confidently-wrong number: a non-zero `needs_biolink_registration` count that is really fragments of
a label. Read the columns by name; do not index by position. (`equivalent_ids` is a *pipe*-joined
CURIE list — `PIPE` in `src/reports/source_impact_details.py` — so split it on `|`, not `,`.)

In the xref files the CURIE columns are `subject`/`object`, which are not the first two fields.
(`new-xrefs.tsv` was tab-separated and shell-friendly until the switch to CSV for consistency; there
is no TSV detail file any more.)

## Two files are committed; the four they reduce are not

Both committed files are *reductions*, and each takes the shape its data calls for. Never commit the
full table: it goes stale on the next build and adds megabytes no SME reads. The unqualified
filename is always the full local table, the qualified one the committed reduction — see the
constants at the top of
[`src/reports/source_impact_details.py`](../../reports/source_impact_details.py).

### `new-cliques-top-100.csv` — a ranked slice

Sources produce thousands of pure-new cliques (3,753 for EMAPA, 14,750 for MP), almost all clean
single-identifier cliques. `NEW_CLIQUES_TOP_N` sets the cap and the filename derives from it, so
both move together — and `write_new_cliques_csv` **ranks before truncating**: rows whose preferred
identifier the Biolink prefix filter would drop come first, then the largest cliques, then CURIE
order for a stable diff. If you change either the cap or the ranking, keep that property. A blind
`rows[:N]` on CURIE order would keep an arbitrary `EMAPA:16*` prefix and could hide the survival
failures the report exists to surface, which is what
`test_new_cliques_csv_cap_keeps_unsurvivable_and_largest_rows` guards.

### `new-xrefs-summary.csv` — an aggregate, not a slice

A slice would be the wrong reduction here: what a reviewer needs from a source's xrefs is
*which join pathways it opens*, and there are far fewer pathways than rows — EMAPA's 4,336 xrefs are
a single pathway, MP's 87 are five. So `summarize_xref_groups` in
[`src/model/source.py`](../../model/source.py) groups rows by predicate, canonical prefix pair,
asserting concord file and status, and keeps `XREF_EXAMPLES_PER_GROUP` examples per group, spread
evenly across the group so they span the identifier range.

Two properties to preserve if you touch the grouping:

- **The prefix pair is sorted**, matching how `src/metadata/provenance.py` keys its metadata counts
  (`xref(CHEBI, DrugCentral)`), so one pathway does not appear twice because two concord files wrote
  it in opposite directions.
- **`asserted_by` and `status` stay in the group key.** They are what survives the sorting, and they
  carry the report's central distinction: MP asserting a mapping to HP is a bridge this addition
  introduces, while HP asserting one to MP may predate it. Same sorted pair, different facts.
  `test_summarize_xref_groups_keeps_the_two_assertion_directions_apart` guards this.

Known wart worth knowing before you read a summary: `asserted_by` is the concord file's path
relative to `concords/`, so a *nested* file such as `UNICHEM/UNICHEM_7` never compares equal to
source `UNICHEM` and its pathways are always labelled `from_other_source`. A pathway whose
`asserted_by` contains a slash is showing you this, not a real third-party assertion.

## Registry and diffing internals

`PIPELINE_CONFIG` in `cli.py` is the registry mapping each pipeline to its hooks; the diffing
logic itself lives in [`src/model/glom_diff.py`](../../model/glom_diff.py) (not
`compendium_diff.py`, which backs `babel-clique-diff`) and
[`src/model/source.py`](../../model/source.py). To register a new pipeline, extract a
`compute_cliques_for_impact_report` helper from that pipeline's `build_compendia()` — see
`src/createcompendia/anatomy.py` for the template — and route the real build through the same
wrapper so the report's reglom provably matches the build. `docs/AddingNewSources.md` step 8 has
the full walkthrough.
