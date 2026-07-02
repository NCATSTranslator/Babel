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

Tests use four marks: `unit` (fast, offline), `network` (requires internet, opt-in with
`--network`), `slow` (>30s but offline), and `pipeline` (invokes Snakemake, opt-in with
`--pipeline`). Use `--all` to opt in to everything at once. Network and pipeline tests are
skipped by default.

Memory-hungry tests also carry a parametrized `min_memory_gb(n)` guard (registered in
`pyproject.toml`, enforced in `tests/conftest.py`) that auto-skips them on machines with less
than `n` GiB of RAM. For example the ChEMBL pipeline tests bulk-load a ~16 GB TTL into an
in-memory `pyoxigraph.Store` and need ~120–150 GiB — far more than the on-disk size, because an
indexed in-memory triple store expands roughly 8–10×. To size a new rule's `mem=` resource or a
test's `min_memory_gb` threshold empirically, use `tools/memory/estimate_rdf_load_memory.py` (see
`tools/memory/README.md`): it streams an RDF dump into a store, samples RSS, and extrapolates the
full-load peak, so it works even on a machine far smaller than the eventual requirement (most
accurate on Linux — macOS memory compression understates the result).

- `tests/README.md` — full mark taxonomy, where to add a new test, what each test file covers.
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

### Pipeline Orchestration

Snakemake drives a two-phase pipeline:

1. **Data Collection** — downloads from FTP/web sources, producing per-source attribute files in
   `babel_downloads/[PREFIX]/` that the factories in `node.py` pick up by prefix. Each is an
   independent, optional TSV: `labels` (CURIE→name, read by `NodeFactory`), `synonyms`
   (CURIE→predicate→synonym, `SynonymFactory`), `taxa` (CURIE→`NCBITaxon:NNNN`, `TaxonFactory`),
   and `descriptions` (CURIE→text, `DescriptionFactory`). A handler emits whichever of these its
   source supports; supplying `taxa`/`descriptions` is how a source enriches its cliques with
   taxon and description data (see ComplexPortal and NCBIGene for examples that emit all four).
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
- **`SynonymFilter`** (`src/synonyms/filter.py`) checks every label and synonym against
  `input_data/obsolete_synonyms.yaml` before it enters a compendium. Each YAML entry
  carries its own `action` field: `"remove"` (default) drops the term and returns `True`
  from `should_suppress()`; `"warn"` logs a warning but keeps the term and returns
  `False`. When calling `should_suppress()`, always pass the full Biolink ancestor chain
  via `NodeFactory.get_ancestors(node_type)` as `node_types` — passing only `[node_type]`
  breaks type-scoped filter entries that match on a parent type.
- **Logging** — always use `get_logger(__name__)` from `src.util` (never
  `logging.getLogger` directly). `get_logger` installs the shared stderr handler and
  formatter that Snakemake captures; bare `logging.getLogger` loggers may produce
  unformatted output if called before any other module has triggered `get_logger`. In
  modules that sit early in the import graph and must defer `src.util` to avoid
  triggering config loading at import time (see `src/synonyms/filter.py`), reassign the
  module-level `logger` inside the deferred-import block rather than at module scope.

### Biolink Model Usage

The Biolink Model version is set in `config.yaml` (the current value is the source of
truth — read it via `get_config()["biolink_version"]` rather than hard-coding a version
in code or in docs that will go stale) and feeds both `NodeFactory` and
`get_biolink_model_toolkit()`.

**Mapped class URIs** — always use the `biolink:`-prefixed form (e.g. `biolink:ChemicalEntity`),
not the raw element name (`chemical entity`). `get_ancestors()` and `get_element().class_uri`
return these mapped forms. Note that `get_element()` returns a bmt `ClassDefinition`
object (a `linkml_runtime` model), not a plain dict. It supports both attribute access
(`element.id_prefixes`, `element.class_uri`) and subscript access (`element["id_prefixes"]`,
which `src/node.py:get_prefixes()` uses), but it has no `dict`-style `.get()` method, so
`element.get("id_prefixes")` raises `AttributeError`. Prefer attribute access (or a plain
`getattr(element, "id_prefixes", default)`) and never reach for `.get()`.

