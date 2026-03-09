# Test Suite

## Running Tests

```bash
PYTHONPATH=. uv run pytest                           # All tests (with coverage)
PYTHONPATH=. uv run pytest --no-cov                  # Without coverage (faster)
PYTHONPATH=. uv run pytest tests/test_glom.py        # Single test file
```

Coverage reports are generated automatically: a summary prints in the terminal and a
browsable HTML report is written to `htmlcov/`.

## Mark Taxonomy

Tests are tagged with marks to control which subset runs in a given context:

| Mark | What it covers | Network? | Typical duration |
|------|---------------|----------|-----------------|
| `unit` | Pure functions, in-memory logic, small fixtures in `tests/testdata/` | No | Seconds |
| `network` | Requires live internet (FTP, SPARQL, BioMart, external APIs) | Yes | Seconds–minutes |
| `slow` | Correct but takes >30s — large fixture processing, SQLite spill, etc. | Sometimes | >30s |
| `pipeline` | Invokes Snakemake rules; requires `babel_downloads/` to be pre-populated | Yes | Minutes–hours |

### Default behavior

- `pytest` alone: runs `unit` and `slow` tests; skips `network` and `pipeline`
- `pytest --network`: also runs `network` tests
- `pytest --pipeline`: also runs `pipeline` tests (ensure `babel_downloads/` exists first)

### Convenience commands

```bash
PYTHONPATH=. uv run pytest -m unit                        # unit tests only (CI default)
PYTHONPATH=. uv run pytest -m "unit or network" --network # unit + live-service checks
PYTHONPATH=. uv run pytest -m "unit or slow"              # unit + slow offline tests
PYTHONPATH=. uv run pytest -m pipeline --pipeline -x     # one Snakemake-triggering test at a time
PYTHONPATH=. uv run pytest -m "not pipeline"              # everything except full pipeline runs
```

## Test Files

### Core

- **`test_node_factory.py`** (`unit`) — Tests `NodeFactory`, the central class for building
  normalized nodes. Covers ancestor retrieval, prefix ordering, identifier
  normalization (selecting the best CURIE from an equivalence set), label
  application, UMLS filtering, PubChem disambiguation, and deduplication of
  `LabeledID` objects. Uses fixture data from `testdata/`.

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

- **`test_chemicals.py`** / **`test_uber.py`** (`network`, `xfail`) — Both test the
  `UberGraph` class for querying ontology subclasses and cross-references via SPARQL.
  Cover direct and indirect subclass retrieval, filtering by cross-reference presence,
  and exact-match label queries. (These two files are currently identical.)

- **`test_geneproteiny.py`** (`unit`) — Integration test for gene-protein conflation. Runs
  `build_compendium` with gene and protein compendia plus a concordance file from
  `testdata/` and verifies output is produced.

### Utilities

- **`test_ftp.py`** (`network`) — Tests FTP download utilities (`pull_via_ftp`) against the
  NCBI FTP server. Covers pulling plain text and gzipped files to memory or disk
  with optional decompression. Requires `--network` to run.

- **`test_ThrottledRequester.py`** (`network`) — Tests the `ThrottledRequester` HTTP client,
  verifying that rate-limiting delays are correctly applied between requests.
  Requires `--network` to run.

## Test Data

The `testdata/` directory contains fixture files used by several tests:

- `gptest_Gene.txt` — Sample gene compendium for gene-protein conflation tests
- `gptest_Protein.txt` — Sample protein compendium
- `gp_UniProtNCBI.txt` — Sample UniProt-NCBI concordance
