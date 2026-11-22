# ComplexPortal ingestion

[ComplexPortal](https://www.ebi.ac.uk/complexportal/) (EBI) is the only source for the
`MacromolecularComplex` compendium. Each complex has a `ComplexPortal:CPX-NNNN` accession.
The handler is `src/datahandlers/complexportal.py`; the compendium builder is
`src/createcompendia/macromolecular_complex.py`.

## What we ingest

ComplexPortal publishes one ComplexTAB TSV file per species under
`https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/`. The original Babel
ingest downloaded only a single hard-coded species file; we now download **all** of them and
union the results into one compendium.

The ComplexTAB format has 19 columns. The canonical column list lives in the source module as
`COMPLEXTAB_COLUMNS` / `COMPLEXTAB_HEADER` (next to the code that reads it) rather than only in
the docs. Babel currently reads four of them:

- Column 0 — `#Complex ac` → the `ComplexPortal:` CURIE.
- Column 1 — `Recommended name` → the label.
- Column 2 — `Aliases for complex` → `|`-separated synonyms (`has_exact_synonym`), or `-`.
- Column 3 — `Taxonomy identifier` → a bare NCBI taxon integer → `NCBITaxon:NNNN`, or `-`.
- Column 9 — `Description` → free-text description.

Columns flagged in `COMPLEXTAB_COLUMNS` as future candidates (participants, GO annotations,
cross references to Reactome/wwPDB/PubMed, disease associations) are not ingested yet but are
the obvious next sources of concords or enrichment if we want them.

## File discovery and download

File discovery scrapes the Apache autoindex HTML listing (`fetch_complexportal_tsv_filenames`)
rather than using FTP `NLST`, and downloads each file over HTTPS with `pull_via_urllib`. The
rationale and the FTP fallback plan are in the cross-cutting
[DownloadPatterns.md](../DownloadPatterns.md). `fetch_complexportal_tsv_filenames` raises if the
listing yields zero `.tsv` files, so a format change surfaces immediately instead of silently
producing an empty compendium.

## Manifest as the download sentinel

`pull_complexportal()` downloads every TSV and then, **as its last action**, writes a manifest
(`downloaded_tsv_files.txt`) listing the files it fetched. The Snakemake `get_complexportal` rule
declares the manifest (not the individual TSVs or a separate `download_done` flag) as its output:
because the manifest is written only after all downloads succeed, its presence is a reliable
signal that the download phase completed. This cleanly separates the download phase from the
extraction phase — `make_labels_synonyms_and_taxa` reads the manifest to know what to parse, and
raises a clear `RuntimeError` (telling the user to delete the manifest and re-run
`get_complexportal`) if a listed TSV is missing on disk.

## Cross-file (cross-species) deduplication

The same `CPX-NNNN` accession can appear in more than one species file (a complex conserved
across species). Each output applies the dedup key that matches its downstream consumer:

- **Labels** — keyed on the identifier alone, so the **first-seen label wins** and no duplicate
  label row is written. (Keying on the `(identifier, label)` pair instead would let two species
  files with different recommended names both emit a row, producing a malformed labels file.)
- **IDs** — one row per identifier, written directly from the source rows as
  `CURIE\tbiolink:MacromolecularComplex`. Deriving the IDs from the source rather than from the
  labels file means an accession with an **empty recommended name** still gets an ID row. (This
  replaced an `awk`-over-labels Snakemake rule.)
- **Synonyms** — keyed on `(identifier, synonym)`, so the same alias seen in two files is written
  once but distinct aliases all survive.
- **Taxa** — keyed on `(identifier, taxon_id)`, so a complex conserved across N species records
  **all N taxa**. The taxon column is a bare integer; the handler raises `ValueError` if it ever
  arrives already `NCBITaxon:`-prefixed (guards against upstream drift producing
  `NCBITaxon:NCBITaxon:9606`).
- **Descriptions** — keyed on `(identifier, description)`. Identical text repeated across species
  is written once, but distinct descriptions for the same complex are all kept, because
  `DescriptionFactory` accumulates descriptions per identifier as a set.

## Outputs

`make_labels_synonyms_and_taxa` writes `labels`, `synonyms`, `taxa`, `descriptions`, a
provenance `metadata.yaml`, and (when `idsfile` is given) the `ids/ComplexPortal` file consumed
by the compendium builder. The taxa file feeds `TaxonFactory` and the descriptions file feeds
`DescriptionFactory`; both are declared as explicit inputs to the
`macromolecular_complex_compendia` rule so the Snakemake DAG reflects that they are read at
compendium-build time.
