# HP source notes

HP (Human Phenotype Ontology) is used in Babel as a disease/phenotype source for human
phenotypes. Identifiers are extracted from UberGraph via a `subClassOf` walk from
[`HP:0000118`](http://purl.obolibrary.org/obo/HP_0000118) "Phenotypic abnormality", and every
term is typed as `biolink:PhenotypicFeature`.

## Taxon assignment

Every HP term Babel ingests describes a human phenotype, so each is tagged with the taxon
[`NCBITaxon:9606`](http://purl.obolibrary.org/obo/NCBITaxon_9606) "Homo sapiens". The assignment
is written to a `babel_downloads/HP/taxa` file (rule `disease_hp_taxa`, configured by
`disease_phenotype_taxa` in `config.yaml`) and read by `TaxonFactory` in `write_compendium`, which
sets the per-identifier `t` field. The taxa file is derived directly from the HP ids file, so it
covers exactly the identifiers Babel ingests and never drifts from them.

The sibling MP source (see [`../MP/README.md`](../MP/README.md)) is tagged
[`NCBITaxon:40674`](http://purl.obolibrary.org/obo/NCBITaxon_40674) "Mammalia" the same way. HP and
MP are kept **disjoint** — no clique contains both an HP and an MP identifier — so an HP clique
carries only the human taxon and never mixes in the mammalian one. See
[`../MP/disjointness.md`](../MP/disjointness.md) for how that separation is enforced and its
clique impact.

Related implementation files:

- `src/createcompendia/diseasephenotype.py`
- `src/snakefiles/diseasephenotype.snakefile`
- `config.yaml`
