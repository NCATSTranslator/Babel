# Manual compendium

This document covers Babel's hand-curated identifier path: terms that do not come from a
normal downloader or parser, but are added directly to a small NDJSON source-of-truth file and
then turned into a compendium.

The code lives in `src/createcompendia/manual.py`; the Snakemake rules are in
`src/snakefiles/manual.snakefile`.

## What it is for

The manual compendium exists for identifiers that Babel needs to expose before there is a full
source-specific ingest. It is intentionally small, explicit, and easy to audit.

Unlike most Babel sources, the manual compendium has:

- no external download step;
- no intermediate `ids/` or `concords/` files;
- one hand-maintained input file, `input_data/manual_terms.ndjson`.

It is also currently **opt-in / unstable**: the stable build excludes it unless Snakemake is run
with `--config unstable=true`. The toggle is `config["unstable"]` in `config.yaml`.

## Source of truth

`input_data/manual_terms.ndjson` contains one JSON object per line. Each object has:

- `curie` — the primary identifier, for example `EUPATH:0009259`
- `type` — the Biolink class CURIE, for example `biolink:ClinicalFinding`
- `preferred` — the preferred label
- `alternatives` — optional list of synonym strings, default `[]`
- `equivalents` — optional list of equivalent CURIEs, default `[]`

`src/createcompendia/manual.py:read_manual_terms()` parses the file into `ManualTerm` records.

## Build path

The Snakemake rules are:

- `manual_labels_synonyms` — reads `input_data/manual_terms.ndjson` and materializes per-prefix
  `labels` and `synonyms` files under `babel_downloads/<PREFIX>/`
- `manual_compendia` — builds `babel_outputs/compendia/Manual.txt`,
  `babel_outputs/synonyms/Manual.txt`, and `babel_outputs/metadata/Manual.txt.yaml`
- `manual` — gzips `Manual.txt`'s synonym output and writes `reports/manual_done`

The compendium builder itself is `build_manual()`, which hands a heterogeneous list of
`TypedClique` values to `write_compendium(..., node_type=None, extra_prefixes=...)`.

## How names are produced

The manual path does not inject synonyms directly into `write_compendium()`. Instead,
`write_manual_labels_and_synonyms()` writes the same per-prefix files that `SynonymFactory`
expects at build time:

- `babel_downloads/<PREFIX>/labels`
- `babel_downloads/<PREFIX>/synonyms`

The writer follows the repo convention used in `src/datahandlers/umls.py`: the preferred label
and every alternative are written as `HAS_EXACT_SYNONYM`, and the preferred label is also written
to the `labels` file.

Only a term's **primary prefix** must be listed in `config["manual_prefixes"]`, because only the
primary CURIE gets its own labels/synonyms rows. Equivalent CURIEs do not get separate synonym
materialization.

## How clique construction works

Each NDJSON line becomes one clique.

- With no `equivalents`, the clique is a singleton: `[curie]`.
- With `equivalents`, the clique identifiers are `[curie] + equivalents`.

`build_manual_cliques()` keeps the primary `curie` first and deduplicates any repeated
equivalents. If a CURIE appears in more than one manual term, the build raises `ValueError`
instead of silently creating overlapping cliques. Merge such cases into a single NDJSON line.

This path is intended for **novel manual additions**. It is not a replacement for adding a real
concord into another compendium's `glom()` path.

## Why `extra_prefixes` matters

Many manual CURIEs will use prefixes that are not in the Biolink Model's `id_prefixes` for the
chosen type. `build_manual_cliques()` collects every distinct prefix used by the primary CURIE and
its equivalents, then passes those prefixes via `extra_prefixes` to `write_compendium()`.

Without that, `NodeFactory.create_node()` would strip those identifiers during node creation and
the manual clique would either lose members or disappear entirely.

## Current scope and limits

- The manual compendium is currently unstable/opt-in.
- It is designed for a small number of explicit additions, not for bulk ingest.
- It does not create normal per-source `ids/` or `concords/` intermediates.
- It does not currently participate in source-impact-report synthetic re-glom flows the way a
  normal source does.

## Related files

- `input_data/manual_terms.ndjson` — source of truth
- `src/createcompendia/manual.py` — parser, label/synonym writer, clique builder
- `src/snakefiles/manual.snakefile` — Snakemake rules
- `config.yaml` — `manual_prefixes`, `manual_outputs`, `unstable`
- `docs/sources/EUPATH/README.md` — current concrete example