**OBO PURL resolution** — `src/util.py:get_biolink_prefix_map()` returns a
`curies.Converter` built from the Biolink prefix map for the configured Biolink version;
use `converter.expand("EMAPA:0")` to turn a CURIE into its IRI. Prefer that helper over
fetching the prefix map yourself.

**Prefix ordering** — `src/prefixes.py` is the canonical registry of prefix string constants. The
order of `id_prefixes` in the Biolink Model determines which CURIE is selected as the preferred
identifier by `NodeFactory`. Update `src/prefixes.py` whenever new prefixes appear in the model.

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

### Leftover UMLS

`src/createcompendia/leftover_umls.py` (rule `leftover_umls`) runs last and sweeps up every valid
UMLS concept in MRCONSO that no other compendium already claimed, writing each as a
single-identifier clique into `compendia/umls.txt` so its label is still available downstream. The
Biolink type for each leftover concept comes from its UMLS semantic type(s) via
`tui_to_biolink_type()` (the bmt `STY:<code>` mapping), corrected by two manual tables at the top of
the module: `STY_OVERRIDES` (per-semantic-type override; `None` means reject) and
`TYPE_COMBO_OVERRIDES` (disambiguates a concept that resolves to multiple Biolink types). These
tables exist because the long-term fix belongs in the Biolink Model but its real-world effect on
Babel is hard to predict; each entry cites a GitHub issue.
`tests/createcompendia/test_leftover_umls.py` records the current Biolink mapping for each override
and flags when one drifts or becomes redundant. The rule also emits coverage CSVs under
`babel_outputs/reports/umls/`. See `docs/sources/UMLS/Leftover.md`.

### DuckDB export

The `src/snakefiles/duckdb.snakefile` rules (driven by `src/exporters/duckdb_exporters.py`)
build a queryable DuckDB database alongside the JSONL compendia, with these tables:

- `Node(curie, curie_prefix, label, label_lc, description, taxa)`
- `Clique(clique_leader, preferred_name, clique_identifier_count, biolink_type, information_content)`
- `Edge(clique_leader, curie, conflation, clique_leader_prefix, curie_prefix, biolink_type)`
- `Conflation(conflation_type, conflation_leader, curie, curie_prefix)`

