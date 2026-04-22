# Test Suite

## Overview

Tests are organized along two independent axes:

- **Mark** — controls *when* a test is run (see [Marks](#marks) below for the full table).
- **Directory** — reflects *what* is being tested.

| Directory | What lives there |
|-----------|-----------------|
| `tests/` (root) | Core utility tests: `glom`, `LabeledID`, `NodeFactory`, `ThrottledRequester`, FTP utilities, UberGraph, and gene-protein conflation |
| `tests/datahandlers/` | One test file per module in `src/datahandlers/` |
| `tests/pipeline/` | Full pipeline integration tests that call `write_*_ids()` functions and check the resulting intermediate files; require `babel_downloads/` to be pre-populated |
| `tests/pipeline/checks/` | Per-compendium regression assertions tied to specific GitHub issues, designed for test-driven development |

**CI** runs only `unit` tests (`uv run pytest -m unit -q`). Keep unit tests fast, offline, and
dependency-free so they remain cheap to run on every PR.

**Pipeline tests** cache their output to the same stable paths that Snakemake uses
(`babel_outputs/intermediate/…`), so a prior full pipeline run is automatically reused. Pass
`--regenerate` to force `write_X_ids()` to re-run even if its output already exists in
`babel_outputs/intermediate/`. See
[Pipeline > Caching](pipeline/README.md#caching-of-intermediate-files) for details.

### Where to add a new test

- **Pure function or small data transform** → `unit` test in `tests/` root (or `tests/datahandlers/`
  if it exercises a specific data handler module).
- **Specific CURIE that should (or should not) appear in a compendium** → append a `ChemCheck` or
  `ConcordCheck` tuple to `tests/pipeline/checks/test_chemicals.py` (or create a parallel file for
  another compendium). No Snakemake needed for ID-presence checks.
- **Cross-vocabulary identifier exclusivity for a new vocabulary** → add fixtures to
  `tests/pipeline/conftest.py` and one entry to `VOCABULARY_REGISTRY` in
  `test_vocabulary_partitioning.py`. See [New pipeline tests](pipeline/README.md#new-pipeline-tests)
  in the pipeline README.
- **Pipeline behavior specific to one vocabulary** → add `tests/pipeline/test_X_pipeline.py`
  marked `pipeline`.

See [Future Plans](#future-plans) at the bottom of this file for a more detailed roadmap of
planned test locations and conventions.

## Running Tests

```bash
uv run pytest                           # All tests
uv run pytest --cov=src                 # With coverage report
uv run pytest tests/test_glom.py        # Single test file
```

Coverage is opt-in: pass `--cov=src` (or `--cov=src --cov-report=html`) to generate
a report. Coverage configuration is in `pyproject.toml` under `[tool.coverage.*]`.

## Marks

Tests are tagged with marks to control which subset runs in a given context:

| Mark       | What it covers                                                           | Network?  | Typical duration | Timeout |
|------------|--------------------------------------------------------------------------|-----------|------------------|---------|
| `unit`     | Pure functions, in-memory logic, small fixtures in `tests/data/`         | No        | Seconds          | 30 s    |
| `network`  | Requires live internet (FTP, SPARQL, BioMart, external APIs)             | Yes       | Seconds–minutes  | 600 s   |
| `slow`     | Correct but takes >30s — large fixture processing, SQLite spill, etc.    | Sometimes | >30s             | 600 s   |
| `pipeline` | Invokes Snakemake rules; requires `babel_downloads/` to be pre-populated | Yes       | Minutes–hours    | 3600 s  |

You can adjust the timeout for marks in [conftest.py](conftest.py).

### Default behavior

- `pytest` alone: runs `unit` and `slow` tests; skips `network` and `pipeline`
- `pytest --network`: also runs `network` tests
- `pytest --pipeline`: also runs `pipeline` tests (ensure `babel_downloads/` exists first)
- `pytest --pipeline --regenerate`: forces `write_X_ids()` to re-run even if its output already
  exists in `babel_outputs/intermediate/` (useful after changing compendium filtering logic; see
  **Caching** below)
- `pytest --all`: runs everything (equivalent to `--network --pipeline`)

### Convenience commands

```bash
uv run pytest -m unit                             # unit tests only (CI default)
uv run pytest -m "unit or network" --network      # unit + live-service checks
uv run pytest -m "unit or slow"                   # unit + slow offline tests
uv run pytest --all --no-cov                      # run every test (no coverage)
uv run pytest -m pipeline --pipeline -x --no-cov # one pipeline test at a time
uv run pytest -m "not pipeline"                   # everything except full pipeline runs
uv run pytest -n auto --no-cov                    # parallel (all CPUs), skip coverage
uv run pytest -n 4 -m unit                        # 4 workers, unit tests only
```

## Test Files

### Core

- **`test_glom.py`** (`unit`) — Tests the `glom` utility, which merges pairwise identifier
  sets into equivalence cliques (union-find). Covers basic merging, iterative
  multi-call usage, tuple vs. set inputs, and the expected `ValueError` when sets
  contain more than two members.

- **`test_LabeledID.py`** (`unit`) — Tests that `LabeledID` objects (a CURIE paired with a
  human-readable label) compare correctly against bare strings and behave properly
  in sets.

- **`test_geneproteiny.py`** (`unit`) — Integration test for gene-protein conflation. Runs
  `build_compendium` with gene and protein compendia plus a concordance file from
  `data/` and verifies output is produced.

- **`test_node_factory.py`** (`network`) — Tests `NodeFactory`, the central class for building
  normalized nodes. Covers ancestor retrieval, prefix ordering, identifier
  normalization (selecting the best CURIE from an equivalence set), label
  application, UMLS filtering, PubChem disambiguation, and deduplication of
  `LabeledID` objects. Marked `network` because the `node_factory` fixture calls
  `bmt.Toolkit`, which fetches `biolink-model.yaml` and `predicate_mapping.yaml`
  from GitHub on first use.

### Data Handlers

- **`datahandlers/test_mesh.py`** (`unit`) — Unit tests for `src/datahandlers/mesh.py`.
  Covers `write_ids()` parameter validation, SCR filtering logic (mock-based), and
  `Mesh.get_scr_terms_mapped_to_trees()` using an inline pyoxigraph store.

- **`datahandlers/test_ensembl.py`** (`network`, `xfail`) — Integration test for the Ensembl
  BioMart data handler. Pulls real data from BioMart, verifies that batched downloads
  (splitting attribute lists across multiple queries) produce the same results as
  single-query downloads, and checks TSV output correctness. Uses `tmp_path`.

### Pipeline

See [`tests/pipeline/README.md`](pipeline/README.md) for caching behavior, fixture setup,
and how to add new checks or vocabularies.

- **`pipeline/test_vocabulary_partitioning.py`** (`pipeline`) — Parametrized mutual-exclusivity
  checks for all registered vocabularies: every `write_X_ids()` must produce non-empty output
  and no identifier may appear in more than one compendium. Currently covers MESH, UMLS, OMIM,
  NCIT, and GO.

- **`pipeline/test_mesh_pipeline.py`** (`pipeline`) — MeSH-specific targeted assertions
  ([issue #675](https://github.com/NCATSTranslator/Babel/issues/675)): chemicals must exclude
  all D05 terms, D08 protein subtrees, and D12.776 — but must include D08.211 Coenzymes.

- **`pipeline/test_umls_pipeline.py`** (`pipeline`) — UMLS-specific targeted assertions:
  chemicals must not contain UMLS IDs claimed by the protein compendium.

- **`pipeline/checks/`** (`pipeline`) — Per-compendium regression assertions tied to GitHub
  issues (ID-presence and direct cross-reference checks), designed for TDD. See
  [`tests/pipeline/README.md`](pipeline/README.md#pipeline-checks) for the full guide.

### Utilities

- **`test_ThrottledRequester.py`** (`unit`) — Tests the `ThrottledRequester` HTTP client,
  verifying that rate-limiting delays are correctly applied between requests.
  Uses a local HTTP server, so no network access is required.

- **`test_ftp.py`** (`network`) — Tests FTP download utilities (`pull_via_ftp`) against the
  NCBI FTP server. Covers pulling plain text and gzipped files to memory or disk
  with optional decompression. Requires `--network` to run.

- **`test_uber.py`** (`network`, `xfail`) — Tests the `UberGraph` class for querying ontology
  subclasses and cross-references via SPARQL. Covers direct and indirect subclass retrieval,
  filtering by cross-reference presence, and exact-match label queries.

## Test Data

The `tests/data` directory contains fixture files used by several tests:

- `gptest_Gene.txt` — Sample gene compendium for gene-protein conflation tests
- `gptest_Protein.txt` — Sample protein compendium
- `gp_UniProtNCBI.txt` — Sample UniProt-NCBI concordance

## Future Plans

### Test infrastructure improvements

- **Bundle the Biolink Model locally** — The `node_factory` fixture calls `bmt.Toolkit`, which
  fetches `biolink-model.yaml` and `predicate_mapping.yaml` from GitHub on first use. Shipping a
  pinned copy of those files with the repo (or using VCR cassettes) would let all 13 tests in
  `test_node_factory.py` run offline and be re-marked `unit`.
- **`responses` / `pytest-httpserver`** — Use HTTP mocking to test `ThrottledRequester` and other
  HTTP-calling code without a live service. This would let `test_ThrottledRequester.py` be
  re-marked `unit` and become reliably deterministic.
- **`babel_config` conftest fixture** — A session fixture that patches `get_config()` to redirect
  `download_directory` and `output_directory` to `tmp_path`. Tests that exercise `create_node()`
  or other path-dependent code could use this instead of manually setting `common_labels = {}`.
- **VCR cassettes** — Record real HTTP/FTP responses for BioMart and UberGraph once, commit the
  cassette files, and replay them in CI. This would let `datahandlers/test_ensembl.py`,
  `test_chemicals.py`, and `test_uber.py` run offline and be promoted from `network + xfail` to
  `unit`.

### New `unit` test files (parsing transforms)

Create a `tests/fixtures/` directory with small golden files (10–20 rows each) per data handler,
then add offline parsing tests:

- **`tests/parsing/test_drugbank.py`** — `extract_drugbank_labels_and_synonyms` with a fixture CSV
- **`tests/parsing/test_ncbigene.py`** — `get_ncbigene_field` and `pull_ncbigene_labels` with a
  fixture `.gz` file
- **`tests/parsing/test_unii.py`** — `write_unii_ids` with a small fixture TSV
- **`tests/parsing/test_mesh.py`** — Mesh SPARQL methods with a fixture `.nt` RDF file

### New `unit` test files (babel_utils and TSVSQLiteLoader)

- **`tests/test_babel_utils.py`** — Cover `sort_identifiers_with_boosted_prefixes()`,
  `get_numerical_curie_suffix()`, `clean_sets()`, `get_prefixes()`, and
  `filter_out_non_unique_ids()`
- **`tests/test_tsvsqliteloader.py`** — Load a small fixture TSV into `TSVSQLiteLoader`, run
  `get_curies()` queries, verify case-insensitive lookups and missing-key handling

### New `unit` test files (compendium transforms)

- **`tests/compendium/test_chemicals_ids.py`** — `write_umls_ids`, `write_unii_ids`,
  `get_type_from_smiles`
- **`tests/compendium/test_gene_ids.py`** — `build_gene_ensembl_relationships` with a fixture
  BioMart TSV
- **`tests/compendium/test_make_cliques.py`** — `get_conflation_ids` parsing logic

See [`tests/pipeline/README.md`](pipeline/README.md#future-plans) for planned pipeline and ETL
test additions.

### Deduplication / cleanup

- Move `test_geneproteiny.py` assertions to also check individual clique contents, not just that
  the output file is non-empty.
