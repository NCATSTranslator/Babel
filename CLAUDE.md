# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Project Overview

GitHub repository: <https://github.com/NCATSTranslator/Babel>

Babel is the Biomedical Data Translator's identifier normalization system. It creates "cliques" —
equivalence sets of identifiers across biomedical vocabularies (e.g., recognizing that MESH:D014867
and DRUGBANK:DB09145 both refer to water). Output is consumed by Node Normalization and Name
Resolver services.

## Key Commands

### Setup

```bash
uv sync
```

### Running the Pipeline

```bash
uv run snakemake --cores N                # Full pipeline (~500GB RAM)
uv run snakemake --cores 1 anatomy        # Single semantic type target
uv run snakemake --cores 1 chemical
```

### Testing

```bash
uv run pytest                           # All tests
uv run pytest --cov=src                 # With coverage report
uv run pytest tests/test_node_factory.py  # Single test file
uv run pytest -m unit -q               # Unit tests only (CI default)
uv run pytest --network                # Include network tests
uv run pytest --all                    # Run every test
uv run pytest -n auto                  # Parallel (all CPUs)
```

Tests use four marks (`unit`/`network`/`slow`/`pipeline`); network and pipeline tests are skipped
by default. See `tests/README.md` for the full taxonomy and where to add a new test.

Memory-hungry tests also carry a parametrized `min_memory_gb(n)` guard (registered in
`pyproject.toml`, enforced in `tests/conftest.py`) that auto-skips them on machines with less than
`n` GiB of RAM — an in-memory RDF store can need 8-10x a dump's on-disk size. Size a new rule's
`mem=` or a test's `min_memory_gb` empirically with `src/tools/memory/estimate_rdf_load_memory.py`
(see `docs/tools/Memory.md`).

- `docs/Testing.md` — testing strategy: cadence per environment (per-PR, nightly, weekly,
  pre-release), GitHub Actions vs HPC self-hosted runner trade-offs, and other strategies.

### Linting (all four checked in CI on PRs)

```bash
uv run ruff check                        # Python lint
uv run ruff check --fix                  # Python auto-fix
uv run ruff format --check               # Python format check
uv run ruff format                       # Python auto-format
uv run snakefmt --check --compact-diff . # Snakemake format check
uv run snakefmt .                        # Snakemake auto-fix
uv run rumdl check .                     # Markdown lint
uv run rumdl fmt .                       # Markdown auto-fix
```

### Configuration

- Line length is 120 for both Python (ruff) and Snakemake (snakefmt). Markdown (`rumdl`, rule
  `MD013`) wraps at 100 instead, though tables are exempt.
- Main config: `config.yaml` (directory paths, version strings, prefix lists per semantic type).
- `UMLS_API_KEY` environment variable required for UMLS/RxNorm downloads.
- `compendium_directories` in `config.yaml` maps Python compendium names to the Snakemake
  intermediate directory names when they differ (e.g., `diseasephenotype → disease`,
  `processactivitypathway → process`). Update this when adding a new semantic type whose
  directory name doesn't match its Python module name.

## Architecture

[`docs/Architecture.md`](docs/Architecture.md) is the full tour: the two-phase pipeline (data
collection → compendium building), the `src/` layout, the core data structures (concord files,
compendium JSONL), and the factory / `glom()` / `TSVSQLiteLoader` / Biolink patterns. Read it
before making structural changes. The notes below are the ones worth having in front of you every
session.

### Biolink Model Usage

The Biolink Model version is set in `config.yaml` — read it via `get_config()["biolink_version"]`
rather than hard-coding a version — and feeds both `NodeFactory` and `get_biolink_model_toolkit()`.

Always use the mapped `biolink:`-prefixed class URI (`biolink:ChemicalEntity`), never the raw
element name (`chemical entity`); `get_element()` (no `.get()` method — see `get_prefixes()`'s
comment in `src/node.py`) and `get_ancestors()` return the mapped form. `src/prefixes.py` is the
canonical prefix-constant registry; its `id_prefixes` order in the Biolink Model drives which CURIE
`NodeFactory` picks as preferred. To resolve a CURIE to a URL use
`src/util.py:get_biolink_prefix_map()` (`converter.expand("EMAPA:0")`), not a hand-rolled map.

