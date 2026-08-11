# Transcript

The Transcript compendium exposes Ensembl transcript identifiers (`ENST*`) as
[`biolink:Transcript`](https://biolink.github.io/biolink-model/docs/Transcript.html). It resolves
the transcript checkbox in [Babel#84](https://github.com/NCATSTranslator/Babel/issues/84): Babel
already downloaded transcript identifiers but parsed them away.

The handler is `src/createcompendia/transcript.py`; the pipeline is
`src/snakefiles/transcript.snakefile` (target `transcript`). Build it with
`uv run snakemake -c all transcript`.

## Where the identifiers come from

NCBI's `gene2ensembl.gz` (downloaded by the existing `get_ncbigene` rule — **no new download**) has
an `Ensembl_rna_identifier` column (column 4) that the gene pipeline never reads
(`gene.build_gene_ncbi_ensembl_relationships` uses only the gene columns). `write_transcript_ids`
reads that column and writes the **unversioned** ENST as a `biolink:Transcript` identifier
(`intermediate/transcript/ids/ENSEMBL`).

`build_transcript_ensembl_relationships` writes one concord
(`intermediate/transcript/concords/ENSEMBL`): each **versioned** ENST (`ENST00000263368.3`) is
linked `eq` to its **unversioned** form (`ENST00000263368`), following the
[issue #72](https://github.com/NCATSTranslator/Babel/issues/72) version-stripping pattern so a
versioned query normalizes into the same clique.

## Design constraints (load-bearing)

- **Own compendium.** `ENSEMBL` is shared by the Gene, Protein, and Transcript `id_prefixes`, and
  two compendia must never share an identifier, so ENST identifiers are built in this isolated
  pipeline rather than added to the gene/protein concords.
- **No transcript↔gene or transcript↔protein edges.** `glom` merges *every* concord pair regardless
  of the relation column (`eq` and `xref` alike). A transcript↔gene concord would therefore pull the
  transcript into a gene clique and mis-type it as `biolink:Gene`. Those cross-granularity
  relationships are *not* equivalences and are a deliberate follow-up; the source data for them
  (`gene2ensembl.gz` columns 1/2/6, `idmapping.dat` `Ensembl_TRS`) is already on disk.
- **`ENSEMBL` is registered for `biolink:Transcript`** in the pinned Biolink Model (4.4.3
  `id_prefixes: [ENSEMBL, FB]`), so no `extra_prefixes` escape hatch is needed.
- **`ENSEMBL` is not a `unique_prefixes` entry** here: a transcript clique legitimately holds the
  versioned and unversioned ENST together.
- **v1 cliques are unlabeled.** Ensembl assigns no labels to its transcript identifiers and the
  versioned↔unversioned concord has no labeled partner, so every Transcript node ships with an empty
  label until the deferred transcript↔gene/protein relationships land.

## Coverage and deferred work

v1 sources the transcript set from `gene2ensembl.gz` alone. That file reports one current version
per transcript and only for genes with a RefSeq↔Ensembl match, so coverage is a subset of all
Ensembl transcripts. Deferred coverage extensions:

- `UniProtKB/idmapping.dat` `Ensembl_TRS` rows (UniProt-linked ENST), also currently dropped.
- The BioMart / MyGene `ensembl_transcript_id` attribute (see `docs/sources/ENSEMBL/Download.md`).
- RefSeq RNA accessions (`NM_`/`NR_`): deferred because no prefix is registered for them on
  `biolink:Transcript`, so `write_compendium` would drop them.
- Transcript↔gene and transcript↔protein relationships (not equivalences — see above).

## Registration in the build

`Transcript.txt` is added to `get_all_compendia` / `get_all_synonyms*` in `src/snakefiles/util.py`,
so it flows through the DuckDB, Parquet, and KGX exports, and `reports/transcript_done` is in the
top-level `all_outputs` rule. Config: `transcript_ids`, `transcript_concords`, `transcript_outputs`
in `config.yaml`.

## Source-impact report

Generated (synthetic mode) and committed at [`impact-report.md`](impact-report.md). Transcript is a
new, isolated pipeline, so there is no published baseline: the "before" state is empty and section 4
reports every transcript clique as pure-new. The per-clique detail CSVs are skipped
(`--no-detail-files`): at ~15.8M cliques they would be multi-GB and are impractical to commit
(regenerate with `uv run source-impact-report --source ENSEMBL` if needed).

Summary:

- **15,803,119 Ensembl transcript identifiers** added (all `biolink:Transcript`) -> **15,803,119 new
  cliques** (mostly singletons + versioned<->unversioned ENST pairs).
- **10,117,291 new cross-references** (versioned<->unversioned Ensembl transcript `eq` equivalences
  from `gene2ensembl.gz`, the issue #72 pattern).
- **0 merges** (transcript-internal concords only; no transcript<->gene/protein edges -- see Design
  constraints).
- `ENSEMBL` is registered for `biolink:Transcript` in the pinned Biolink Model, so no
  `extra_prefixes` escape hatch is needed and no "NOT emitted" flag appears.

Regenerate after a typing or extraction change:

```bash
uv run source-impact-report --source ENSEMBL
```

## Related

- `src/createcompendia/transcript.py` — `write_transcript_ids`,
  `build_transcript_ensembl_relationships`, `build_compendia`, `compute_cliques_for_impact_report`.
- `tests/test_transcript.py` — offline unit tests over `tests/data/gene2ensembl_sample.gz` (verbatim
  rows).
- [Babel#84](https://github.com/NCATSTranslator/Babel/issues/84) — the originating request.
