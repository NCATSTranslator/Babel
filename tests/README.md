# Test Suite

## Running Tests

```bash
PYTHONPATH=. uv run pytest                           # All tests (with coverage)
PYTHONPATH=. uv run pytest --no-cov                  # Without coverage (faster)
PYTHONPATH=. uv run pytest tests/test_glom.py        # Single test file
```

Coverage reports are generated automatically: a summary prints in the terminal and a
browsable HTML report is written to `htmlcov/`.

Not all tests currently pass (see issue #602).

## Test Files

### Core

- **`test_node_factory.py`** -- Tests `NodeFactory`, the central class for building
  normalized nodes. Covers ancestor retrieval, prefix ordering, identifier
  normalization (selecting the best CURIE from an equivalence set), label
  application, UMLS filtering, PubChem disambiguation, and deduplication of
  `LabeledID` objects. Uses fixture data from `testdata/`.

- **`test_glom.py`** -- Tests the `glom` utility, which merges pairwise identifier
  sets into equivalence cliques (union-find). Covers basic merging, iterative
  multi-call usage, tuple vs. set inputs, and the expected `ValueError` when sets
  contain more than two members.

- **`test_LabeledID.py`** -- Tests that `LabeledID` objects (a CURIE paired with a
  human-readable label) compare correctly against bare strings and behave properly
  in sets.

### Data Handlers

- **`datahandlers/test_ensembl.py`** -- Integration test for the Ensembl BioMart
  data handler. Pulls real data from BioMart, verifies that batched downloads
  (splitting attribute lists across multiple queries) produce the same results as
  single-query downloads, and checks TSV output correctness. Uses `tmp_path`.

### Compendia

- **`test_chemicals.py`** / **`test_uber.py`** -- Both test the `UberGraph` class
  for querying ontology subclasses and cross-references via SPARQL. Cover direct and
  indirect subclass retrieval, filtering by cross-reference presence, and exact-match
  label queries. (These two files are currently identical.)

- **`test_geneproteiny.py`** -- Integration test for gene-protein conflation. Runs
  `build_compendium` with gene and protein compendia plus a concordance file from
  `testdata/` and verifies output is produced.

### Utilities

- **`test_ftp.py`** -- Tests FTP download utilities (`pull_via_ftp`) against the
  NCBI FTP server. Covers pulling plain text and gzipped files to memory or disk
  with optional decompression. All tests are marked `@pytest.mark.ftp` (they
  require network access and may not work in all CI environments).

- **`test_ThrottledRequester.py`** -- Tests the `ThrottledRequester` HTTP client,
  verifying that rate-limiting delays are correctly applied between requests.

## Test Data

The `testdata/` directory contains fixture files used by several tests:

- `gptest_Gene.txt` -- Sample gene compendium for gene-protein conflation tests
- `gptest_Protein.txt` -- Sample protein compendium
- `gp_UniProtNCBI.txt` -- Sample UniProt-NCBI concordance