**Node output schema** — see `NodeFactory.create_node()`'s docstring in `src/node.py`:

```python
{"identifiers": [{"identifier": CURIE, "label": str}, ...], "type": "biolink:Foo", "id": {"identifier": CURIE, "label": str}}
```

### Subsystem gotchas

- **Clique-building skeleton** — `glom_from_files()` in `src/model/cliques.py` (see its docstring
  for the three hooks); route a pipeline's `build_compendia` and
  `compute_cliques_for_impact_report` through the same wrapper so the impact report provably matches
  the build.
- **`SynonymFilter`** (`src/synonyms/filter.py`) checks every label/synonym against
  `input_data/obsolete_synonyms.yaml` before it enters a compendium — see its docstring for the
  `action` field and the `should_suppress()` contract.
- **Logging** — always use `get_logger(__name__)` from `src.util`, never `logging.getLogger`
  directly (see its docstring for why and the deferred-import exception).
- **Leftover UMLS** — `src/createcompendia/leftover_umls.py` (rule `leftover_umls`) runs last and
  writes every unclaimed valid MRCONSO concept as a single-identifier clique into
  `compendia/umls.txt` so its label survives downstream. Manual Biolink-type override tables and
  their drift test: [`docs/sources/CLAUDE.md`](docs/sources/CLAUDE.md) and
  `docs/sources/UMLS/Leftover.md`.
- **DuckDB export** — `src/snakefiles/duckdb.snakefile` builds a queryable DuckDB database
  (`Node`/`Clique`/`Edge`/`Conflation`) alongside the JSONL compendia (schema in
  `docs/DataFormats.md`); its `Edge` table answers "which clique contains CURIE X" in one query
  (`SELECT DISTINCT clique_leader FROM Edge WHERE curie IN (...)`), far cheaper than re-running glom
  or scanning JSONL.
- **Per-compendium metadata YAMLs** — `babel_outputs/metadata/<Type>.yaml` records provenance with
  per-source `prefix_counts` like `xref(CHEBI, DrugCentral): 4302`. Aggregate (prefix-pair) only —
  confirms a join pathway exists, not whether *specific* CURIEs are joinable.
- **`data/`** — gitignored local scratch space for ad hoc files (analysis notebooks, one-off
  downloads, intermediate digging); never committed.

### Per-source & developer-tool docs

