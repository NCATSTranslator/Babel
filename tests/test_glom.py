"""glom is a tool that looks at list of sets of values and combines them together if they share members"""

import pytest

from src.babel_utils import glom


@pytest.mark.unit
def test_uberon():
    uberon = [("UBERON:123",)]
    dict = {}
    glom(dict, uberon, unique_prefixes="UBERON")
    uber2 = [{"UBERON:123", "SOME:other"}]
    glom(dict, uber2, unique_prefixes="UBERON")
    print(dict)


@pytest.mark.unit
def test_simple():
    """Given 3 sets, 2 of which share a member, output 2 sets, with the sharing sets combined"""
    d = {}
    eqs = [("1", "2"), ("2", "3"), ("4", "5")]
    glom(d, eqs)
    print(f"{d}")
    assert len(d) == 5
    assert d["1"] == d["2"] == d["3"] == {"1", "2", "3"}
    assert d["4"] == d["5"] == {"4", "5"}


@pytest.mark.unit
def test_two_calls():
    """Test using glom iteratively. The first call joins the first two sets, then the second call joins
    the next two and the new set."""
    d = {}
    eqs = [("1", "2"), ("2", "3"), ("4", "5"), ("6", "7")]
    oeqs = [("5", "7")]
    glom(d, eqs)
    glom(d, oeqs)
    assert d["1"] == d["2"] == d["3"] == {"1", "2", "3"}
    assert d["4"] == d["5"] == d["6"] == d["7"] == {"4", "5", "6", "7"}


@pytest.mark.unit
def test_sets():
    """Test using set() as opposed to {}"""
    d = {}
    eqs = [{"1", "2"}, {"2", "3"}, {"4", "5"}, {"6", "7"}]
    oeqs = [{"5", "7"}]
    glom(d, eqs)
    glom(d, oeqs)
    assert d["1"] == d["2"] == d["3"] == {"1", "2", "3"}
    assert d["4"] == d["5"] == d["6"] == d["7"] == {"4", "5", "6", "7"}


@pytest.mark.unit
def test_bigger_sets():
    """Test when the sets have more than two members.
    As of recent builds, we no longer expect this to work.
    Now glom only operates on new pairwise sets"""
    d = {}
    eqs = [{"1", "2", "3"}, {"4", "5", "6"}]
    try:
        glom(d, eqs)
        assert False
    except ValueError:
        assert True


# PAIR SHAPES
#
# Compendium builders hand glom() concord pairs as 2-tuples, sometimes from a generator, to save
# memory (see src.model.intermediates.read_concord_pairs); they used to hand it 2-sets in a list.
# These pin that the shape changes nothing, including the two places it could: a self-pair, which
# is one element as a set but two as a tuple, and a unique_prefixes conflict, which keeps whichever
# pair glom() sees first.

GLOM_SHAPE_PAIRS = [
    ("A:1", "B:1"),
    ("B:1", "A:2"),  # Refused: would put A:1 and A:2 in one clique, and A is unique.
    ("C:1", "C:1"),  # A self-pair.
    ("C:1", "B:2"),
    ("B:2", "D:1"),
]
GLOM_SHAPE_EXPECTED = {
    "A:1": {"A:1", "B:1"},
    "B:1": {"A:1", "B:1"},
    "C:1": {"C:1", "B:2", "D:1"},
    "B:2": {"C:1", "B:2", "D:1"},
    "D:1": {"C:1", "B:2", "D:1"},
}


@pytest.mark.unit
@pytest.mark.parametrize(
    "shape",
    [
        pytest.param(lambda pairs: [set(p) for p in pairs], id="list-of-sets"),
        pytest.param(lambda pairs: [list(p) for p in pairs], id="list-of-lists"),
        pytest.param(lambda pairs: list(pairs), id="list-of-tuples"),
        pytest.param(lambda pairs: (p for p in pairs), id="generator-of-tuples"),
    ],
)
def test_pair_shape_does_not_change_cliques(shape):
    """Should build the same cliques, and refuse the same unique_prefixes merge, whatever the pairs' container."""
    d = {}
    glom(d, shape(GLOM_SHAPE_PAIRS), unique_prefixes=["A"])
    assert d == GLOM_SHAPE_EXPECTED
