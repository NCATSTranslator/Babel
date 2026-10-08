"""Unit tests for src/model/glom_diff.py.

Exercises diff_cliques against hand-built before/after glom-dict states.

Test groups
-----------
Basic classification (pure_new / expanded / merged / unrelated):
    The four mutually exclusive buckets that diff_cliques produces. Each test
    constructs a minimal before/after pair that should land entirely in one bucket.

Edge cases:
    Behaviours that the bucket names alone do not make obvious — multi-prefix sources,
    the added-vs-preexisting split, and concord-introduced aliases.

Utilities (cliques_set, cliques_from_compendia):
    The helper functions that collapse a glom dict or JSONL compendia to the frozenset
    view consumed by diff_cliques.
"""

import pytest

from src.model.glom_diff import (
    cliques_from_compendia,
    cliques_set,
    diff_cliques,
)
from tests.conftest import glom_dict_from_cliques

# ---------------------------------------------------------------------------
# Basic classification
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_diff_classifies_pure_new_clique_of_only_source_curies():
    """A clique whose every member is a source CURIE is pure_new — it did not exist before."""
    before = glom_dict_from_cliques([{"A:1"}])
    after = glom_dict_from_cliques([{"A:1"}, {"NEW:1", "NEW:2"}])
    diff = diff_cliques(before, after, {"NEW:1", "NEW:2"}, babel_pipeline="t")

    assert {frozenset({"NEW:1", "NEW:2"})} == set(diff.pure_new_cliques)
    assert diff.expanded_cliques == []
    assert diff.merged_cliques == []


@pytest.mark.unit
def test_diff_classifies_expanded_clique():
    """A source CURIE joining a single existing before-clique is an expansion of that clique."""
    before = glom_dict_from_cliques([{"A:1", "B:1"}])
    after = glom_dict_from_cliques([{"A:1", "B:1", "NEW:1"}])
    diff = diff_cliques(before, after, {"NEW:1"}, babel_pipeline="t")

    assert diff.pure_new_cliques == []
    assert diff.merged_cliques == []
    assert len(diff.expanded_cliques) == 1
    expanded = diff.expanded_cliques[0]
    assert expanded.before_clique == frozenset({"A:1", "B:1"})
    assert expanded.added_source_curies == frozenset({"NEW:1"})
    assert expanded.after_clique == frozenset({"A:1", "B:1", "NEW:1"})


@pytest.mark.unit
def test_diff_classifies_merged_cliques():
    """A source CURIE that bridges two distinct before-cliques into one is a merge."""
    before = glom_dict_from_cliques([{"A:1", "B:1"}, {"C:1", "D:1"}])
    after = glom_dict_from_cliques([{"A:1", "B:1", "C:1", "D:1", "NEW:1"}])
    diff = diff_cliques(before, after, {"NEW:1"}, babel_pipeline="t")

    assert diff.pure_new_cliques == []
    assert diff.expanded_cliques == []
    assert len(diff.merged_cliques) == 1
    merged = diff.merged_cliques[0]
    assert set(merged.before_cliques) == {
        frozenset({"A:1", "B:1"}),
        frozenset({"C:1", "D:1"}),
    }
    assert merged.source_curies_involved == frozenset({"NEW:1"})


@pytest.mark.unit
def test_diff_ignores_cliques_with_no_source_curies():
    """After-cliques that contain no source CURIE at all are silently skipped."""
    before = glom_dict_from_cliques([{"A:1"}, {"B:1"}])
    after = glom_dict_from_cliques([{"A:1"}, {"B:1"}, {"NEW:1"}])
    diff = diff_cliques(before, after, {"NEW:1"}, babel_pipeline="t")

    assert len(diff.pure_new_cliques) == 1
    assert diff.expanded_cliques == []
    assert diff.merged_cliques == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_diff_handles_multi_prefix_source_curies():
    """A single source may declare CURIEs under more than one prefix; the diff must
    treat all of them as 'source' regardless of prefix."""
    before = glom_dict_from_cliques([{"A:1", "B:1"}, {"C:1"}])
    after = glom_dict_from_cliques(
        [
            {"A:1", "B:1", "SRC_A:1"},
            {"C:1", "SRC_B:1"},
        ]
    )
    diff = diff_cliques(before, after, {"SRC_A:1", "SRC_B:1"}, babel_pipeline="t")

    assert diff.pure_new_cliques == []
    assert diff.merged_cliques == []
    assert {ec.added_source_curies for ec in diff.expanded_cliques} == {
        frozenset({"SRC_A:1"}),
        frozenset({"SRC_B:1"}),
    }


@pytest.mark.unit
def test_diff_splits_truly_added_from_preexisting_source_curies():
    """When a source's CURIE is already in the before-clique via xref from another
    source, ``added_source_curies`` must not include it — only ``preexisting_source_curies``
    should. The before-clique itself is unchanged in that case; the new source only
    re-types the xref leaf to a typed identifier without growing the clique."""
    # SRC:1 is pre-existing in the before-clique via someone else's xref; adding the
    # SRC source's ids file doesn't grow the clique, it just types SRC:1.
    before = glom_dict_from_cliques([{"A:1", "B:1", "SRC:1"}])
    after = glom_dict_from_cliques([{"A:1", "B:1", "SRC:1"}])
    diff = diff_cliques(before, after, {"SRC:1"}, babel_pipeline="t")

    assert len(diff.expanded_cliques) == 1
    ec = diff.expanded_cliques[0]
    assert ec.added_source_curies == frozenset()
    assert ec.preexisting_source_curies == frozenset({"SRC:1"})
    assert ec.before_clique == ec.after_clique


@pytest.mark.unit
def test_diff_treats_concord_introduced_aliases_as_pure_new():
    """If a source's concord introduces non-source CURIEs that weren't in any before
    clique, the resulting after-clique is reported as pure_new — without the source,
    those CURIEs would not be in Babel at all."""
    before = glom_dict_from_cliques([{"A:1"}])  # ALIAS:1 not present in before
    after = glom_dict_from_cliques([{"A:1"}, {"SRC:1", "ALIAS:1"}])
    diff = diff_cliques(before, after, {"SRC:1"}, babel_pipeline="t")

    assert diff.expanded_cliques == []
    assert diff.merged_cliques == []
    assert frozenset({"SRC:1", "ALIAS:1"}) in set(diff.pure_new_cliques)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cliques_set_collapses_shared_set_references():
    """glom dicts point many CURIEs at the same set object; cliques_set must dedupe."""
    shared = {"X:1", "Y:1"}
    glom_dict = {"X:1": shared, "Y:1": shared, "Z:1": {"Z:1"}}
    out = cliques_set(glom_dict)
    assert out == frozenset({frozenset({"X:1", "Y:1"}), frozenset({"Z:1"})})


@pytest.mark.unit
def test_cliques_from_compendia_reads_jsonl(tmp_path):
    """Reads the ``i`` field from each identifier entry across one or more JSONL compendium files."""
    path = tmp_path / "Foo.txt"
    path.write_text(
        '{"type":"biolink:Foo","identifiers":[{"i":"A:1","l":"a"},{"i":"B:1","l":"b"}]}\n'
        '{"type":"biolink:Foo","identifiers":[{"i":"C:1","l":"c"}]}\n'
    )
    out = cliques_from_compendia([path])
    assert out == frozenset({frozenset({"A:1", "B:1"}), frozenset({"C:1"})})
