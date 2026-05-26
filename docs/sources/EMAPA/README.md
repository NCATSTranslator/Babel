# EMAPA source notes

EMAPA (Mouse Developmental Anatomy Ontology, https://obofoundry.org/ontology/emapa.html) is used in Babel as an anatomy source.

In this integration, Babel:

- extracts EMAPA identifiers for anatomy processing;
- exports EMAPA xref concords from UberGraph;
- includes EMAPA in anatomy compendium merge inputs.

Related implementation files:

- `src/createcompendia/anatomy.py`
- `src/snakefiles/anatomy.snakefile`
- `config.yaml`

Additional source details are documented in:

- `download.md` — how EMAPA data is retrieved (via the UberGraph SPARQL endpoint) and what
  queries are used.
- `filtering.md` — which root term the identifier extraction starts from and how the
  `part_of` traversal works.
- `mappings.md` — how EMAPA cross-references to other prefixes are extracted from UberGraph
  xrefs and written as concord rows.
- `impact-report.md` — auto-generated report quantifying the identifiers, biolink types, and
  clique changes EMAPA adds to the anatomy compendium. See "Adding a new data source" in
  `CLAUDE.md` for how to regenerate it.
