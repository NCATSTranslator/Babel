# Per-source documentation

This folder holds documentation specific to an individual upstream data source — how Babel
downloads, parses, types, and routes that source's identifiers — as opposed to the
pipeline-wide documentation in the parent `docs/` folder.

## Layout

One directory per data source, named by the source's CURIE prefix (the same prefix used in
`src/prefixes.py` and in `babel_downloads/<PREFIX>/`). A source directory may contain multiple
files when there is enough to say (ingestion, synonyms, known issues, etc.).

When you learn something non-obvious about how a source is ingested, add it here rather than
letting it accumulate in `CLAUDE.md` — `CLAUDE.md` should point here, not duplicate the detail.

## Sources documented so far

- **COMPLEXPORTAL** ([COMPLEXPORTAL/Ingestion.md](./COMPLEXPORTAL/Ingestion.md)) — the
  `MacromolecularComplex` source: which ComplexTAB columns Babel reads, downloading all species
  files, the manifest-as-download-sentinel pattern, and the per-output cross-species
  deduplication rules (labels, IDs, synonyms, taxa, descriptions).
- **MESH** ([MESH/Ingestion.md](./MESH/Ingestion.md)) — how MeSH is partitioned across compendia
  by tree letter, how Supplementary Concept Records (SCRs) are typed and routed, the
  chemical/protein D-tree split, and which MeSH branches/SCR classes we deliberately skip.
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