Source-specific notes live under `docs/sources/<PREFIX>/` — see
[`docs/sources/README.md`](docs/sources/README.md) for the index and
[`docs/sources/CLAUDE.md`](docs/sources/CLAUDE.md) for cross-cutting xref/data-quality conventions
(read it before adding or filtering a source's cross-references). Developer tools each live in
`src/tools/<tool>/` with their own `CLAUDE.md`, documented in `docs/tools/`; see
`src/tools/CLAUDE.md` for the "thin CLI frontend" convention.

## Running Babel

Run a particular rule with `uv run snakemake -c all --rerun-incomplete [rulename]`. Download steps
are easiest run through Snakemake directly; for a rule that needs intermediate files, it's often
faster to pull them from a cluster run's output, e.g.
<https://stars.renci.org/var/babel/2025dec11/>, than to rebuild every upstream source — check the
rule's resource requirements to decide.

A killed run can leave `LockException: Directory cannot be locked` on the next invocation; clear it
with `uv run snakemake --unlock`.

Most semantic-type targets are much cheaper than the full pipeline (anatomy builds end-to-end on a
laptop in ~25 minutes; the README's 500 GB figure is for the heaviest targets only). See
`docs/RunningBabel.md` for a per-target sizing breakdown and common build issues.

## Adding a new data source

`docs/AddingNewSources.md` is the full guide: how to wire a source (prefix, data handler, compendium
hook, Snakemake rules, `config.yaml`, docs, tests), then generate and read its source-impact report
— including assembling the intermediate inputs from a `stars.renci.org` snapshot when a full local
build (~500 GB RAM) is impractical. Two things the report exists to catch: an ids file missing its
Biolink type (see `docs/Development.md`), and a prefix not yet registered in the Biolink Model for
its class (`write_compendium()` silently drops such CURIEs — EMAPA's
`biolink:GrossAnatomicalStructure` terms are the current example).
**Generate and commit the report** (`uv run source-impact-report --source <SOURCE>`) and, for
changes that *restructure* existing cliques, follow up with `babel-clique-diff` — see
`src/tools/source_impact_report/CLAUDE.md` and `src/tools/clique_diff/CLAUDE.md` for the tool
internals.

Use `retries: 3` (not `retries: 10`) on network-backed Snakemake rules (UberGraph, FTP, HTTP) — see
`docs/AddingNewSources.md` step 4 for why. `src/tools/slurm/CLAUDE.md` covers analyzing a
(possibly partial) run on the cluster.

## Conventions

Point-of-use conventions live where they apply: process-level guidance for adding/enhancing an
ingest is in `docs/Development.md` ("Enhancing a data source ingest"); datahandler code rules
(attribute files, IRI parsing, pyoxigraph, file-path args) are in
[`src/datahandlers/CLAUDE.md`](src/datahandlers/CLAUDE.md); test conventions are in
[`tests/CLAUDE.md`](tests/CLAUDE.md). The rules below apply repo-wide.

- **Configuration over constants** — prefer `config.yaml` over module-level Python constants for
  any value that is a data-level choice (a list of prefixes, a threshold, a flag) rather than pure
  logic. Constants buried in Python files are invisible to readers of `config.yaml` and are easily
  missed when related settings change. Module-level constants are fine for values that are pure
  implementation details with no user-facing meaning.

- **Document every configuration value** — every entry in `config.yaml` and every module-level
  constant that remains in Python must have an inline comment explaining *what it controls* and
  *why the chosen value was picked*. One-word names are not self-documenting.

- **Keep related settings together** — configuration entries that constrain or depend on each other
  must sit adjacent in `config.yaml`, separated from unrelated entries. For example, the anatomy
  block groups `anatomy_prefixes`, `anatomy_ids`, `anatomy_concords`, `anatomy_outputs`, and
  `anatomy_unique_prefixes` together so that adding a new source requires reviewing all of them at
  once. Never scatter correlated settings across the file.

- **`babel_pipeline` vs `biolink_type`** — easy to confuse; keep distinct in code and variable
  names. See the Terminology section of `docs/AddingNewSources.md` for the full distinction
  (plus the unrelated third term, `umls_semantic_type`/`sty`).

- **Biolink class references** — always use the named constants from `src/categories.py`
  (e.g. `CHEMICAL_ENTITY`, `DRUG`) rather than hardcoding `"biolink:..."` strings; add a missing
  constant there first.

- **Error handling** — raise exceptions (`RuntimeError`, `ValueError`) rather than
  `print(...) + exit(1)`, which bypasses Python's exception machinery and breaks unit testing.

- **Docstrings** — give modules, classes, and non-trivial functions a docstring covering what they
  do and any non-obvious behavior. Name functions for what they do — `fetch_*` (not `get_*`) when
  the call hits the network.

## Debugging

Prefer invoking this repo's existing download code over a fresh API lookup when investigating a
source database, unless you suspect that code is wrong — then compare the two to see how they
differ.

When a bug fix is easy to cover with a test, suggest adding one as part of the fix.

Two different compendia must never share an identifier, and no valid identifier should be dropped
without good reason — when changing how one compendium filters identifiers, check the effect on
every other compendium too.

## Documentation

When making a significant change, check whether it affects any documentation (`docs/*.md`, `*.md`)
and update it, or suggest a new doc file if one is needed.

Prefer section headings over horizontal pipes for dividing up documentation.

When a documentation file mentions a specific ontology term by CURIE, link it to its OBO
PURL and include the preferred label in double-quotes:

```markdown
[`EMAPA:0`](http://purl.obolibrary.org/obo/EMAPA_0) "anatomical structure"
```

Resolve CURIEs with `get_biolink_prefix_map()` (see Biolink Model Usage above). Preferred labels
come from `babel_downloads/<PREFIX>/labels` (tab-separated `CURIE\tlabel`).
