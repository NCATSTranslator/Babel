# Test Suite

## Running Tests

```bash
PYTHONPATH=. uv run pytest                           # All tests
PYTHONPATH=. uv run pytest --cov=src                 # With coverage report
PYTHONPATH=. uv run pytest tests/test_glom.py        # Single test file
```

Coverage is opt-in: pass `--cov=src` (or `--cov=src --cov-report=html`) to generate
a report. Coverage configuration is in `pyproject.toml` under `[tool.coverage.*]`.

## Mark Taxonomy

Tests are tagged with marks to control which subset runs in a given context:

| Mark       | What it covers                                                           | Network?  | Typical duration | Timeout |
|------------|--------------------------------------------------------------------------|-----------|------------------|---------|
| `unit`     | Pure functions, in-memory logic, small fixtures in `tests/data/`         | No        | Seconds          | 30 s    |
| `network`  | Requires live internet (FTP, SPARQL, BioMart, external APIs)             | Yes       | Seconds–minutes  | 600 s   |
| `slow`     | Correct but takes >30s — large fixture processing, SQLite spill, etc.    | Sometimes | >30s             | 600 s   |
| `pipeline` | Invokes Snakemake rules; requires `babel_downloads/` to be pre-populated | Yes       | Minutes–hours    | 3600 s  |

### Default behavior

- `pytest` alone: runs `unit` and `slow` tests; skips `network` and `pipeline`
- `pytest --network`: also runs `network` tests
- `pytest --pipeline`: also runs `pipeline` tests (ensure `babel_downloads/` exists first)
- `pytest --all`: runs everything (equivalent to `--network --pipeline`)

### Convenience commands

```bash
PYTHONPATH=. uv run pytest -m unit                        # unit tests only (CI default)
PYTHONPATH=. uv run pytest -m "unit or network" --network # unit + live-service checks
PYTHONPATH=. uv run pytest -m "unit or slow"              # unit + slow offline tests
PYTHONPATH=. uv run pytest --all                          # run every test
PYTHONPATH=. uv run pytest -m pipeline --pipeline -x     # one Snakemake-triggering test at a time
PYTHONPATH=. uv run pytest -m "not pipeline"              # everything except full pipeline runs
PYTHONPATH=. uv run pytest -n auto --no-cov               # parallel (all CPUs), skip coverage
PYTHONPATH=. uv run pytest -n 4 -m unit                  # 4 workers, unit tests only
```

## Test Files

### Core

- **`test_node_factory.py`** (`network`) — Tests `NodeFactory`, the central class for building
  normalized nodes. Covers ancestor retrieval, prefix ordering, identifier
  normalization (selecting the best CURIE from an equivalence set), label
  application, UMLS filtering, PubChem disambiguation, and deduplication of
  `LabeledID` objects. Marked `network` because the `node_factory` fixture calls
  `bmt.Toolkit`, which fetches `biolink-model.yaml` and `predicate_mapping.yaml`
  from GitHub on first use.

- **`test_glom.py`** (`unit`) — Tests the `glom` utility, which merges pairwise identifier
  sets into equivalence cliques (union-find). Covers basic merging, iterative
  multi-call usage, tuple vs. set inputs, and the expected `ValueError` when sets
  contain more than two members.

- **`test_LabeledID.py`** (`unit`) — Tests that `LabeledID` objects (a CURIE paired with a
  human-readable label) compare correctly against bare strings and behave properly
  in sets.

### Data Handlers

- **`datahandlers/test_ensembl.py`** (`network`, `xfail`) — Integration test for the Ensembl
  BioMart data handler. Pulls real data from BioMart, verifies that batched downloads
  (splitting attribute lists across multiple queries) produce the same results as
  single-query downloads, and checks TSV output correctness. Uses `tmp_path`.

### Compendia

- **`test_uber.py`** (`network`, `xfail`) — Tests the
  `UberGraph` class for querying ontology subclasses and cross-references via SPARQL.
  Covers direct and indirect subclass retrieval, filtering by cross-reference presence,
  and exact-match label queries.

- **`test_geneproteiny.py`** (`unit`) — Integration test for gene-protein conflation. Runs
  `build_compendium` with gene and protein compendia plus a concordance file from
  `data/` and verifies output is produced.

### Utilities

- **`test_ftp.py`** (`network`) — Tests FTP download utilities (`pull_via_ftp`) against the
  NCBI FTP server. Covers pulling plain text and gzipped files to memory or disk
  with optional decompression. Requires `--network` to run.

- **`test_ThrottledRequester.py`** (`network`) — Tests the `ThrottledRequester` HTTP client,
  verifying that rate-limiting delays are correctly applied between requests.
  Requires `--network` to run.

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

### New `network + slow` ETL tests

Add a `tests/etl/` sub-package with a shared `conftest.py` that provides an `etl_output_dir`
fixture (`tmp_path_factory`). Each file downloads and parses one data handler end-to-end and
asserts the output file is non-empty:

- `test_etl_ncbigene.py`, `test_etl_chebi.py`, `test_etl_mesh.py`, `test_etl_ensembl.py`, …

### New `pipeline` tests

Add a `tests/pipeline/` sub-package with a `snakemake_rule` session fixture (calls the Snakemake
Python API, inherits dependency resolution, returns the output directory). Requires
`babel_downloads/` to be pre-populated — document this in `tests/pipeline/README.md`.

Example tests:

- **`test_pipeline_chemical.py`** — Runs `chemical_umls_ids` rule, checks output file exists and
  is non-empty
- **`test_pipeline_gene.py`** — Runs the gene sub-pipeline, checks `NCBIGene.txt` compendium

### Deduplication / cleanup

- `test_chemicals.py` and `test_uber.py` are currently identical. Consolidate into one file or
  give each a distinct focus (e.g. chemicals-specific SPARQL queries vs. general UberGraph
  behaviour).
- Move `test_geneproteiny.py` assertions to also check individual clique contents, not just that
  the output file is non-empty.
