# EMAPA source notes

EMAPA (Mouse Developmental Anatomy Ontology) is used in Babel as an anatomy source.

In this integration, Babel:

- extracts EMAPA identifiers for anatomy processing;
- exports EMAPA xref concords from UberGraph;
- includes EMAPA in anatomy compendium merge inputs.

Related implementation files:

- `src/createcompendia/anatomy.py`
- `src/snakefiles/anatomy.snakefile`
- `config.yaml`

Additional source details are documented in:

- `download.md`
- `filtering.md`
- `mappings.md`
