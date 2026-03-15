# Babel Architecture

This document describes how Babel's source code is organized, how data flows through the pipeline,
and the key patterns and data structures that appear throughout the codebase. It is intended for
contributors who want to understand the system before making changes.

For instructions on how to run and configure the pipeline, see
[RunningBabel.md](./RunningBabel.md). For the development workflow and known challenges, see
[Development.md](./Development.md).

---

## Pipeline overview

Babel's pipeline has two phases, orchestrated by [Snakemake](https://snakemake.github.io/):

1. **Data collection** — individual data handlers download source data from FTP servers and the
   web, then parse and normalize it into two kinds of files per source:
   - `labels` files: CURIE → preferred name mappings
   - `synonyms` files: CURIE → predicate → synonym mappings

   These files are written into `babel_downloads/[PREFIX]/`.

2. **Compendium building** — for each semantic type (e.g. chemicals, genes, anatomy), a compendium
   creator module reads the relevant label and synonym files, extracts the identifiers for that
   type into `babel_outputs/intermediate/[TYPE]/ids/`, produces pairwise cross-reference files
   called **concords**, merges the concords into equivalence cliques using a union-find algorithm,
   and writes enriched JSONL compendia to `babel_outputs/`.

The top-level `Snakefile` coordinates the whole pipeline by including ~20 specialized snakefiles
from `src/snakefiles/` — one per semantic type, plus files for data collection, reports, exports,
and DuckDB integration.

---

## Source code layout

All Python and Snakemake source code lives under `src/`:

| Directory / file | Purpose |
|------------------|---------|
| `src/datahandlers/` | ~37 modules, one per external data source. Each module downloads, parses, and normalizes data from a specific source (ChEBI, UniProt, NCBI Gene, DrugBank, MESH, etc.). |
| `src/createcompendia/` | ~15 modules, one per semantic type (chemicals, genes, proteins, anatomy, disease/phenotype, etc.). These consume data handler outputs, build concords, and write final compendia. |
| `src/snakefiles/` | Snakemake rule files that wire data handlers to compendium creators and define the full dependency graph. |
| `src/node.py` | Core factory classes: `NodeFactory`, `SynonymFactory`, `DescriptionFactory`, `TaxonFactory`, `InformationContentFactory`, `TSVSQLiteLoader`. |
| `src/make_cliques.py` | Union-find clique merging logic — takes concord files and produces equivalence cliques. |
| `src/babel_utils.py` | Download and FTP utilities, state management helpers. |
| `src/util.py` | Logging setup, config loading, Biolink Model Toolkit (`bmt`) access. |
| `src/exporters/` | Output format handlers for KGX, Apache Parquet, and JSONL. |
| `src/reports/` | Report generation code. |
| `src/synonyms/` | Synonym file generation. |
| `src/metadata/` | Provenance and metadata handling. |

---

## Key data structures

### Concord files

Concord files are the central intermediate data structure in Babel. Each concord file is a
tab-separated file of triples:

```text
CURIE1 <TAB> Relation <TAB> CURIE2
```

Each triple expresses that `CURIE1` and `CURIE2` are related by `Relation` (typically
`skos:exactMatch` or an equivalent). The compendium building phase reads all concord files for a
semantic type and feeds them into the union-find algorithm (`make_cliques.py`) to produce
equivalence cliques.

### Compendium JSONL

Each line of a compendium file is a JSON object representing one clique. A clique includes:

- `identifiers` — list of all equivalent CURIEs, in preferred-prefix order
- `ic` — information content score (from UberGraph)
- `taxa` — associated taxa (for genes, proteins, etc.)
- `preferred_name` — the preferred human-readable label for the clique
- `descriptions` — descriptions collected from UberGraph
- `type` — Biolink semantic type

The first identifier in `identifiers` is the preferred identifier for the clique. See
[DataFormats.md](./DataFormats.md) for the full format specification.

---

## Key patterns

### Factory pattern for large datasets

`NodeFactory`, `SynonymFactory`, `DescriptionFactory`, `TaxonFactory`, and
`InformationContentFactory` (all in `src/node.py`) use a factory pattern for lazy loading.
Rather than loading entire datasets into memory up front, they load data on demand and cache
results. This is important because many source files are gigabytes in size.

### TSVSQLiteLoader

`TSVSQLiteLoader` (in `src/node.py`) loads tab-separated files into in-memory SQLite databases
that spill to disk when memory pressure is high. This avoids the need to hold entire large TSV
files in RAM, which would be infeasible given Babel's data volumes.

### Union-find clique merging

`src/make_cliques.py` implements a union-find (disjoint-set) data structure to merge concord
triples into equivalence cliques. Each CURIE starts as its own set; each `CURIE1 exactMatch CURIE2`
triple unions the two sets. At the end, each set is one clique.

### Biolink Model integration

All semantic types, valid CURIE prefixes, and naming conventions follow the
[Biolink Model](https://github.com/biolink/biolink-model). The `bmt` library (Biolink Model
Toolkit) is accessed via `src/util.py` and is used throughout the codebase to validate types,
look up preferred prefix orderings, and check whether a given prefix is valid for a type.

### Conflation modules

Gene+Protein and Drug+Chemical each have dedicated conflation modules
(`src/createcompendia/geneprotein.py` and `src/createcompendia/drugchemical.py`) that merge their
respective cliques after the initial compendium build. See [Conflation.md](./Conflation.md) for
details on what conflation means and how it works.

---

## Runtime directories

When the pipeline runs, it creates and populates these directories:

| Directory | Contents |
|-----------|----------|
| `babel_downloads/` | Cached source data, organized by prefix (e.g. `babel_downloads/CHEBI/`). Can be reused across runs. |
| `babel_outputs/intermediate/` | Intermediate build artifacts: ids files, concord files, per-type label and synonym aggregates. |
| `babel_outputs/` | Final outputs: compendia (JSONL), synonym files, reports, and exports (Parquet, KGX). |

---

## Configuration

The main configuration file is `config.yaml` at the repository root. It contains:

- Directory paths for inputs and outputs
- Version strings for the current build
- Per-semantic-type lists of valid CURIE prefixes and their priority ordering
- Chemical-specific settings such as `preferred_name_boost_prefixes` and `demote_labels_longer_than`

The `UMLS_API_KEY` environment variable is required for downloading UMLS and RxNorm data.
