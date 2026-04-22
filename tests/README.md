# Test Suite

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
- `pytest --pipeline --regenerate`: re-runs `write_X_ids()` even if intermediate files already
  exist (useful after changing compendium filtering logic; see **Caching** below)
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

- **`datahandlers/test_mesh.py`** (`unit`) — Unit tests for `src/datahandlers/mesh.py`.
  Covers `write_ids()` parameter validation, SCR filtering logic (mock-based), and
  `Mesh.get_scr_terms_mapped_to_trees()` using an inline pyoxigraph store.

### Pipeline

#### Caching of intermediate files

Processing fixtures write intermediate ID files to the exact paths Snakemake uses:

```text
babel_outputs/intermediate/{semantic_type}/ids/{vocab}
```

For example, `anatomy.write_umls_ids()` writes to
`babel_outputs/intermediate/anatomy/ids/UMLS`. By default, if that file already
exists it is reused — `write_umls_ids()` is not called again. This means:

- **Second and later runs are fast** — only the test assertions execute.

- **A prior full Snakemake pipeline run can be reused directly** — the test fixtures
  will pick up any files Snakemake already produced.

- **To force re-processing**, pass `--regenerate`:

  ```bash
  uv run pytest tests/pipeline/ --pipeline --regenerate --no-cov -v
  ```

- **To selectively regenerate one vocabulary**, delete its files manually then run
  without `--regenerate`:

  ```bash
  rm babel_outputs/intermediate/*/ids/UMLS
  uv run pytest tests/pipeline/ --pipeline --no-cov -v -k UMLS
  ```

- **`pipeline/test_vocabulary_partitioning.py`** (`pipeline`) — Generic mutual-exclusivity
  tests parametrized over all registered vocabularies. For each vocabulary, verifies that
  (1) every compendium's `write_X_ids()` produces non-empty output and (2) no identifier
  appears in more than one compendium. Currently covers five vocabularies: MESH (5
  compendia), UMLS (7 compendia), OMIM (2 compendia), NCIT (2 compendia via UberGraph),
  GO (2 compendia via UberGraph). Adding a new vocabulary requires only adding its fixtures
  to `conftest.py` and one entry in `VOCABULARY_REGISTRY` — this file never changes.

