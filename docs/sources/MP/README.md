# MP source notes

MP (Mammalian Phenotype Ontology) is used in Babel as a disease/phenotype source for
mammalian — primarily mouse — phenotypes.

In this integration, Babel:

- extracts MP identifiers for disease/phenotype processing;
- exports MP xref concords from UberGraph;
- includes MP in disease/phenotype compendium merge inputs.

Related implementation files:

- `src/createcompendia/diseasephenotype.py`
- `src/snakefiles/diseasephenotype.snakefile`
- `config.yaml`

Additional source details are documented in:

- `download.md`
- `filtering.md`
- `mappings.md`
- `impact-report.md` (auto-generated; see "Adding a new data source" in
  `CLAUDE.md` for how to regenerate it)
