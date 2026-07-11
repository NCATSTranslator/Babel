# CLAUDE.md — src/datahandlers/

Code-level conventions for the ~35 data-source handlers, for Claude Code. Each module downloads,
parses, and normalizes one external source into the per-source attribute files the factories in
`src/node.py` pick up by prefix. The process-level narrative — how to wire a source end to end — is
`docs/Development.md` ("Enhancing a data source ingest") and `docs/AddingNewSources.md`;
cross-cutting xref/data-quality conventions are in `docs/sources/CLAUDE.md`. This file is just the
in-module code rules.

## Attribute files a handler emits

Each handler writes whichever of four independent, optional TSVs its source supports, into
`babel_downloads/[PREFIX]/`: `labels` (CURIE→name, `NodeFactory`), `synonyms`
(CURIE→predicate→synonym, `SynonymFactory`), `taxa` (CURIE→`NCBITaxon:NNNN`, `TaxonFactory`), and
`descriptions` (CURIE→text, `DescriptionFactory`). ComplexPortal and NCBIGene emit all four.
`write_compendium` unions each identifier's `taxa` onto its clique. Match each output's
**deduplication key to its downstream consumer**: labels key on the identifier alone (first-seen
wins), but taxa and descriptions keep every distinct `(identifier, value)` pair. For a
one-taxon-per-ontology source (HP→human, MP→mammal), derive `taxa` from the already-built ids file
rather than hand-maintaining it — see `diseasephenotype.write_phenotype_taxa`.

## Code rules

- **Explicit file-path arguments** — label/synonym extraction functions should accept explicit
  `infile`/`outfile` arguments rather than calling `make_local_name` internally, so tests can pass
  `tmp_path` paths and Snakemake can declare inputs/outputs precisely.

- **IRI parsing helpers** — functions extracting IDs from external-format strings (pyoxigraph IRIs,
  SPARQL results) must validate the format and raise `ValueError` on mismatch, using a named prefix
  constant shared by the check and the extraction. See `mesh.py:get_mesh_id_from_iri()`.

- **pyoxigraph literal stripping** — use `parse_rdf_literal()` from `src/babel_utils.py` to strip
  plain/language-tagged literal quoting; don't inline the regex. Pass `base_iri` to
  `Store.bulk_load()` when loading RDF/XML with `<owl:Ontology rdf:about=""/>`, or it raises a
  builtin `SyntaxError` on the empty relative IRI.

- **IDs-file typing** — the `ids/[TYPE]/[PREFIX]` file is `CURIE→biolink:Type`; write the type
  explicitly even when every CURIE shares one prefix and type. See `docs/Development.md`.