- **`pipeline/test_mesh_pipeline.py`** (`pipeline`) — MeSH-specific targeted test (issue
  #675). Downloads `babel_downloads/MESH/mesh.nt` automatically if absent. One test:
  chemicals output must exclude all D05/D08/D12.776 descriptor terms, including
  "in-neither" subtrees like Polymers and Coenzymes, even though these are not captured
  by `protein.write_mesh_ids()`.

- **`pipeline/test_umls_pipeline.py`** (`pipeline`) — UMLS-specific targeted test. Requires
  `UMLS_API_KEY` for the initial download (or cached files). One test: chemicals must not
  contain any UMLS IDs that the protein compendium claimed (semantic type tree
  A1.4.1.2.1.7, Amino Acid/Peptide/Protein).

- **`pipeline/checks/`** (`pipeline`) — Regression checks sourced from GitHub issues,
  designed for test-driven development. See [Pipeline Checks](#pipeline-checks) below.

### Pipeline Checks

`tests/pipeline/checks/` contains per-compendium regression assertion files driven by
specific GitHub issues. They are intended for TDD: add a failing check, run the pipeline,
iterate on source code until the check passes.

Two kinds of assertions are supported in each file:

**ID-presence checks** (`EXPECTED_IN_CHEMICALS` / `NOT_IN_CHEMICALS`)

Verify that a specific CURIE appears in (or is absent from) the intermediate ID file for a
compendium. These only require `write_*_ids()` to have run — no Snakemake needed. They
depend on the existing vocab fixtures (`mesh_pipeline_outputs`, `umls_pipeline_outputs`, …).

The `expected_type` field documents the Biolink type; it is also asserted against the second
column of the intermediate file if the vocabulary writes type hints (e.g. UMLS does; MESH
does not).

**Direct cross-reference checks** (`EXPECTED_XREF` / `EXPECTED_NO_XREF`)

Verify that two CURIEs are (or are not) a direct xref pair in any concord file for the
compendium. These depend on `chemicals_concords_dir` (or the equivalent fixture for another
compendium), which runs `snakemake --until get_chemical_wikipedia_relationships` if needed.

**Scope limitation**: only *direct* xref pairs are checked. Indirect equivalences through
multi-hop chains are not detected. This is intentional — it is fast enough for TDD and
locates the concord file that is the root cause of a bad link.

**Adding a new check** — append one tuple to the appropriate list in
`tests/pipeline/checks/test_chemicals.py` (or add a new `test_X.py` file for another
compendium):

```python
# ID-presence check (MESH, no Snakemake required):
ChemCheck(
    "mesh_pipeline_outputs",
    "MESH:C000001",
    "biolink:ChemicalEntity",
    "https://github.com/NCATSTranslator/Babel/issues/NNN",
),

# Direct-xref check (requires concords to be generated):
ConcordCheck(
    "chemicals_concords_dir",
    "MESH:C000001",
    "CHEBI:12345",
    False,   # False = must NOT be a direct xref
    "https://github.com/NCATSTranslator/Babel/issues/NNN",
),
```

**Adding a new vocabulary** — change the `fixture` field to the appropriate session fixture
name (e.g. `"umls_pipeline_outputs"` for UMLS ID checks). For a new compendium's concord
checks, add a `my_compendium_concords_dir` fixture to `conftest.py` following the
`chemicals_concords_dir` pattern, using the appropriate Snakemake sentinel rule.

```bash
# Run all checks:
uv run pytest tests/pipeline/checks/ --pipeline --no-cov -v

# Run only ID-presence checks (fast):
uv run pytest tests/pipeline/checks/ -k "in_chemicals or not_in_chemicals" --pipeline --no-cov -v

# Run only direct-xref checks:
uv run pytest tests/pipeline/checks/ -k "xref" --pipeline --no-cov -v
```

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

- **`test_ThrottledRequester.py`** (`unit`) — Tests the `ThrottledRequester` HTTP client,
  verifying that rate-limiting delays are correctly applied between requests.
  Uses a local HTTP server, so no network access is required.

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

The vocabulary-partitioning framework in `tests/pipeline/conftest.py` makes adding
new multi-compendium vocabularies straightforward. Each vocabulary needs:

1. A **download/connectivity fixture** in `conftest.py` — either a file download using
   `_download_or_skip`, a credential-checked download (like UMLS), or a network health
   check (like `ubergraph_connection` for NCIT/GO).

2. A **processing fixture** in `conftest.py` that calls all `write_X_ids()` functions for
   that vocabulary and returns a `{compendium_name: output_path}` dict.

3. **One line** in `VOCABULARY_REGISTRY`: `"MYVOCAB": "my_vocab_pipeline_outputs"`.

No new test file is needed for the standard non-empty and mutual-exclusivity checks —
`test_vocabulary_partitioning.py` picks them up automatically. Add a
`test_X_pipeline.py` only for vocabulary-specific targeted assertions.

Vocabularies not yet covered (candidates):

- **ENSEMBL** — appears in protein (`write_ensembl_protein_ids`) and gene
  (`write_ensembl_gene_ids`). Deferred because the download uses BioMart
  (`pull_ensembl(ensembl_dir, complete_file, ...)`) which is more complex to invoke
  outside Snakemake.
- **NCBI Gene / HGNC / other single-source** — vocabularies that appear in only one
  compendium don't need mutual-exclusivity tests, but could still get non-empty checks
  in a per-compendium ETL test (see "New `network + slow` ETL tests" above).

### Deduplication / cleanup

- Move `test_geneproteiny.py` assertions to also check individual clique contents, not just that
  the output file is non-empty.

## Out of Scope / Pipeline-only

The pipeline tests live in `tests/pipeline/`. See the "Pipeline" subsection of "Test Files"
and "New pipeline tests" in Future Plans for the current coverage and how to extend it.

Run them with:

```bash
uv run pytest tests/pipeline/test_mesh_pipeline.py --pipeline --no-cov -v
```
