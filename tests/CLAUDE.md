# CLAUDE.md — tests/

Point-of-use conventions for writing Babel tests, for Claude Code. For the test taxonomy (the four
`unit`/`network`/`slow`/`pipeline` marks, the `min_memory_gb` guard) and *where* a new test belongs,
see [`README.md`](README.md) — this file only covers how to write one once you know where it goes.

- **Test documentation** — every test docstring states the scenario and expected outcome ("should"
  phrasing works well). Group related tests with a `# LABEL` section comment; the module docstring
  describes the file overall without duplicating that section list.

- **Assertion helpers** — `tests/conftest.py` exports `assert_labels_file_valid`,
  `assert_synonyms_file_valid`, `assert_ids_file_valid`, `assert_concordance_file_valid`,
  `assert_taxa_file_valid`, and `assert_descriptions_file_valid` (plus `read_tsv`). Use these
  instead of hand-rolling TSV checks. When a handler adds a new output kind, add the matching helper
  to the root `conftest.py` rather than a private one in the test file.

- **Ruff lint in test code** — all Python must pass `uv run ruff check`. Two rules are easy to trip
  in tests: E741 (no single-letter ambiguous names like `l`/`O`/`I`) and F841 (no unread
  assignments).
