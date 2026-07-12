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

- **Fixtures for a real-data bug must be copied verbatim** — when a test stands in for a specific
  record from a source file, paste that record's row exactly as it appears in the downloaded file
  and name the record's ID in a comment, so the next person can re-derive it. Never hand-compose a
  row that looks like what you think the source contains. A fabricated fixture in the #744 work
  invented a `gene_info.gz` row shape NCBI never emits and then asserted it survives, certifying a
  guarantee the real data does not provide — and it read as entirely plausible for months. If the
  real row is too long to paste, that is a reason to add a `pipeline` test over the real file, not
  a reason to invent a shorter one.

- **Pin known-imperfect behavior, don't leave it unasserted** — when shipping a partial fix, assert
  the wrong-but-harmless behavior that remains, with a comment saying it pins current behavior, a
  link to the tracking issue, and an instruction to **invert** the assertion when the fix lands
  rather than delete it. Otherwise the eventual fix changes behavior nothing was watching. See the
  leftover comma-pieces in `tests/datahandlers/test_ncbigene.py` (issue #932).
