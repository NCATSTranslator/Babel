# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Project Overview

Babel is the Biomedical Data Translator's identifier normalization system. It creates "cliques" —
equivalence sets of identifiers across biomedical vocabularies (e.g., recognizing that MESH:D014867
and DRUGBANK:DB09145 both refer to water). Output is consumed by Node Normalization and Name
Resolver services.

## Key Commands

### Setup

```bash
uv sync                    # Install dependencies
```

### Running the Pipeline

```bash
uv run snakemake --cores N                # Full pipeline (~500GB RAM)
uv run snakemake --cores 1 anatomy        # Single semantic type target
uv run snakemake --cores 1 chemical       # Another target
```

### Testing

```bash
PYTHONPATH=. uv run pytest                           # All tests
PYTHONPATH=. uv run pytest tests/test_node_factory.py  # Single test file
```

Note: not all tests currently pass (issue #602).

### Linting (all three checked in CI on PRs)

```bash
uv run ruff check                        # Python lint
uv run ruff check --fix                  # Python auto-fix
uv run snakefmt --check --compact-diff . # Snakemake format check
uv run snakefmt .                        # Snakemake auto-fix
uv run rumdl check .                     # Markdown lint
uv run rumdl fmt .                       # Markdown auto-fix
```

### Configuration

- Line length is 160 for both Python (ruff) and Snakemake (snakefmt).
- Main config: `config.yaml` (directory paths, version strings, prefix lists per semantic type).
- `UMLS_API_KEY` environment variable required for UMLS/RxNorm downloads.

## Architecture

### Pipeline Orchestration

Snakemake drives a two-phase pipeline:

1. **Data Collection** — downloads from FTP/web sources, producing `labels` (CURIE→name) and
   `synonyms` (CURIE→predicate→synonym) files in `babel_downloads/[PREFIX]/`.
2. **Compendium Building** — extracts identifiers per semantic type into `ids/[TYPE]`, creates
   pairwise cross-reference mappings (concords), merges them into equivalence cliques via
   union-find, and outputs enriched JSONL compendia.

The top-level `Snakefile` includes ~20 specialized snakefiles from `src/snakefiles/` — one per
semantic type plus data collection, reports, exports, and DuckDB.

### Source Code Layout (`src/`)

- **`datahandlers/`** — ~37 modules, each wrapping a specific external data source (ChEBI, UniProt,
  NCBI Gene, DrugBank, MESH, etc.). These download, parse, and normalize source data.
- **`createcompendia/`** — ~15 modules, one per semantic type (chemicals, genes, proteins, anatomy,
  disease/phenotype, etc.). These consume data handler outputs and build concords → cliques.
- **`snakefiles/`** — Snakemake rule definitions wiring data handlers to compendium creators.
- **`node.py`** — Core classes: `NodeFactory`, `SynonymFactory`, `DescriptionFactory`,
  `TaxonFactory`, `InformationContentFactory`, `TSVSQLiteLoader`.
- **`babel_utils.py`** — Download/FTP utilities, state management.
- **`util.py`** — Logging, config loading, Biolink Model Toolkit (bmt) access.
- **`make_cliques.py`** — Union-find clique merging logic.
- **`exporters/`** — Output format handlers (KGX, Parquet, JSONL).
- **`reports/`**, **`synonyms/`**, **`metadata/`** — Report generation, synonym files, provenance.

### Key Patterns

- **Factory pattern** for lazy-loading large datasets (`NodeFactory`, `SynonymFactory`, etc.).
- **`TSVSQLiteLoader`** creates in-memory SQLite databases that spill to disk, avoiding full RAM
  loading of large TSV files.
- **Biolink Model** integration via `bmt` — types, valid prefixes, and naming conventions all follow
  the Biolink Model.
- **Concord files** are the core data structure: tab-separated `CURIE1 \t Relation \t CURIE2`
  triples expressing cross-references between vocabularies.

### Conflation

Gene+Protein and Drug+Chemical each have dedicated conflation modules (`geneprotein.py`,
`drugchemical.py`) that merge their respective cliques. See `docs/Conflation.md`.

### Directories at Runtime

- `babel_downloads/` — cached source data
- `babel_outputs/intermediate/` — intermediate build artifacts
- `babel_outputs/` — final compendia, synonyms, reports, exports

# Running Babel

You may run `uv run snakemake -c all --rerun-incomplete [rulename]` to run a particular rule.
When running a download step, it will be easier to run the job in Snakemake, but when running
a rule that produces intermediate files, it might be easier to download the intermediate files from
https://stars.renci.org/var/babel/2025dec11/ (which is the `babel_output` folder from a run on a
high performance cluster)  so you don't need to download all the source files and 
rerun the entire pipeline. You can look at the resource requirements of a rule to decide which
option would be best. 

# Debugging

When looking things up in the source databases, prefer to invoke the existing download code in
this repository unless you suspect that it is incorrect, in which case use the existing code
and then compare it with an API lookup to see how they differ.

If it is easy to add a test that will either exercise this bug or check some other relevant
functionality, please suggest that when planning the bug fix.

It is very important that two different compendia don't contain the same identifier and that we
don't miss out on any valid identifiers without very good reason. If you're changing how
identifiers are filtered in one compendium, think about whether that will affect which identifiers
should be included in the other compendia to prevent any identifiers from being missed or being
added twice.
