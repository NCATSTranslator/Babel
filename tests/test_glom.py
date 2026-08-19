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


# --- Rust implementation: synthetic semantics tests ---
#
# These pin the behaviour of the Rust union-find (rust/src/glom.rs) that replaced the Python glom.
# They are written against small, hand-computed expected cliques rather than a Python reference copy
# (there is no longer one), and they deliberately exercise the paths that are easy to get wrong:
# order-sensitive unique-prefix rejection, the KEGG/PUBCHEM guard, singletons, in-place mutation,
# the `close` check, and the cross-call state cache.


@pytest.mark.unit
def test_returns_none_and_mutates_in_place():
    """glom must keep the original contract: mutate conc_set, return None."""
    d = {}
    result = glom(d, [("A:1", "B:1")], unique_prefixes=[])
    assert result is None
    assert d["A:1"] == {"A:1", "B:1"}
    assert d["B:1"] == {"A:1", "B:1"}
    # both members share one set object, like the Python implementation
    assert d["A:1"] is d["B:1"]


@pytest.mark.unit
def test_singletons_register_without_merging():
    d = {}
    glom(d, [("A:1",), ("B:2",)], unique_prefixes=[])
    assert d["A:1"] == {"A:1"}
    assert d["B:2"] == {"B:2"}


@pytest.mark.unit
def test_unique_prefix_rejection_blocks_second_same_prefix():
    """A merge that would put two identifiers of a unique prefix in one clique is skipped.

    Identifiers are pre-registered first (as the pipeline does via identifier files), so the
    rejected identifier stays in its own singleton clique rather than disappearing."""
    d = {}
    glom(d, [("INCHIKEY:A",), ("INCHIKEY:B",), ("X:1",)], unique_prefixes=["INCHIKEY"])
    glom(d, [("INCHIKEY:A", "X:1")], unique_prefixes=["INCHIKEY"])
    glom(d, [("INCHIKEY:B", "X:1")], unique_prefixes=["INCHIKEY"])
    assert d["INCHIKEY:A"] == {"INCHIKEY:A", "X:1"}
    # INCHIKEY:B's merge was rejected; it stays in its own singleton clique.
    assert d["INCHIKEY:B"] == {"INCHIKEY:B"}


@pytest.mark.unit
def test_rejected_group_does_not_add_new_members():
    """Faithful to the Python: if a group is rejected, its *new* members are not added to conc_set
    at all (they do not even become singletons). In the real pipeline every identifier is
    pre-registered from the identifier files first, so this only affects never-registered ids."""
    d = {}
    glom(d, [("INCHIKEY:A", "X:1")], unique_prefixes=["INCHIKEY"])
    glom(d, [("INCHIKEY:B", "X:1")], unique_prefixes=["INCHIKEY"])
    assert "INCHIKEY:B" not in d
    assert d["X:1"] == {"INCHIKEY:A", "X:1"}


@pytest.mark.unit
def test_unique_prefix_rejection_is_order_sensitive():
    """Whichever same-prefix identifier reaches the bridge first claims it; reversing the order
    reverses who is rejected. This is why the merge loop must stay sequential."""
    d1 = {}
    glom(d1, [("INCHIKEY:A",), ("INCHIKEY:B",), ("X:1",)], unique_prefixes=["INCHIKEY"])
    glom(d1, [("INCHIKEY:A", "X:1"), ("INCHIKEY:B", "X:1")], unique_prefixes=["INCHIKEY"])
    assert d1["X:1"] == {"INCHIKEY:A", "X:1"}
    assert d1["INCHIKEY:B"] == {"INCHIKEY:B"}

    d2 = {}
    glom(d2, [("INCHIKEY:A",), ("INCHIKEY:B",), ("X:1",)], unique_prefixes=["INCHIKEY"])
    glom(d2, [("INCHIKEY:B", "X:1"), ("INCHIKEY:A", "X:1")], unique_prefixes=["INCHIKEY"])
    assert d2["X:1"] == {"INCHIKEY:B", "X:1"}
    assert d2["INCHIKEY:A"] == {"INCHIKEY:A"}


