# GtoPdb's InChIKeys vs. UniChem's in 2026jul22

Written by `compare_gtopdb_inchikeys.py`; do not edit by hand.

| | GtoPdb's `ligands.tsv` | UniChem source 4 |
|---|---|---|
| Ligands with an InChIKey | 11,469 | 11,176 |
| Stereo-less keys | 5,409 of 11,469 (47.2%) | 11,011 of 11,176 (98.5%) |
| Keys given to more than one ligand | 221 keys, 448 ligands | 378 keys, 818 ligands |
| Ligands only this source has a key for | 294 | 1 |

## The 11,175 ligands with a key from both

| GtoPdb's key vs. UniChem's | Ligands |
|---|---|
| Same skeleton; UniChem stereo-less, GtoPdb specific | 5,728 |
| Same key | 5,358 |
| Same skeleton; two different stereo layers | 84 |
| Different skeleton | 4 |
| Same skeleton and stereo; charge flag only | 1 |

## Where the 5,817 ligands whose keys differ would go

Read from the build's chemical `Edge.parquet` files: the clique each ligand is in, and the
clique that holds GtoPdb's own key for it. The examples are spread evenly across the ligands
that would join another clique, in CURIE order.

| Outcome | Ligands |
|---|---|
| Own key is in another clique: the ligand joins it | 5,705 |
| Of the ligands that leave their clique: it held only the ligand and its UniChem key | 283 |
| Own key is in no clique: the ligand and its key become a new clique | 112 |

| Ligand | Clique in this build | Clique of its own key |
|---|---|---|
| `GTOPDB:1000` | `PUBCHEM.COMPOUND:70007065` | `PUBCHEM.COMPOUND:5311425` |
| `GTOPDB:11380` | `PUBCHEM.COMPOUND:9842708` | `UNII:NIL6PST6V7` |
| `GTOPDB:12678` | `PUBCHEM.COMPOUND:5155` | `CHEBI:63581` |
| `GTOPDB:14002` | `PUBCHEM.COMPOUND:16129627` | `CHEBI:6736` |
| `GTOPDB:2811` | `PUBCHEM.COMPOUND:53693050` | `PUBCHEM.COMPOUND:9863342` |
| `GTOPDB:4649` | `CHEBI:24848` | `CHEBI:10642` |
| `GTOPDB:6540` | `PUBCHEM.COMPOUND:75596515` | `PUBCHEM.COMPOUND:50991498` |
| `GTOPDB:8329` | `PUBCHEM.COMPOUND:168314179` | `PUBCHEM.COMPOUND:134813893` |
