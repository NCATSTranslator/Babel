# Leaving `OntologyClass` out of synonym records' types

`synonym_record_types()` (`src/synonyms/record_types.py`) decides the Biolink types every synonym
record lists. It leaves out `OntologyClass` when that is only an ancestor of the clique's type (PR

## 1179; the wider question for every output is

[#1178](https://github.com/NCATSTranslator/Babel/issues/1178)). Before that, every synonym record
listed the clique type's full ancestor chain, which for most classes includes `OntologyClass`.

[`scripts/count_synonym_type_changes.py`](scripts/count_synonym_type_changes.py) measures the change
without a rebuild. A published record's `types` is its clique's ancestor list, so the script runs
`synonym_record_types()` over it and counts the records whose `types` would differ. Nothing else in
a record depends on its types, and a conflated record's types are the union of its cliques', so the
count covers the conflated files too. It streams each file and reads only the `types` field.

### Against 2026jul22

Run over the 17 files in 2026jul22's `synonyms/` directory, which is what Name Resolver loads. The
per-type files that the two conflated files replace (Gene, Protein, SmallMolecule and so on) aren't
loaded, so they weren't counted. All 17 files took under 7 minutes on a laptop.

```shell
uv run python docs/synonyms/ontology-class/scripts/count_synonym_type_changes.py <build_url> \
    AnatomicalEntity BiologicalProcess Cell CellLine CellularComponent Disease GeneFamily \
    GrossAnatomicalStructure MacromolecularComplex MolecularActivity OrganismTaxon Pathway \
    PhenotypicFeature Publication umls DrugChemicalConflated GeneProteinConflated \
    --jobs 17 --output docs/synonyms/ontology-class/2026jul22.tsv
```

| File                     |     Records | Records whose types change |
|--------------------------|------------:|---------------------------:|
| AnatomicalEntity         |     144,544 |                    144,544 |
| BiologicalProcess        |      44,600 |                     44,600 |
| Cell                     |       9,191 |                      9,191 |
| CellLine                 |      38,896 |                          0 |
| CellularComponent        |       9,078 |                      9,078 |
| Disease                  |     351,605 |                    351,605 |
| GeneFamily               |      28,463 |                          0 |
| GrossAnatomicalStructure |      10,877 |                     10,877 |
| MacromolecularComplex    |      20,579 |                          0 |
| MolecularActivity        |     193,981 |                    193,981 |
| OrganismTaxon            |   3,602,995 |                          0 |
| Pathway                  |      53,772 |                     53,772 |
| PhenotypicFeature        |      75,045 |                     75,045 |
| Publication              |           0 |                          0 |
| umls                     |   1,274,014 |                    172,043 |
| DrugChemicalConflated    | 123,913,428 |                123,626,486 |
| GeneProteinConflated     | 201,745,931 |                 70,826,491 |
| **All**                  | 331,516,999 |                195,517,713 |

[`2026jul22.tsv`](2026jul22.tsv) breaks each file down by the record's first type (the clique's own
type, or a conflated record's lead clique's). What it shows:

- A record changes exactly when its type inherits `OntologyClass`: every anatomy, disease, process
  and activity record, every Gene-led GeneProtein record, and every SmallMolecule-, Drug- and
  MolecularMixture-led DrugChemical record. Protein, CellLine, GeneFamily, OrganismTaxon and
  MacromolecularComplex don't inherit it, so none of their records change.
- Of the 288,206 DrugChemical records led by a `ChemicalEntity` clique, 1,269 change:
  `ChemicalEntity` doesn't inherit `OntologyClass`, but a clique merged into those records does.
- No record in any file is typed `OntologyClass` itself, so after the change no record Name Resolver
  loads lists it, and a Name Resolver search filtered on `OntologyClass` returns nothing.