@pytest.mark.unit
def test_garbage_prefix_raises():
    """A bare KEGG: or PUBCHEM: identifier raises (the Python raised Exception('garbage'))."""
    with pytest.raises(Exception, match="garbage"):
        glom({}, [("KEGG:C00001", "X:1")], unique_prefixes=[])
    with pytest.raises(Exception, match="garbage"):
        glom({}, [("PUBCHEM:123", "Y:1")], unique_prefixes=[])


@pytest.mark.unit
def test_garbage_prefix_is_exact_not_a_prefix_match():
    """KEGG.COMPOUND / PUBCHEM.COMPOUND must NOT trip the guard (only bare KEGG:/PUBCHEM: do)."""
    d = {}
    glom(d, [("KEGG.COMPOUND:C00001", "X:1"), ("PUBCHEM.COMPOUND:9", "Y:1")], unique_prefixes=[])
    assert d["KEGG.COMPOUND:C00001"] == {"KEGG.COMPOUND:C00001", "X:1"}
    assert d["PUBCHEM.COMPOUND:9"] == {"PUBCHEM.COMPOUND:9", "Y:1"}


@pytest.mark.unit
def test_close_rejects_when_a_close_partner_is_already_in_the_clique():
    """close={cpref: {ident: partners}}: merging ident into a clique that already holds one of its
    partners is rejected."""
    d = {}
    glom(d, [("HP:9", "X:1")], unique_prefixes=[])
    glom(d, [("MONDO:001",)], unique_prefixes=[])  # pre-register the singleton
    close = {"MONDO": {"MONDO:001": ["HP:9"]}}
    glom(d, [("MONDO:001", "X:1")], unique_prefixes=[], close=close)
    # Rejected: HP:9 (MONDO:001's close partner) is already in X:1's clique.
    assert d["MONDO:001"] == {"MONDO:001"}
    assert d["X:1"] == {"HP:9", "X:1"}


@pytest.mark.unit
def test_close_is_a_no_op_when_partners_are_not_clique_members():
    """Mirrors diseasephenotype's current use, where close partners are predicate strings that never
    appear as clique members, so nothing is rejected."""
    d = {}
    close = {"MONDO": {"MONDO:001": ["oio:closeMatch"]}}
    glom(d, [("MONDO:001", "HP:1")], unique_prefixes=[], close=close)
    assert d["MONDO:001"] == {"MONDO:001", "HP:1"}


@pytest.mark.unit
def test_labeled_id_elements_use_their_identifier():
    """glom accepts LabeledID group elements via their .identifier attribute."""
    from src.LabeledID import LabeledID

    d = {}
    glom(d, [(LabeledID("A:1", "label a"), "B:1")], unique_prefixes=[])
    assert d["A:1"] == {"A:1", "B:1"}


@pytest.mark.unit
def test_cache_stays_correct_when_the_dict_grows_outside_glom():
    """The cross-call state cache is keyed by the dict and validated by its entry count; if the dict
    is mutated outside glom (here: a new singleton added by hand) the next call must rebuild and
    still produce the right cliques."""
    d = {}
    glom(d, [("A:1", "B:1")], unique_prefixes=[])
    d["C:1"] = {"C:1"}  # external mutation -> entry count changes
    glom(d, [("C:1", "B:1")], unique_prefixes=[])
    assert d["A:1"] == {"A:1", "B:1", "C:1"}
    assert d["C:1"] == {"A:1", "B:1", "C:1"}


@pytest.mark.unit
def test_repeated_calls_on_one_dict_accumulate():
    """The hot-caller pattern (one glom call per file on the same dict) must accumulate state."""
    d = {}
    glom(d, [("A:1", "B:1")], unique_prefixes=[])
    glom(d, [("C:1",)], unique_prefixes=[])
    glom(d, [("B:1", "C:1")], unique_prefixes=[])
    assert d["A:1"] == d["B:1"] == d["C:1"] == {"A:1", "B:1", "C:1"}
