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
uv run pytest                           # All tests
uv run pytest --cov=src                 # With coverage report
uv run pytest tests/test_node_factory.py  # Single test file
uv run pytest -m unit -q               # Unit tests only (CI default)
uv run pytest --network                # Include network tests
uv run pytest --all                    # Run every test
uv run pytest -n auto                  # Parallel (all CPUs)
```

Tests use four marks: `unit` (fast, offline), `network` (requires internet, opt-in with
`--network`), `slow` (>30s but offline), and `pipeline` (invokes Snakemake, opt-in with
`--pipeline`). Use `--all` to opt in to everything at once. Network and pipeline tests are
skipped by default. See `tests/README.md` for the full taxonomy.

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
- `compendium_directories` in `config.yaml` maps Python compendium names to the Snakemake
  intermediate directory names when they differ (e.g., `diseasephenotype → disease`,
  `processactivitypathway → process`). Update this when adding a new semantic type whose
  directory name doesn't match its Python module name.

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

- **`datahandlers/`** — ~35 modules, each wrapping a specific external data source (ChEBI, UniProt,
  NCBI Gene, DrugBank, MESH, etc.). These download, parse, and normalize source data.
- **`createcompendia/`** — ~16 modules, one per semantic type (chemicals, genes, proteins, anatomy,
  disease/phenotype, etc.). These consume data handler outputs and build concords → cliques.
- **`snakefiles/`** — Snakemake rule definitions wiring data handlers to compendium creators.
- **`node.py`** — Core classes: `NodeFactory`, `SynonymFactory`, `DescriptionFactory`,
  `TaxonFactory`, `InformationContentFactory`, `TSVSQLiteLoader`.
- **`babel_utils.py`** — Download/FTP utilities, `glom()` (clique merging), `write_compendium()`
  (compendium builder), state management.
- **`util.py`** — Logging, config loading, Biolink Model Toolkit (bmt) access.
- **`exporters/`** — Output format handlers (KGX, Parquet, JSONL).
- **`reports/`**, **`synonyms/`**, **`metadata/`** — Report generation, synonym files, provenance.

### Key Patterns

- **Factory pattern** for lazy-loading large datasets (`NodeFactory`, `SynonymFactory`, etc.).
- **`TSVSQLiteLoader`** creates in-memory SQLite databases that spill to disk, avoiding full RAM
  loading of large TSV files.
- **Biolink Model** integration via `bmt` — types, valid prefixes, and naming conventions all follow
  the Biolink Model.
- **Concord files** are the core data structure: tab-separated `CURIE1 \t Relation \t CURIE2`
  triples expressing cross-references between vocabularies. The `glom()` function in
  `babel_utils.py` merges them into equivalence cliques.

### Biolink Model Usage

The Biolink Model version is set in `config.yaml` (`biolink_version: "4.3.6"`) and is the single
source of truth used by `NodeFactory` and `get_biolink_model_toolkit()`. The model is fetched from
GitHub on first use (bmt may cache it locally).

**Mapped class URIs** — always use the `biolink:`-prefixed form (e.g. `biolink:ChemicalEntity`),
not the raw element name (`chemical entity`). `get_ancestors()` and `get_element()["class_uri"]`
return these mapped forms.

**Prefix ordering** — `src/prefixes.py` is the canonical registry of prefix string constants. The
order of `id_prefixes` in the Biolink Model determines which CURIE is selected as the preferred
identifier by `NodeFactory`. In biolink 4.3.6, for example, `CHEBI` ranks above `PUBCHEM.COMPOUND`
for `biolink:SmallMolecule`. Update `src/prefixes.py` whenever new prefixes appear in the model.

**Node output schema** — `NodeFactory.create_node()` returns:

```python
{"identifiers": [{"identifier": CURIE, "label": str}, ...], "type": "biolink:Foo", "id": {"identifier": CURIE, "label": str}}
```

`identifiers[0]` is the preferred identifier (highest-priority prefix); `id` is an alias for
`identifiers[0]`. Labels remain on the identifier that owns them and are not promoted to the first
entry.

### Conflation

GeneProtein and DrugChemical conflation each have dedicated conflation modules (`geneprotein.py`,
`drugchemical.py`) that merge their respective cliques. See `docs/Conflation.md`.

### Directories at Runtime

- `babel_downloads/` — cached source data
- `babel_outputs/intermediate/` — intermediate build artifacts
- `babel_outputs/` — final compendia, synonyms, reports, exports

## Running Babel

You may run `uv run snakemake -c all --rerun-incomplete [rulename]` to run a particular rule.
When running a download step, it will be easier to run the job in Snakemake, but when running
a rule that produces intermediate files, it might be easier to download the intermediate files from
<https://stars.renci.org/var/babel/2025dec11/> (which is the `babel_output` folder from a run on a
high performance cluster) so you don't need to download all the source files and
rerun the entire pipeline. You can look at the resource requirements of a rule to decide which
option would be best.

## Conventions

- **Error handling** — raise exceptions (`RuntimeError`, `ValueError`, etc.) rather than
  `print(...) + exit(1)`. Exceptions are testable and propagate cleanly through Snakemake;
  bare `exit()` calls bypass Python's exception machinery and make unit testing impossible.

- **Biolink class references** — always use the named constants from `src/categories.py`
  (e.g. `CHEMICAL_ENTITY`, `DRUG`) rather than hardcoding `"biolink:..."` strings directly.
  This ensures that a Biolink class rename only requires updating `src/categories.py`.
  If a needed constant is missing from `categories.py`, add it there first.

- **IRI parsing helpers** — functions that extract IDs from external-format strings (e.g.
  pyoxigraph IRIs, SPARQL results) must validate the input format and raise `ValueError` if
  it doesn't match. Use a named prefix constant so the check and the extraction share the
  same string. Example pattern from `src/datahandlers/mesh.py`:

  ```python
  _MESH_IRI_PREFIX = "<http://id.nlm.nih.gov/mesh/"

  def _mesh_id(iri) -> str:
      s = str(iri)
      if not s.startswith(_MESH_IRI_PREFIX) or not s.endswith(">"):
          raise ValueError(f"Expected a MeSH IRI, got: {s!r}")
      return s[len(_MESH_IRI_PREFIX):-1]
  ```

## Debugging

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

## Documentation

When making a significant change, check if it affects any of the documentation
files (`docs/*.md`, `*.md`) and update them if necessary. Suggest adding
new documentation files if necessary.

When writing documentation files, avoid using horizontal pipes unless necessary --
section headings are sufficient for dividing up documentation.
