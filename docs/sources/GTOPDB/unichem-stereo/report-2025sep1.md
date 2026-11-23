# GtoPdb's InChIKeys vs. UniChem's in 2025sep1

Written by `compare_gtopdb_inchikeys.py`; do not edit by hand.

| | GtoPdb's `ligands.tsv` | UniChem source 4 |
|---|---|---|
| Ligands with an InChIKey | 10,970 | 8,635 |
| Stereo-less keys | 5,174 of 10,970 (47.2%) | 4,220 of 8,635 (48.9%) |
| Keys given to more than one ligand | 221 keys, 448 ligands | 217 keys, 441 ligands |
| Ligands only this source has a key for | 2,349 | 14 |

## The 8,621 ligands with a key from both

| GtoPdb's key vs. UniChem's | Ligands |
|---|---|
| Same key | 8,589 |
| Different skeleton | 19 |
| Same skeleton; different stereo or isotope layers | 8 |
| Same skeleton; UniChem stereo-less, GtoPdb specific | 3 |
| Same skeleton; GtoPdb stereo-less, UniChem specific | 2 |
