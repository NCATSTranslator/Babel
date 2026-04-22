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
    uv run pytest tests/pipeline/test_vocabulary_partitioning.py --pipeline --no-cov -v
Run a single vocabulary:
    uv run pytest tests/pipeline/test_vocabulary_partitioning.py --pipeline --no-cov -v -k MESH
"""
import pytest

from tests.pipeline.conftest import _output_paths, _read_ids

# Known cross-compendium duplicates that have not yet been resolved.
# Each entry is a set of identifier strings that are known to appear in more
# than one compendium for that vocabulary.
#
# When an underlying bug is fixed, remove the corresponding IDs from this dict
# so that the test starts enforcing the invariant for those identifiers.
#
# TODO: Create a tracking issue for each vocabulary listed here and link it.
KNOWN_DUPLICATES: dict[str, set[str]] = {
    "UMLS": {
        "UMLS:C5443441",
        "UMLS:C5443442",
    },
    "MESH": {
        # protein / anatomy overlaps
        "MESH:D022041", "MESH:D035321", "MESH:D006570", "MESH:D009707",
        "MESH:D064448", "MESH:D035341", "MESH:D045524", "MESH:D007106",
        "MESH:D000067816", "MESH:D000089804", "MESH:D002843", "MESH:D017358",
        "MESH:D008894", "MESH:D000961", "MESH:D009360",
        # chemicals / anatomy overlaps
        "MESH:D000091083", "MESH:D014688",
        # anatomy / diseasephenotype overlaps
        "MESH:D000072717", "MESH:D018404", "MESH:D065309", "MESH:D003809",
        "MESH:D008467", "MESH:D012303", "MESH:D017439", "MESH:D000153",
        "MESH:D014097", "MESH:D010677", "MESH:D000072662", "MESH:D003750",
        "MESH:D008551", "MESH:D048629", "MESH:D002921", "MESH:D007627",
        # anatomy / taxon overlaps
        "MESH:D036226", "MESH:D013172", "MESH:D052940", "MESH:D033761",
        "MESH:D053058", "MESH:D002523", "MESH:D038821", "MESH:D033661",
        "MESH:D013171", "MESH:D034101", "MESH:D013104", "MESH:D052939",
        "MESH:D013170",
    },
}


@pytest.mark.pipeline
def test_ids_non_empty(vocab_outputs):
    """Every compendium in this vocabulary must produce at least one identifier."""
    vocab, outputs = vocab_outputs
    paths = _output_paths(outputs)
    empty = [name for name, path in paths.items() if not _read_ids(path)]
    assert not empty, f"{vocab}: these compendia produced no output: {empty}"


@pytest.mark.pipeline
def test_no_id_in_multiple_compendia(vocab_outputs):
    """No identifier may appear in more than one compendium for this vocabulary."""
    vocab, outputs = vocab_outputs
    paths = _output_paths(outputs)
    seen = {}       # id -> first compendium name
    duplicates = {} # id -> list of all compendia it appeared in
    for name, path in paths.items():
        for id_ in _read_ids(path):
            if id_ in seen:
                duplicates.setdefault(id_, [seen[id_]]).append(name)
            else:
                seen[id_] = name

    known = KNOWN_DUPLICATES.get(vocab, set())
    unexpected = {k: v for k, v in duplicates.items() if k not in known}
    assert not unexpected, (
        f"{vocab}: found {len(unexpected)} unexpected IDs in multiple compendia: "
        f"{dict(list(unexpected.items())[:5])}"
    )

    still_known = known & duplicates.keys()
    if still_known:
        pytest.xfail(
            f"{vocab}: {len(still_known)} known duplicate(s) not yet fixed "
            f"(see KNOWN_DUPLICATES in this file): "
            f"{sorted(still_known)[:5]}"
        )
