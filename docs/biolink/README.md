# Biolink class notes

This folder holds notes organised by **Biolink class**: how Babel represents a class, or
deliberately does not, and the modelling questions that are still open for it. The per-source notes
in [`../sources/`](../sources/README.md) say how one upstream vocabulary is ingested; a class note
cuts across sources, because the same question ("is this a family or a protein?") arrives from UMLS,
MeSH, the Protein Ontology and HGNC at once and has to be answered the same way for all of them.

Add a note here when a Biolink class needs a decision that no single source's documentation can
hold. Name the file after the class (`ProteinFamily.md`), keep its analysis scripts and generated
output in a sibling directory named after the note in kebab case (`protein-family/`), and follow the
conventions in [`../sources/CLAUDE.md`](../sources/CLAUDE.md) for committing the check rather than
the conclusion.

## Notes so far

- **ProteinFamily** ([ProteinFamily.md](./ProteinFamily.md)) — how protein families and other
  non-sequence protein concepts ("Claudins", "Hemoglobins", "Lipoproteins") should be modelled
  across Babel, NodeNorm, NameRes, the Biolink Model and the UI: the options, the decisions the
  group has to make, and the Babel maintainers' recommendation. Measurements in
  [`protein-family/`](./protein-family/).
