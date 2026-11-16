# UniChem

UniChem maps identifiers from many chemical databases to structures. Babel downloads its
`reference.tsv.gz` and `structure.tsv.gz` table dumps (`src/datahandlers/unichem.py`), and
`write_unichem_concords()` turns the sources listed in `unichem.data_sources` into one
identifier → `INCHIKEY` concord each, `concords/UNICHEM/UNICHEM_<prefix>`.
`rule chemical_unichem_concordia` gloms those into `partials/UNICHEM`, the partial every chemical
clique grows from. `INCHIKEY` is a unique prefix, so the key an identifier gets here is the one it
keeps.

## Two sources are not read from UniChem: PubChem and GtoPdb

Some time between the 2025dec11 and 2026jul22 builds, UniChem's structures for two of its sources
changed in the stereo layer. For GtoPdb the stereochemistry disappeared; that story is in
[`../GTOPDB/README.md`](../GTOPDB/README.md). For PubChem, UniChem's key stopped matching the one
PubChem publishes for 2.47 million CIDs:

| UniChem's key for a CID vs. PubChem's own | 2025sep1 and 2025dec11 | 2026jul22 |
|---|---|---|
| CIDs in UniChem | 116,164,164 | 123,860,440 |
| Same key | 114,302,709 | 121,376,193 |
| Same skeleton; PubChem stereo-less, UniChem specific | 46 | 1,454,223 |
| Same skeleton; two different stereo layers | 87 | 972,740 |
| Same skeleton; UniChem stereo-less, PubChem specific | 59 | 39,417 |
| Different skeleton | 606 | 958 |
| CID is not in PubChem's file | 1,860,657 | 16,923 |

(2025sep1 and 2025dec11 share a column because their `UNICHEM_PUBCHEM.COMPOUND` concords are
byte-identical. PubChem's side is its `CID-InChI-Key.gz` as downloaded on 2026-11-16 in every
column, so a CID "not in PubChem's file" is one PubChem has since withdrawn.)

Cliques form on an exact InChIKey, so a CID with the wrong key leaves its drug.
`PUBCHEM.COMPOUND:5284616`, sirolimus, got `QFJCIRLUMZQUOT-KADBNGAOSA-N` from UniChem in 2026jul22,
which is the key PubChem gives a different double-bond isomer (CID 21944094), while ChEBI, DrugBank
and PubChem itself all have `QFJCIRLUMZQUOT-HPLJOQBZSA-N`. Sirolimus's ChEBI clique ended up with no
PubChem CID at all (issues [#1165](https://github.com/NCATSTranslator/Babel/issues/1165) and
[#1207](https://github.com/NCATSTranslator/Babel/issues/1207)); temsirolimus split the same way.

UniChem's other sources did not move. Between 2025dec11 and 2026jul22 the key changed for 0.04% of
ChEBI identifiers, 0.06% of DrugBank, 0.6% of UNII and DrugCentral, none of HMDB and one ChEMBL
compound out of 2.47 million. So they are still read from UniChem.

### How PubChem's structures are read instead

`rule get_pubchem_structures` already downloaded PubChem's `CID-InChI-Key.gz`, and nothing read it.
`make_pubchem_inchikey_concord()` now streams it into `concords/PUBCHEM_INCHIKEY`, which is listed
in `config.yaml: chemical_structure_concords` and so glommed with the UniChem structures, in the
place `UNICHEM_PUBCHEM.COMPOUND` used to take. `PUBCHEM.COMPOUND` is gone from
`unichem.data_sources` and `unichem_datasources`.

Unlike GtoPdb's concord, this one is **not** in `chemical_concords`. It is about 125 million rows:
too large to read a second time, and too large for `write_concord_metadata()`, which counts
distinct CURIEs in memory. The `UNICHEM_*` concords have no metadata for the same reason (#648).

Compared with 2026jul22, the switch:

- gives a different key to the 2.47 million CIDs above;
- gives a key to about a million CIDs PubChem has and UniChem had not yet picked up.
  `ids/PUBCHEM.COMPOUND` comes from PubChem's own title file, so these were already identifiers in
  the build, without a structure;
- drops the roughly 17,000 CIDs that only UniChem still listed.

Compared with 2025sep1, when UniChem and PubChem agreed on all but about 800 CIDs, it changes
almost nothing, which is the point: it puts PubChem's structures back where they were.

### Re-checking

[`pubchem-inchikeys/`](pubchem-inchikeys/) holds the comparison:

- [`report-2026jul22.md`](pubchem-inchikeys/report-2026jul22.md) and
  [`report-2025dec11.md`](pubchem-inchikeys/report-2025dec11.md): the counts above, with five
  examples of each kind of difference.
- [`examples-2026jul22.csv`](pubchem-inchikeys/examples-2026jul22.csv) and
  [`examples-2025dec11.csv`](pubchem-inchikeys/examples-2025dec11.csv): up to 200 CIDs of each
  kind, spread evenly across the CID range. The full list is millions of rows and is not committed;
  the script's DuckDB file (`--workdir`) holds it as the `compared` table.
- [`scripts/compare_pubchem_inchikeys.py`](pubchem-inchikeys/scripts/compare_pubchem_inchikeys.py)
  regenerates them from a build's `UNICHEM_PUBCHEM.COMPOUND` concord, or its `Concord.parquet`.

A build made after this change writes no `UNICHEM_PUBCHEM.COMPOUND`. To see whether UniChem has
caught up with PubChem again, put source `"22"` back into `unichem.data_sources` locally, run
`rule get_chemical_unichem_relationships`, and run the script over the result.
`test_unichem_is_not_a_source_of_pubchem_structures` fails if the source is re-added without that.

To check any other UniChem source against a previous build, compare its `UNICHEM_<prefix>` concord
in the two builds identifier by identifier; a jump in the share of keys that changed, or in the
share whose second block is `UHFFFAOYSA` (no stereo), is the signal that caught both of these.
