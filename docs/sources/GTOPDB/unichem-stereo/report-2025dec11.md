# GtoPdb's InChIKeys vs. UniChem's in 2025dec11

Written by `compare_gtopdb_inchikeys.py`; do not edit by hand.

| | GtoPdb's `ligands.tsv` | UniChem source 4 |
|---|---|---|
| Ligands with an InChIKey | 11,177 | 8,635 |
| Stereo-less keys | 5,280 of 11,177 (47.2%) | 4,220 of 8,635 (48.9%) |
| Keys given to more than one ligand | 221 keys, 448 ligands | 217 keys, 441 ligands |
| Ligands only this source has a key for | 2,558 | 16 |

## The 8,619 ligands with a key from both

| GtoPdb's key vs. UniChem's | Ligands |
|---|---|
| Same key | 8,587 |
| Different skeleton | 19 |
| Same skeleton; two different stereo layers | 8 |
| Same skeleton; UniChem stereo-less, GtoPdb specific | 3 |
| Same skeleton; GtoPdb stereo-less, UniChem specific | 2 |
