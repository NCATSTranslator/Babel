# ChemicalParent conflation measurements

The ChemicalParent conflation (`src/createcompendia/chemicalparent.py`, described in
[`docs/Conflation.md`](../../Conflation.md#chemicalparent)) groups chemical cliques whose InChIKeys
differ only in the protonation block.

- [`scripts/measure_protonation_groups.py`](scripts/measure_protonation_groups.py) replays the
  production grouping over a published build's DuckDB `Edge.parquet` files and reports group counts,
  group sizes, the compendia each group spans, and overlap with DrugChemical. Its docstring has the
  commands to fetch the inputs and run it.
- [`2025dec11.md`](2025dec11.md) is its output for the 2025dec11 build.

Re-run it against a new build before changing the grouping rule, and commit the new report beside
this one.
