"""Offline tests for the concord rows that ``build_sets()`` writes.

These cover the output-ordering guarantee that keeps concord files reproducible between
builds. ``tests/test_uber.py`` holds the live-endpoint UberGraph tests; everything here
stubs the endpoint out so it runs in the default (offline) CI pass.
"""

import io

import pytest

from src.ubergraph import HIERARCHY_PART_OF, build_sets

pytestmark = [pytest.mark.unit]


class _StubUberGraph:
    """Stands in for ``UberGraph``, returning a fixed descendent → xrefs map, no network call.

    ``build_sets()`` constructs its own ``UberGraph()`` with no arguments, so tests install
    this by monkeypatching the name in ``src.ubergraph``.
    """

    def __init__(self, result):
        self._result = result

    def get_subclasses_and_xrefs(self, iri, hierarchy_predicate=None):
        return self._result


def _run_build_sets(monkeypatch, result, prefix="UBERON"):
    """Run build_sets() against a stubbed endpoint and return the written concord lines."""
    monkeypatch.setattr("src.ubergraph.UberGraph", lambda: _StubUberGraph(result))
    buffer = io.StringIO()
    build_sets("UBERON:0001062", {prefix: buffer}, set_type="xref")
    return buffer.getvalue().splitlines()


# ---
# OUTPUT ORDERING
# ---


def test_build_sets_writes_xrefs_for_one_subject_in_sorted_order(monkeypatch):
    """The xrefs of a single subject should be written in sorted order.

    ``build_sets()`` collects xrefs into a set, whose iteration order for strings varies
    per process under hash randomization. Unsorted output makes clique membership depend
    on the run, because glom's ``unique_prefixes`` keeps whichever CURIE of a restricted
    prefix it encounters first. Eight xrefs make an accidentally-sorted pass a 1-in-40320
    coincidence rather than a coin flip.
    """
    xrefs = {
        "EMAPA:35459",
        "EMAPA:28061",
        "EMAPA:16271",
        "EMAPA:16169",
        "MA:0002935",
        "MA:0001234",
        "ZFA:0000787",
        "ZFA:0000111",
    }
    lines = _run_build_sets(monkeypatch, {"UBERON:0005185": xrefs})

    written = [line.split("\t")[2] for line in lines]
    assert written == sorted(xrefs)


def test_build_sets_writes_subjects_in_sorted_order(monkeypatch):
    """Subjects should be written in sorted order too.

    The SPARQL queries carry no ORDER BY, so the map ``build_sets()`` iterates preserves
    whatever arbitrary row order the endpoint returned. Sorting makes the concord
    byte-identical across builds of identical code and data.
    """
    result = {
        "UBERON:0007213": {"EMAPA:16271"},
        "UBERON:0000955": {"EMAPA:16169"},
        "UBERON:0005185": {"EMAPA:28061"},
        "UBERON:0002107": {"EMAPA:35459"},
    }
    lines = _run_build_sets(monkeypatch, result)

    subjects = [line.split("\t")[0] for line in lines]
    assert subjects == sorted(result)


def test_build_sets_keeps_the_lowest_curie_first_for_competing_xrefs(monkeypatch):
    """A subject xreffing two CURIEs of the same prefix should write the lower one first.

    This pins the case that exposed the ordering bug: [`UBERON:0005185`] xrefs both
    ``EMAPA:28061`` "medullary collecting duct" and the label-less, deprecated
    ``EMAPA:35459``. Whenever the target prefix is one of a pipeline's ``unique_prefixes``,
    only the first-written of two competing CURIEs joins the clique and the loser is dropped
    entirely if it has no ids-file row -- so which one wins must not vary between builds.
    EMAPA is no longer restricted this way (see ``anatomy_unique_prefixes`` in config.yaml),
    but UBERON and GO still are, and the guarantee is what makes any such choice reproducible.
    """
    lines = _run_build_sets(monkeypatch, {"UBERON:0005185": {"EMAPA:35459", "EMAPA:28061"}})

    assert [line.split("\t")[2] for line in lines] == ["EMAPA:28061", "EMAPA:35459"]


# ---
# ARGUMENT VALIDATION
# ---


def test_build_sets_rejects_custom_hierarchy_predicate_for_non_xref():
    """build_sets() should raise ValueError immediately if a non-default hierarchy_predicate
    is combined with set_type != 'xref', because those code paths hardcode rdfs:subClassOf.

    Offline by construction: the check fires before any UberGraph instance is built, which is
    why this lives here rather than in the network-marked tests/test_uber.py.
    """
    for set_type in ("exact", "close"):
        with pytest.raises(ValueError, match="hierarchy_predicate"):
            build_sets("EMAPA:0", {}, set_type=set_type, hierarchy_predicate=HIERARCHY_PART_OF)
