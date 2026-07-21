# Per-source documentation

This folder holds documentation specific to an individual upstream data source — how Babel
downloads, parses, types, and routes that source's identifiers — as opposed to the
pipeline-wide documentation in the parent `docs/` folder.

## Layout

One directory per data source, named by the source's CURIE prefix (the same prefix used in
`src/prefixes.py` and in `babel_downloads/<PREFIX>/`). A source directory may contain multiple
files when there is enough to say (ingestion, synonyms, known issues, etc.).

When you learn something non-obvious about how a source is ingested, add it here rather than
letting it accumulate in `AGENTS.md` — `AGENTS.md` should point here, not duplicate the detail.

## Sources documented so far

- **COMPLEXPORTAL** ([COMPLEXPORTAL/Ingestion.md](./COMPLEXPORTAL/Ingestion.md)) — the
  `MacromolecularComplex` source: which ComplexTAB columns Babel reads, downloading all species
  files, the manifest-as-download-sentinel pattern, and the per-output cross-species
  deduplication rules (labels, IDs, synonyms, taxa, descriptions).
- **CHEBI** ([CHEBI/sdf_tags/README.md](./CHEBI/sdf_tags/README.md)) — the data-item tags Babel
  reads out of `ChEBI_complete.sdf`, the renames that silently emptied the secondary-ID and PubChem
  ingests in `babel-1.18`, the checks that now catch a rename, and how to re-audit a new SDF.
- **DRUGBANK** ([DRUGBANK/food-and-extracts/README.md](./DRUGBANK/food-and-extracts/README.md))
  — retyping DrugBank food-and-extract products (foods, pollens, danders) out of
  `biolink:ChemicalEntity`: foods become `biolink:Food` via their UNII's NCIt class, non-food
  allergens become `biolink:ComplexMolecularMixture`.
- **ENSEMBL** ([ENSEMBL/Download.md](./ENSEMBL/Download.md)) — how Ensembl identifiers are
  downloaded via the BioMart API: per-dataset retry logic, permanently broken datasets and how to
  skip them, the attribute-batching workaround, and how partial progress is preserved across
  failed runs.
- **HP** ([HP/README.md](./HP/README.md)) — the Human Phenotype Ontology as a disease/phenotype
  source: extracting identifiers from the [`HP:0000118`](http://purl.obolibrary.org/obo/HP_0000118)
  "Phenotypic abnormality" subtree, and tagging every ingested term with the taxon
  [`NCBITaxon:9606`](http://purl.obolibrary.org/obo/NCBITaxon_9606) "Homo sapiens".
- **MESH** ([MESH/Ingestion.md](./MESH/Ingestion.md)) — how MeSH is partitioned across compendia
  by tree letter, how Supplementary Concept Records (SCRs) are typed and routed, the
  chemical/protein D-tree split, and which MeSH branches/SCR classes we deliberately skip.
- **MP** ([MP/README.md](./MP/README.md)) — the Mammalian Phenotype Ontology as a
  disease/phenotype source: extracting identifiers from UberGraph via a `subClassOf` walk from
  [`MP:0000001`](http://purl.obolibrary.org/obo/MP_0000001) "mammalian phenotype", typing every
  term as `biolink:PhenotypicFeature`, tagging each with the taxon
  [`NCBITaxon:40674`](http://purl.obolibrary.org/obo/NCBITaxon_40674) "Mammalia", exporting xref
  concords, and routing them into the disease compendia.
- **UMLS** ([UMLS/Leftover.md](./UMLS/Leftover.md)) — the "leftover UMLS" compendium: how
  unclaimed UMLS concepts are swept up and typed, the manual STY→Biolink override tables and the
  drift test that keeps them honest, and the coverage report under `reports/umls/`.
- **NCBIGene** ([NCBIGene/quoting/README.md](./NCBIGene/quoting/README.md)) — an investigation into
  how the two free-text synonym columns (`Synonyms`/`otheraliases`, `Other_designations`/
  `otherdesignations`) in `gene_info.gz` are quoted, prompted by issue #744's `''…''` fragments and
  the discovery that a trailing `''` is legitimate "double-prime" gene nomenclature.

## Cross-cutting patterns

- **Download patterns** ([DownloadPatterns.md](./DownloadPatterns.md)) — HTTP directory listing
  vs FTP for file discovery, and when to use each approach.

See the data handlers in `src/datahandlers/` and the compendium builders in
`src/createcompendia/` for the code behind each source.
