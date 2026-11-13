# ChemicalParent conflation measurements

The ChemicalParent conflation (`src/createcompendia/chemicalparent.py`, described in
[`docs/Conflation.md`](../../Conflation.md#chemicalparent)) groups chemical cliques that are one
parent compound in different charge states, salts or hydrates.

## Charge states

- [`scripts/measure_protonation_groups.py`](scripts/measure_protonation_groups.py) replays the
  production grouping, without salts, over a published build's DuckDB `Edge.parquet` files. It
  reports group counts and sizes, the compendia each group spans, and overlap with DrugChemical.
- [`2025dec11.md`](2025dec11.md) is its output for the 2025dec11 build.

Re-run it against a new build before changing the grouping rule, and commit the new report beside
this one.

## Salts and hydrates

- [`scripts/review_salt_components.py`](scripts/review_salt_components.py) measures how completely
  [`input_data/chemical_parent_components.tsv`](../../../input_data/chemical_parent_components.tsv)
  resolves the multi-component records in curated cliques. It ranks the unreviewed components that
  still block records, and writes a review sheet in the list's own columns. Its docstring has the
  commands. The first run splits UniChem's and GtoPdb's InChIs with RDKit and caches the result;
  later runs take a minute or two.
- [`salt-review-2025dec11.md`](salt-review-2025dec11.md) is the report after the last review round:
  94.4% of curated multi-component records resolve, and no unreviewed component blocks more than 4.

To extend the list, run the script, mark the top rows of the sheet `drop` (counterion or solvent) or
`keep` (anything else, including co-actives and metal centres), append them to the list, and re-run.
Stop when the remaining blockers are a long tail of rare components.
