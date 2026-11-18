# Cliques claimed by two conflation groups

`conflate_synonyms()` (`src/synonyms/synonymconflation.py`) merges the synonym records of each
conflated group into one record. A group claims every member of a compendium clique that one of its
listed IDs belongs to. If two groups claim one clique — its members are listed in two conflation
lines, or it shares a CURIE with a conflated clique of another group — its records would be split
between two conflated records, so the function raises `RuntimeError` naming every such clique.

That error stops a multi-hour rule, so before making it an error we checked that no real build
would hit it. [`scripts/check_split_cliques.py`](scripts/check_split_cliques.py) counts the cases
from a finished build's conflation files and DuckDB `Edge` Parquet exports, read in place.

## 2026jul22

Run with the compendia each rule passes to `conflate_synonyms()` (`config.yaml`:
`chemical_outputs` for DrugChemical, `gene_outputs` and `protein_outputs` for GeneProtein):

| Conflation   | Conflation IDs | Conflated cliques | Clique listed in two groups | CURIE in two groups' cliques |
|--------------|---------------:|------------------:|----------------------------:|-----------------------------:|
| DrugChemical |        104,863 |           104,863 |                           0 |                            0 |
| GeneProtein  |     35,199,861 |        35,199,861 |                           0 |                            0 |

Every conflation ID is the leader of its own clique, and no conflated clique leader appears in more
than one of the compendia passed in. No ID is named by two conflation lines with different primary
IDs. The DrugChemical run takes about a minute; GeneProtein downloads an 800 MB conflation file and
two large `Edge` tables, and takes considerably longer.
