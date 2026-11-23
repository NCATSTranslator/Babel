# UniChem

[UniChem](https://www.ebi.ac.uk/unichem/) maps each source's compound IDs to structures. It is
where Babel gets the InChIKeys of most chemical sources, and so it decides most structure-based
merges in the chemical pipeline.

## What Babel reads

- `reference.tsv.gz` and `structure.tsv.gz` from UniChem's
  [table dumps](https://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/)
  (`download_unichem_reference()`, `download_unichem_structure()`).
- Only the sources in `data_sources` (`src/datahandlers/unichem.py`), mirrored by
  `config.yaml: unichem_datasources`. `filter_unichem()` keeps their current assignments, and
  `write_unichem_concords()` writes one `UNICHEM_<prefix>` concord per source.
- `combine_unichem()` gloms those concords first. `INCHIKEY` is a unique prefix, so an identifier
  keeps the first key it is given: wherever UniChem and a source's own structure disagree, UniChem
  wins, unless the source is in `config.yaml: chemical_structure_concords` and UniChem's copy is
  left out (GtoPdb, [GTOPDB/README.md](../GTOPDB/README.md)).

## How UniChem gets its structures

From UniChem's documentation (<https://chembl.gitbook.io/unichem>, read 2026-11-23):

- It uses a source's own Standard InChIs when the source supplies them. Otherwise it computes
  them with RDKit, from the SMILES of a tabular file or the Molblock of an SDF. So a UniChem key
  can differ from the key the source itself publishes.
- An assignment is current (1) or obsolete (0), and an obsolete one is supposed to be kept, with
  the last source release in which it was current. `reference.tsv.gz` has both; Babel reads only
  current ones.
- There is no changelog. Changes reach the dumps unannounced: the reference file's `ASSIGNMENT`
  column became `ASSIGMENT` in 2026-06 (`UNICHEM_REFERENCE_TSV_HEADER`), and in the first half of
  2026 GtoPdb's structures lost their stereochemistry, apparently in a reload that kept no
  obsolete rows (#1206).

So when a UniChem source's structures look wrong, compare them with the source's own where Babel
can read both, and compare each source's share of stereo-less keys with the previous build (#1258
proposes making that a build check). `docs/sources/GTOPDB/unichem-stereo/` is a worked example.
