"""Unit tests for src/model/clique_diff.py.

Exercises diff_cliques against hand-built before/after glom-dict states so the four-way
categorisation (pure_new / expanded / merged / unrelated) is locked in. Includes a
multi-prefix source_curies case to confirm the diff logic does not silently special-case
a single-prefix source.
"""

import pytest

from src.model.clique_diff import (
    cliques_from_compendia,
    cliques_set,
    diff_cliques,
)


def _glom_dict_from_cliques(cliques):
    """Helper: build a {curie: set} glom-style dict where every CURIE in a clique points
    to that clique's shared set object."""
    out = {}
    for members in cliques:
        s = set(members)
        for c in members:
            out[c] = s
    return out


@pytest.mark.unit
def test_diff_classifies_pure_new_clique_of_only_source_curies():
    before = _glom_dict_from_cliques([{"A:1"}])
    after = _glom_dict_from_cliques([{"A:1"}, {"NEW:1", "NEW:2"}])
    diff = diff_cliques(before, after, {"NEW:1", "NEW:2"}, semantic_type="t")

    assert {frozenset({"NEW:1", "NEW:2"})} == set(diff.pure_new_cliques)
    assert diff.expanded_cliques == []
    assert diff.merged_cliques == []


@pytest.mark.unit
def test_diff_classifies_expanded_clique():
    before = _glom_dict_from_cliques([{"A:1", "B:1"}])
    after = _glom_dict_from_cliques([{"A:1", "B:1", "NEW:1"}])
    diff = diff_cliques(before, after, {"NEW:1"}, semantic_type="t")

    assert diff.pure_new_cliques == []
    assert diff.merged_cliques == []
    assert len(diff.expanded_cliques) == 1
    expanded = diff.expanded_cliques[0]
    assert expanded.before_clique == frozenset({"A:1", "B:1"})
    assert expanded.added_source_curies == frozenset({"NEW:1"})
    assert expanded.after_clique == frozenset({"A:1", "B:1", "NEW:1"})


@pytest.mark.unit
def test_diff_classifies_merged_cliques():
    before = _glom_dict_from_cliques([{"A:1", "B:1"}, {"C:1", "D:1"}])
    after = _glom_dict_from_cliques([{"A:1", "B:1", "C:1", "D:1", "NEW:1"}])
    diff = diff_cliques(before, after, {"NEW:1"}, semantic_type="t")

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
    before = _glom_dict_from_cliques([{"A:1"}, {"B:1"}])
    after = _glom_dict_from_cliques([{"A:1"}, {"B:1"}, {"NEW:1"}])
    diff = diff_cliques(before, after, {"NEW:1"}, semantic_type="t")

    assert len(diff.pure_new_cliques) == 1
    assert diff.expanded_cliques == []
    assert diff.merged_cliques == []


@pytest.mark.unit
def test_diff_handles_multi_prefix_source_curies():
    """A single source may declare CURIEs under more than one prefix; the diff must
    treat all of them as 'source' regardless of prefix."""
    before = _glom_dict_from_cliques([{"A:1", "B:1"}, {"C:1"}])
    after = _glom_dict_from_cliques(
        [
            {"A:1", "B:1", "SRC_A:1"},
            {"C:1", "SRC_B:1"},
        ]
    )
    diff = diff_cliques(before, after, {"SRC_A:1", "SRC_B:1"}, semantic_type="t")

    assert diff.pure_new_cliques == []
    assert diff.merged_cliques == []
    assert {ec.added_source_curies for ec in diff.expanded_cliques} == {
        frozenset({"SRC_A:1"}),
        frozenset({"SRC_B:1"}),
    }


@pytest.mark.unit
def test_diff_treats_concord_introduced_aliases_as_pure_new():
    """If a source's concord introduces non-source CURIEs that weren't in any before
    clique, the resulting after-clique is reported as pure_new — without the source,
    those CURIEs would not be in Babel at all."""
    before = _glom_dict_from_cliques([{"A:1"}])  # ALIAS:1 not present in before
    after = _glom_dict_from_cliques([{"A:1"}, {"SRC:1", "ALIAS:1"}])
    diff = diff_cliques(before, after, {"SRC:1"}, semantic_type="t")

    assert diff.expanded_cliques == []
    assert diff.merged_cliques == []
    assert frozenset({"SRC:1", "ALIAS:1"}) in set(diff.pure_new_cliques)


@pytest.mark.unit
def test_cliques_set_collapses_shared_set_references():
    """glom dicts point many CURIEs at the same set object; cliques_set must dedupe."""
    shared = {"X:1", "Y:1"}
    glom_dict = {"X:1": shared, "Y:1": shared, "Z:1": {"Z:1"}}
    out = cliques_set(glom_dict)
    assert out == frozenset({frozenset({"X:1", "Y:1"}), frozenset({"Z:1"})})


@pytest.mark.unit
def test_cliques_from_compendia_reads_jsonl(tmp_path):
    path = tmp_path / "Foo.txt"
    path.write_text(
        '{"type":"biolink:Foo","identifiers":[{"i":"A:1","l":"a"},{"i":"B:1","l":"b"}]}\n'
        '{"type":"biolink:Foo","identifiers":[{"i":"C:1","l":"c"}]}\n'
    )
    out = cliques_from_compendia([path])
    assert out == frozenset({frozenset({"A:1", "B:1"}), frozenset({"C:1"})})
