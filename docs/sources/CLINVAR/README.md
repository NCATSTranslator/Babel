# ClinVar

[ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) archives the clinical significance of genomic
variants. Babel ingests it as
[`biolink:SequenceVariant`](https://biolink.github.io/biolink-model/docs/SequenceVariant.html) in a
dedicated `sequencevariant` pipeline (`src/createcompendia/sequencevariant.py`,
`src/snakefiles/sequencevariant.snakefile`), covering SNVs, deletions, indels, and other variant
types ("SNPs/SNVs and stuff").

The source is NCBI's public `variant_summary.txt.gz` — an **anonymous download (no credentials)**,
fetched by the `get_clinvar` rule from `clinvar_download_url_prefix` in `config.yaml`.

## What is ingested

`variant_summary.txt` is read **by column name** (robust to its ~40 columns and any reordering).
ClinVar prefixes the first column with `#` (`#AlleleID`), so the parser strips a leading `#` from
the header and opens with `utf-8-sig` (also tolerates a BOM). Columns used:

- `VariationID` — the ClinVar variation, emitted as `CLINVAR:<VariationID>` (the `CLINVAR` prefix
  denotes the variation, Bioregistry pattern `^\d+$`; **not** the per-allele `AlleleID`). Each
  variation appears once per assembly (GRCh37/GRCh38), so identifiers are
  **deduplicated by VariationID**.
- `RS# (dbSNP)` — the dbSNP `rs` number, emitted as `DBSNP:rs<N>` (the local part is `rs`-prefixed
  per the Bioregistry `dbsnp` pattern `^rs\d+$`). `-1`/empty means no `rs` id.
- `Name` — the HGVS name, used as the label.

`write_clinvar_ids` writes `CLINVAR:<VariationID>\tbiolink:SequenceVariant`; `write_clinvar_labels`
writes the HGVS `Name`; `build_clinvar_dbsnp_relationships` writes
`CLINVAR:<VariationID> eq DBSNP:rs<N>`.

## Design notes (load-bearing)

- **The dbSNP link is an equivalence; the gene link is not.** A variant *is* its dbSNP `rs` id (same
  entity, different identifier), so `CLINVAR`↔`DBSNP` is an `eq` concord. A variant is *in* a gene
  but is not the gene, so the `GeneID` column is deliberately **not** emitted as an `eq` concord —
  `glom` merges every concord pair, which would pull the variant into a gene clique and mis-type it.
- **No `extra_prefixes`.** Both `CLINVAR` and `DBSNP` are registered for `biolink:SequenceVariant`
  in the pinned Biolink Model, so `write_compendium` keeps both without an escape hatch.
- **All variant types are `biolink:SequenceVariant`** (the general class). `biolink:Snv` (where
  `snp` maps) is a subclass; finer per-variant typing using the `Type` column is a refinement.
- **Loud failure on empty parse:** `write_clinvar_ids` raises if no variations parse (e.g. a
  truncated download), so the compendium is never silently emptied.

## Registration in the build

`sequencevariant_labels` / `sequencevariant_ids` / `sequencevariant_concords` (`[CLINVAR]`) and
`sequencevariant_outputs` (`[SequenceVariant.txt]`) in `config.yaml`; `SequenceVariant.txt` is added
to the `util.py` compendium/synonym aggregators and `report_tables.py`, so it flows through the
DuckDB/KGX/Parquet/report exports. `reports/sequencevariant_done` is in the top-level `all_outputs`.

## Testing

`tests/datahandlers/test_clinvar.py` runs over a **verbatim** fixture
(`tests/data/clinvar_variant_summary_sample.tsv` — real header + 7 real rows): VariationID dedup
across the assembly duplicates, the `rs`-prefixed `CLINVAR`↔`DBSNP` concord, the `RS='-1'` skip,
HGVS labels, the `_rs_curies` comma/`rs`-prefix handling, and the empty-download `RuntimeError`.

## Coverage / deferred

- v1 sources variants from **ClinVar only**. Full **dbSNP** (`rs`-space, hundreds of millions of
  variants) and the other Biolink-registered `SequenceVariant` prefixes (`CAID`, `SPDI`,
  `PHARMGKB.VARIANT`, the MOD allele prefixes) are deferred.
- A variant↔gene relationship (ClinVar `GeneID`/`HGNC_ID`) is intentionally not an equivalence;
  exposing it needs a non-merging relationship, not a concord.
- Source-impact report / clique diff deferred (per maintainer); `compute_cliques_for_impact_report`
  is staged but not yet registered in `PIPELINE_CONFIG`.

## Related

- `src/datahandlers/clinvar.py` — `write_clinvar_ids`, `write_clinvar_labels`,
  `build_clinvar_dbsnp_relationships`.
- `src/createcompendia/sequencevariant.py` — `build_compendia`, `compute_cliques_for_impact_report`.
- `tests/datahandlers/test_clinvar.py` — verbatim-fixture unit tests.