The `Edge` table answers "which clique contains CURIE X" with a one-line query
(`SELECT DISTINCT clique_leader FROM Edge WHERE curie IN (...)`) and is the fastest way to
check whether several CURIEs landed in the same clique in a given build — much cheaper than
re-running glom or scanning the JSONL compendia. `biolink_type` is denormalized onto every edge
(it equals the owning clique's type) so cross-compendium reports can group by
`(curie_prefix, biolink_type)` with a plain scan instead of a large Edge-to-Clique join, which
OOM-killed `generate_curie_report` even on a largemem node.

### Per-source documentation (`docs/sources/`)

Deeper, source-specific notes live under `docs/sources/<PREFIX>/` (one directory per data source,
named by its CURIE prefix); see `docs/sources/README.md` for the convention and an index. Check
there first when working on a specific vocabulary, and add to it when you learn something
non-obvious about how Babel ingests that source. Keep the detail in the source file — `CLAUDE.md`
should point here, not duplicate it. Documented so far: ComplexPortal
(`docs/sources/COMPLEXPORTAL/Ingestion.md`), Ensembl/BioMart
(`docs/sources/ENSEMBL/Download.md`), MeSH (`docs/sources/MESH/Ingestion.md`), and UMLS
(`docs/sources/UMLS/Leftover.md`). Cross-cutting download/discovery patterns (HTTP autoindex
listing vs FTP `NLST`) live in `docs/sources/DownloadPatterns.md`.

### Per-compendium metadata YAMLs

Each final compendium has a sibling `babel_outputs/metadata/<Type>.yaml` that records the
provenance tree of which concord/source contributed what, including per-source
`prefix_counts` like `xref(CHEBI, DrugCentral): 4302`. These are aggregate (prefix-pair
level), not per-CURIE — useful for confirming a join pathway exists between two prefixes,
not for answering "are *these specific* CURIEs joinable."

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

If a previous Snakemake run was killed, the next invocation may fail with
`LockException: Directory cannot be locked`. Clear it with `uv run snakemake --unlock` before
retrying.

Most semantic-type targets are individually much cheaper than the full pipeline — anatomy in
particular builds end-to-end on a laptop in roughly 25 minutes wall time (UMLS download
dominates). The 500 GB figure in the README applies to the heaviest builds (protein,
drugchemical-conflated, and the full pipeline), not to every target. `docs/RunningBabel.md`
has a per-target sizing breakdown and a "Common build issues" section.

## Adding a new data source

`docs/AddingNewSources.md` is the full guide: how to wire a source (prefix, data handler,
compendium hook, Snakemake rules, `config.yaml`, docs, tests), then generate and read its
source-impact report — including assembling the intermediate inputs from a `stars.renci.org`
snapshot when a full local build (~500 GB RAM) is impractical. Two things to get right that
the report exists to catch:

- **Type every ids file.** Each ids row should carry a presumptive Biolink Type in column 2
  (`CURIE\tbiolink:Type`); this drives clique typing in the build. `write_compendium()` →
  `NodeFactory.create_node()` then keeps only CURIEs whose prefix is in the Biolink Model's
  `id_prefixes` for the clique's class and silently drops the rest — so a prefix that is not
  yet registered for its type never reaches the compendium. EMAPA's
  `biolink:GrossAnatomicalStructure` terms are the current not-yet-registered example.
- **Generate and commit the report.** `uv run source-impact-report --source <SOURCE>` writes
  `docs/sources/<SOURCE>/impact-report.md` plus an `impact-report/` subdirectory; commit
  `new-cliques.csv`, `modified-cliques.csv`, and `new-xrefs.tsv` (`modified-cliques.json` is
  gitignored). Its `would_be_added` / `needs_biolink_registration` columns flag identifiers
  the prefix filtering above would drop. When extending the report to a new semantic type,
  add a `compute_cliques_for_impact_report` helper to that type's `createcompendia/*.py`
  module (mirroring `anatomy.py`) and register it in `PIPELINE_CONFIG` in
  `src/cli/source_impact_report.py`.

**Snakemake `retries:`** — use `retries: 3` for any network-backed rule (UberGraph, FTP,
HTTP). Do not use `retries: 10`. UberGraph rules already get per-request retry-with-backoff
inside `TripleStore.execute_query` (default 3 attempts, exponential back-off, configurable
via `config["sparql"]["max_attempts"]`), so the Snakemake `retries:` is only a coarse
safety net for whole-rule failures, not a substitute for fine-grained request retries.

The shared clique-building skeleton lives in `src/model/cliques.py`.
`glom_from_files()` runs the common `load ids → glom`,
`load concords → filter → drop overused xrefs → glom` loop, parameterized by three hooks:
`concord_pair_filter` (per-pair keep/drop, with access to the clique state built so far),
`overused_xref_remover` (per-file `remove_overused_xrefs` variant), and `glom_kwargs`
(e.g. disease's `close={MONDO: ...}`). A type's `compute_cliques_for_impact_report` should
be a thin wrapper supplying that type's hooks, and its `build_compendia` should call the
same wrapper so the impact report's reglom provably matches the real build (anatomy does
this). If a compendium can't route its real build through the wrapper, add a test that
keeps the two clique computations in sync instead.

### Analyzing a SLURM run (`tools/slurm`)

`tools/slurm` analyzes a (possibly partial) Snakemake-on-SLURM run; see `docs/tools/README.md` and
the per-tool pages under `docs/tools/`. `uv run babel-slurm-errors <version>` (the successor to the
old `tools/babel-errors.py`) aggregates failing-rule logs and prints a
completed/failed/still-running job summary, to decide what to re-run.
`uv run babel-slurm-resources <run-dir>` joins actual usage (the `benchmark:` TSVs — authoritative,
since Hatteras `sacct` reports empty `MaxRSS`/`TotalCPU`) against requested resources and recommends
right-sized `mem`/`cpus`, flagging rules that need an explicit override before the cluster default
can be lowered. Both subcommands share `tools/slurm/parse.py`. Note that
`reports/slurm/slurm_efficiency_reports/` is a *directory* that accumulates one
`efficiency_report_<uuid>.csv` shard per Snakemake restart (each covering only that invocation's
jobs); the analyzer merges them all, so copy the whole directory when archiving a run.

## Conventions

When adding or enhancing a data source ingest, `docs/Development.md` ("Enhancing a data source
ingest") collects the process-level lessons (which attribute files to emit, IDs-file typing,
docstrings, and when to add a pipeline test) that the individual conventions below back up.

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

- **`babel_pipeline` vs `biolink_type`** — these two concepts are easy to confuse because the
  codebase (and this file) sometimes uses the vague phrase "semantic type" for either. Keep them
  distinct in code and variable names:
  - **`babel_pipeline`** is the pipeline directory name: `anatomy`, `chemical`, `diseasephenotype`,
    etc. It is a Babel artifact — an intermediate-file namespace, not a vocabulary term.
  - **`biolink_type`** is the Biolink class URI stored in compendia: `biolink:AnatomicalEntity`,
    `biolink:SmallMolecule`, etc. Multiple Biolink types can map to the same `babel_pipeline`
    (e.g. `anatomy` covers both `biolink:AnatomicalEntity` and `biolink:GrossAnatomicalStructure`).
  - **`umls_semantic_type`** (or `sty`) is yet a third thing: a UMLS TUI code / tree string used
    only inside the UMLS ingest. Do not conflate it with either of the above.
  Prefer these three explicit names in code. Avoid "semantic type" as a bare phrase unless quoting
  an external vocabulary (e.g. "UMLS semantic type").

- **Commits** — if you need to make a large change, break it into multiple commits so it's clearer
  what changes are related.

- **Separate download and extract/validate rules** — always split a Snakemake data-collection step
  into two rules: a `download_*` rule that only fetches the raw file(s), and a separate rule that
  validates format or extracts content. This way, if upstream changes its format (e.g. a column
  rename), only the validation rule fails; Snakemake preserves the downloaded file and the
  expensive re-download is avoided after a code fix. Format validation belongs in the
  extraction/filter rule, never in the download rule.

- **Ruff lint** — all Python must pass `uv run ruff check` (run automatically on PRs). Two rules
  that are easy to trip in test code:
  - **E741** — do not use single-letter ambiguous variable names (`l`, `O`, `I`). Use `line`,
    `row`, `col`, etc. instead.
  - **F841** — do not assign a variable that is never read. Remove or inline the assignment.

- **Imports** — place all imports at the top of the file (stdlib, then third-party, then local),
  following standard Python convention. Defer an import inside a function only when it is
  genuinely necessary to break a circular dependency or avoid a heavy optional dependency; if
  you do defer one, add a comment explaining why.

- **Error handling** — raise exceptions (`RuntimeError`, `ValueError`, etc.) rather than
  `print(...) + exit(1)`. Exceptions are testable and propagate cleanly through Snakemake;
  bare `exit()` calls bypass Python's exception machinery and make unit testing impossible.

- **Biolink class references** — always use the named constants from `src/categories.py`
  (e.g. `CHEMICAL_ENTITY`, `DRUG`) rather than hardcoding `"biolink:..."` strings directly.
  This ensures that a Biolink class rename only requires updating `src/categories.py`.
  If a needed constant is missing from `categories.py`, add it there first.

- **IRI parsing helpers** — functions that extract IDs from external-format strings (e.g. pyoxigraph
  IRIs, SPARQL results) must validate the input format and raise `ValueError` if it doesn't match.
  Use a named prefix constant so the check and the extraction share the same string. See
  `src/datahandlers/mesh.py:get_mesh_id_from_iri()` for the canonical example.

- **pyoxigraph literal stripping** — pyoxigraph returns plain string literals as `"value"` and
  language-tagged literals as `"value"@en`. Use `parse_rdf_literal()` from `src/babel_utils.py`
  to strip the quoting; do not inline the regex. When loading RDF/XML files that contain
  `<owl:Ontology rdf:about=""/>`, always pass `base_iri` to `Store.bulk_load()` — without it
  pyoxigraph raises a builtin `SyntaxError` on the empty relative IRI.

- **Datahandler file-path arguments** — label and synonym extraction functions should accept
  explicit `infile` / `outfile` path arguments rather than calling `make_local_name` internally.
  Explicit paths let unit tests pass `tmp_path`-based paths without patching the config, and
  let Snakemake rules declare inputs and outputs precisely.

- **Pin external column layouts in source, assert headers in tests** — when a handler parses a
  fixed-column TSV by index, define the column list as a module-level constant in the source
  (e.g. `complexportal.COMPLEXTAB_COLUMNS`/`COMPLEXTAB_HEADER`), import it into the tests to build
  fixture rows, and add a test that asserts the upstream header still has the expected column at
  each index Babel reads. The constant is the canonical format documentation living next to the
  code; the header assertion turns a silent upstream re-ordering into a loud test failure instead
  of corrupted output. See `src/datahandlers/complexportal.py`.

- **Manifest/sentinel as the Snakemake output of a multi-file download** — when a rule downloads
  many files discovered at runtime, write a manifest listing them as the *last* action and declare
  the manifest (not the individual files or a separate flag) as the rule's output. Its presence
  then reliably signals that the whole download phase completed, and the extraction rule reads it
  to know what to parse. See `complexportal.pull_complexportal()`.

- **Always write an explicit Biolink type in the IDs file** — the `ids/[TYPE]/[PREFIX]` file is
  `CURIE\tbiolink:Type`. Even when every CURIE from a source has the same prefix and type (so the
  type column looks redundant), write it explicitly: it is essential the moment a source spans
  multiple types, and it documents intent. Prefer generating IDs directly from the source rows
  (as each CURIE is first seen) rather than deriving the file from `labels` via `awk` — deriving
  from labels silently drops any identifier whose label column is empty.

- **Docstrings** — give modules, classes, and non-trivial functions a docstring saying what they
  do and any non-obvious behavior (e.g. dedup keys, side effects, why a network call happens).
  This is cheap, survives refactors, and is the first thing read when revisiting an ingest. Name
  functions for what they do — e.g. `fetch_*` (not `get_*`) when the call hits the network.

- **Test documentation** — every test function should have a docstring that explains (a) what
  scenario is being tested and (b) what the expected outcome is. "Should" phrasing makes both
  explicit (e.g. "``excluded_sources`` should skip ids and concords — FOO:2 must not appear in the
  clique dict"). Group related tests with a `# LABEL` section comment in the code (e.g.
  `# BASIC MERGING`, `# EDGE CASES`), with additional `# ----` lines before and after the section
  comments if that will help make them more distinct. The module docstring should describe what the
  file covers overall; do **not** duplicate the group list there — the section headers in the code
  are the authoritative, always-current index.

- **Test assertion helpers** — `tests/conftest.py` exports `assert_labels_file_valid`,
  `assert_synonyms_file_valid`, `assert_ids_file_valid`, `assert_concordance_file_valid`,
  `assert_taxa_file_valid`, and `assert_descriptions_file_valid` (plus `read_tsv`). Use these
  instead of hand-rolling TSV checks in new tests; when a handler adds a new output kind, add the
  matching helper to the root conftest rather than a private one in the test file.

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

When a documentation file mentions a specific ontology term by CURIE, link it to its OBO
PURL and include the preferred label in double-quotes:

```markdown
[`EMAPA:0`](http://purl.obolibrary.org/obo/EMAPA_0) "anatomical structure"
```

Resolve CURIEs to URLs with `src/util.py:get_biolink_prefix_map()`, which returns a
`curies.Converter` for the configured Biolink version (`converter.expand("EMAPA:0")`);
prefer that helper over fetching the prefix map yourself. Preferred labels come from
`babel_downloads/<PREFIX>/labels` (tab-separated `CURIE\tlabel`).
