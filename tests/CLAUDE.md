# Working on tests (agent notes)

Operational guidance for editing and running Babel's tests. This file is the agent-facing
companion to [`README.md`](README.md) (human-facing taxonomy, per-file index, strategy) — when
they overlap, put *what a test covers* in the README and *how not to break things* here.

## Running the right subset

- CI runs only `uv run pytest -m unit -q` — keep unit tests fast, offline, dependency-free.
- `network` and `pipeline` tests are skipped unless opted in (`--network`, `--pipeline`, or
  `--all`). Pipeline tests call `write_*_ids()` and reuse cached `babel_outputs/intermediate/…`;
  pass `--regenerate` to force a rebuild after changing filtering logic.
- A test that needs lots of RAM must carry `@pytest.mark.min_memory_gb(n)` (auto-skips below `n`
  GiB); match `n` to the corresponding Snakemake rule's `mem=`.

## Import-mode gotchas (these cause confusing collection errors)

The test tree mostly does **not** use `__init__.py`, so pytest's default *prepend* import mode
imports each test file as a **top-level module**. Two consequences:

- **Every test file needs a basename unique across the whole suite.** Two files named
  `test_foo.py` in different directories collide with `import file mismatch ... use a unique
  basename`. Before naming `tests/<dir>/test_foo.py`, check there is no other `test_foo.py`; if
  there is, name yours `test_foo_<context>.py` (e.g. `test_clique_diff_tool.py` exists precisely
  because `tests/test_clique_diff.py` already does).
- **Do not add `tests/tools/__init__.py`.** Making `tests/tools` a package puts it on `sys.path`
  as `tools`, shadowing the real top-level `tools/` package and breaking `from tools.slurm import
  …`. Tool tests import fine via the `pythonpath = ["."]` setting in `pyproject.toml`.

## Conventions to follow when adding a test

- **Use the shared validators**, don't hand-roll TSV checks: `assert_labels_file_valid`,
  `assert_ids_file_valid`, `assert_concordance_file_valid`, `assert_taxa_file_valid`,
  `assert_descriptions_file_valid`, `assert_synonyms_file_valid`, `read_tsv` — all exported from
  the **root** `tests/conftest.py`. When a handler grows a new output kind, add the matching helper
  there, not privately in the test file.
- **Docstring every test** with the scenario and expected outcome ("should" phrasing), and group
  related tests with `# --- Label ---` section comments. The module docstring lists the section
  labels, not the individual tests. (Full convention: root `CLAUDE.md` → Conventions.)
- **Mirror the source's column constants** when testing a fixed-column parser (import
  `*_COLUMNS`/`*_HEADER` from the handler) and add a header-assertion test so an upstream
  re-ordering fails loudly. See `tests/datahandlers/test_complexportal.py`.
- Ruff runs on tests too: no single-letter `l`/`O`/`I` (E741), no unused assignments (F841).

## Where to add what / per-file index

See [`README.md`](README.md) — "Where to add a new test", the per-file descriptions, and
[`pipeline/README.md`](pipeline/README.md) for pipeline fixtures, caching, and the
`VOCABULARY_REGISTRY`.
