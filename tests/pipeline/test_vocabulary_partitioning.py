"""Generic vocabulary-partitioning tests for all entries in VOCABULARY_REGISTRY.

For every registered vocabulary, two tests run automatically:

  test_ids_non_empty
      Each compendium's write_X_ids() must produce at least one identifier.

  test_no_id_in_multiple_compendia
      No identifier may appear in more than one compendium's output — the core
      correctness invariant.  If the same ID lands in two compendia, Node
      Normalization will see a duplicate and normalization will be ambiguous.

Vocabulary-specific targeted tests (e.g. MeSH tree-exclusion, UMLS protein-
semantic-tree guard) live in test_mesh_pipeline.py / test_umls_pipeline.py.

To add a new vocabulary, add its fixtures to conftest.py and one entry in
VOCABULARY_REGISTRY.  This file never needs to change.

All tests are skipped by default.  Run with:
    PYTHONPATH=. uv run pytest tests/pipeline/test_vocabulary_partitioning.py --pipeline --no-cov -v
Run a single vocabulary:
    PYTHONPATH=. uv run pytest tests/pipeline/test_vocabulary_partitioning.py --pipeline --no-cov -v -k MESH
"""
import pytest

from tests.pipeline.conftest import _read_ids


@pytest.mark.pipeline
def test_ids_non_empty(vocab_outputs):
    """Every compendium in this vocabulary must produce at least one identifier."""
    vocab, outputs = vocab_outputs
    # outputs is a dict; "excluded_tree_terms" (MESH-specific) is not an output path.
    paths = {name: path for name, path in outputs.items() if isinstance(path, str)}
    empty = [name for name, path in paths.items() if not _read_ids(path)]
    assert not empty, f"{vocab}: these compendia produced no output: {empty}"


@pytest.mark.pipeline
def test_no_id_in_multiple_compendia(vocab_outputs):
    """No identifier may appear in more than one compendium for this vocabulary."""
    vocab, outputs = vocab_outputs
    paths = {name: path for name, path in outputs.items() if isinstance(path, str)}
    seen = {}       # id -> first compendium name
    duplicates = {} # id -> list of all compendia it appeared in
    for name, path in paths.items():
        for id_ in _read_ids(path):
            if id_ in seen:
                duplicates.setdefault(id_, [seen[id_]]).append(name)
            else:
                seen[id_] = name
    assert not duplicates, (
        f"{vocab}: found {len(duplicates)} IDs in multiple compendia: "
        f"{dict(list(duplicates.items())[:5])}"
    )
