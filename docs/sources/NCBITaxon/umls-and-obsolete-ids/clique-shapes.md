# OrganismTaxon clique shapes

- Before: main (bb882867)
- After: this branch (37e01618)

| | before | after |
|---|---|---|
| cliques | 3,785,393 | 3,072,393 |
| cliques holding only a UMLS identifier | 745,560 | 33,189 |
| cliques with two identifiers of one prefix | 0 | 0 |
| largest clique | 3 | 3 |

In the after build, 780,474 cliques hold both an NCBITaxon and a UMLS identifier. 721,650 have the
same label on both. Of the other 58,824, 48,981 have the UMLS label among NCBITaxon's own synonyms.
