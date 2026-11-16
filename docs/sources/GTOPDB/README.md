# GTOPDB (IUPHAR/BPS Guide to Pharmacology)

GtoPdb ligands enter the chemical pipeline from one file, `babel_downloads/GTOPDB/ligands.tsv`
(`gtopdb.pull_gtopdb_ligands()`), which supplies their identifiers and types (`write_gtopdb_ids()`),
labels and synonyms (`gtopdb.make_labels_and_synonyms()`), and structures
(`make_gtopdb_relations()`, which writes `concords/GTOPDB`).

## Structures come from GtoPdb, not UniChem

UniChem also maps GtoPdb ligands to structures (its source 4), and until issue
[#1206](https://github.com/NCATSTranslator/Babel/issues/1206) Babel read both, UniChem's first.
`INCHIKEY` is a unique prefix in `glom()`, so an identifier keeps the first key it is given and a
pair offering it a second one is refused: wherever the two disagreed, UniChem won.

Some time between the 2025dec11 and 2026jul22 builds, UniChem began assigning GtoPdb ligands
structures with no stereochemistry. No other UniChem source changed. In 2026jul22:

- 98.5% of UniChem's GtoPdb InChIKeys were stereo-less, against 47.2% of GtoPdb's own (and 48.9%
  of UniChem's in 2025dec11).
- 5,728 ligands had a stereo-less key from UniChem and a stereo-specific one from GtoPdb, up from
  3. Each sat in the clique of the stereo-unspecified record rather than the drug's:
  ruxolitinib's `GTOPDB:5688` was with `CHEBI:91405`, not `CHEBI:66919`.
- Stereoisomers that GtoPdb lists as separate ligands were merged, because they share a
  stereo-less key: 378 UniChem keys were shared by 818 ligands, against 221 keys and 448 ligands
  in GtoPdb's data.

So UniChem is no longer a source of GtoPdb structures. `GTOPDB` is absent from
`unichem.data_sources` and from `config.yaml: unichem_datasources`, and `concords/GTOPDB` is listed
in `chemical_structure_concords`, which makes `rule chemical_unichem_concordia` glom it into
`partials/UNICHEM` together with the UniChem structures.

### Why the concord is glommed with the structures, not after them

`concords/GTOPDB` is also in `chemical_concords`, where `build_untyped_compendia()` reads it after
the structure partial. Leaving it only there would have been a smaller change, and it would have
lost structures: that function runs `remove_overused_xrefs()` over every concord, which drops any
InChIKey claimed by more than one ligand. GtoPdb gives a radiolabelled ligand the key of its
unlabelled compound (`GTOPDB:1247` "[3H]histamine" and `GTOPDB:1204` "histamine"), so 448 ligands
would have had no structure at all. UniChem's GtoPdb rows were never filtered that way, and those
pairs have always shared a clique. `combine_unichem()` applies the filter only to UNII, KEGG and
DrugCentral, so reading the concord there keeps the old behaviour and changes only where the keys
come from.

The concord stays in `chemical_concords` because that is where its metadata is collected. By then
every one of its pairs is already in a clique, so the second read changes nothing.

### What moves

Of the 5,817 ligands whose two keys differed in 2026jul22, 5,705 join an existing clique that
already holds GtoPdb's key, and 112 form a new clique of the ligand and its key, because no other
source has that structure. 283 of the cliques they leave held nothing but the ligand and its
UniChem key, and disappear. The per-ligand record is in the CSV below.

### What the change costs

One identifier. `GTOPDB:2092` had a UniChem key in 2026jul22 and is not in GtoPdb's `ligands.tsv`
at all, so it no longer reaches any clique.

GtoPdb and the rest of a drug's clique can still disagree about a fully specified structure.
Tanespimycin's `GTOPDB:7751` has `AYUNIORJHRXIBJ-HTLBVUBBSA-N` in `ligands.tsv` while `CHEBI:64153`
has `AYUNIORJHRXIBJ-TXHRRWQRSA-N`. That is issue
[#1208](https://github.com/NCATSTranslator/Babel/issues/1208), and this change neither causes nor
cures it.

### Re-checking

[`unichem-stereo/`](unichem-stereo/) holds the comparison and its output for both builds:

- [`report-2025dec11.md`](unichem-stereo/report-2025dec11.md) and
  [`report-2026jul22.md`](unichem-stereo/report-2026jul22.md): how the two sources' keys differ,
  and for 2026jul22 where each affected ligand sat and which clique holds its own key.
- [`differing-ligands-2026jul22.csv`](unichem-stereo/differing-ligands-2026jul22.csv): one row per
  ligand whose two keys differ.
- [`scripts/compare_gtopdb_inchikeys.py`](unichem-stereo/scripts/compare_gtopdb_inchikeys.py)
  regenerates them from a build directory or URL.

A build made after this change writes no `UNICHEM_GTOPDB` concord. To see whether UniChem has
restored the stereochemistry, put source `"4"` back into `unichem.data_sources` locally, run
`rule get_chemical_unichem_relationships`, and run the script over the result. Until that shows the
two sources agreeing again, don't re-add it:
`test_unichem_is_not_a_source_of_gtopdb_structures` fails if someone does.
