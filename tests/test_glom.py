"""The behavior of ``src.babel_utils.glom()``, written down as a contract.

glom() merges pairwise equivalences into cliques, and every compendium is built by it. These tests
pin what it does today -- the intended behavior and the quirks alike -- so that a change to it, or a
replacement (a Rust port has been floated: #988), can be checked against something more exact than
"the build looks the same". A test whose name or docstring says **quirk** pins behavior that is
probably accidental: a replacement should reproduce it until someone decides otherwise, and whoever
changes it should invert that test rather than delete it.

The ``# REFERENCE MODEL`` section restates the whole contract as a short, plain implementation and
checks glom() against it over randomized inputs. If you change glom(), change the model to match and
say why; if you replace glom(), the model is the specification to test the replacement against.
"""

import copy
import random
from collections import defaultdict

import pytest

from src.babel_utils import glom


def partition(cliques):
    """The cliques in a glom() dict, as a set of frozensets, for order-free comparison."""
    return {frozenset(members) for members in cliques.values()}


# BASIC MERGING


@pytest.mark.unit
def test_pairs_sharing_a_member_merge():
    """Should merge pairs that share a member, transitively, and leave unconnected pairs apart."""
    d = {}
    glom(d, [("1", "2"), ("2", "3"), ("4", "5")], unique_prefixes=[])
    assert len(d) == 5
    assert d["1"] == d["2"] == d["3"] == {"1", "2", "3"}
    assert d["4"] == d["5"] == {"4", "5"}


@pytest.mark.unit
def test_calls_accumulate_into_the_same_dict():
    """Should merge a later call's pairs into the cliques earlier calls built."""
    d = {}
    glom(d, [("1", "2"), ("2", "3"), ("4", "5"), ("6", "7")], unique_prefixes=[])
    glom(d, [("5", "7")], unique_prefixes=[])
    assert d["1"] == d["2"] == d["3"] == {"1", "2", "3"}
    assert d["4"] == d["5"] == d["6"] == d["7"] == {"4", "5", "6", "7"}


@pytest.mark.unit
def test_a_one_element_group_adds_a_singleton():
    """Should add a 1-tuple as a clique of one: this is how ids files are loaded before concords."""
    d = {}
    glom(d, [("A:1",)], unique_prefixes=[])
    assert d == {"A:1": {"A:1"}}


@pytest.mark.unit
def test_an_empty_group_is_a_no_op():
    """Should do nothing for an empty group."""
    d = {"A:1": {"A:1"}}
    glom(d, [()], unique_prefixes=[])
    assert d == {"A:1": {"A:1"}}


@pytest.mark.unit
def test_repeating_a_pair_changes_nothing():
    """Should leave the cliques as they were when a pair already inside one clique is glommed again."""
    d = {}
    glom(d, [("A:1", "B:1"), ("B:1", "C:1")], unique_prefixes=[])
    before = partition(d)
    glom(d, [("C:1", "A:1"), ("A:1", "B:1")], unique_prefixes=[])
    assert partition(d) == before


@pytest.mark.unit
def test_returns_none_and_mutates_in_place():
    """Should return None: the dict passed in is the result."""
    d = {}
    assert glom(d, [("A:1", "B:1")], unique_prefixes=[]) is None
    assert d


# THE DICT IT BUILDS


@pytest.mark.unit
def test_every_member_maps_to_the_same_set_object():
    """Should map every member of a clique to one shared, mutable set, which callers rely on to dedupe cliques."""
    d = {}
    glom(d, [("A:1", "B:1"), ("B:1", "C:1"), ("D:1", "E:1")], unique_prefixes=[])
    assert d["A:1"] is d["B:1"] is d["C:1"]
    assert d["D:1"] is d["E:1"]
    assert type(d["A:1"]) is set
    # Every key is in its own clique, and every clique member is a key.
    for key, members in d.items():
        assert key in members
        assert all(d[member] is members for member in members)


@pytest.mark.unit
def test_frozenset_groups_are_accepted():
    """Should accept a frozenset group and still store a plain, mutable set."""
    d = {}
    glom(d, [frozenset(["A:1", "B:1"])], unique_prefixes=[])
    assert type(d["A:1"]) is set
    assert d["A:1"] is d["B:1"]


# PAIR SHAPES
#
# Compendium builders hand glom() concord pairs as 2-tuples, sometimes from a generator, to save
# memory (see src.model.intermediates.read_concord_pairs); they used to hand it 2-sets in a list.
# The shape could have mattered in two places, and doesn't: a self-pair, which is one element as a
# set but two as a tuple, and a unique_prefixes conflict, which keeps whichever pair comes first.

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
        pytest.param(lambda pairs: [frozenset(p) for p in pairs], id="list-of-frozensets"),
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


@pytest.mark.unit
@pytest.mark.parametrize("shape", [tuple, list, set, frozenset])
def test_the_debug_sentinel_works_in_every_container(shape):
    """Should merge a group naming glom()'s debug id (``test_id``) whatever its container.

    The debug branch it switches on called ``group.intersection()``, which a tuple or list lacks, so
    a 2-tuple naming it raised AttributeError. No source emits the id -- its leading "x" is what
    keeps the branch off -- but whoever re-points it at a real CURIE to debug a build will be
    feeding it tuples.
    """
    d = {}
    glom(d, [shape(["xUBERON:0002262", "A:1"]), shape(["A:1", "B:1"])], unique_prefixes=[])
    assert d["B:1"] == {"xUBERON:0002262", "A:1", "B:1"}


# GROUP SIZE


@pytest.mark.unit
def test_a_group_of_three_raises():
    """Should raise ValueError for a group of more than two: glom() only takes pairs."""
    with pytest.raises(ValueError):
        glom({}, [{"1", "2", "3"}], unique_prefixes=[])


@pytest.mark.unit
def test_groups_before_a_bad_one_stay_applied():
    """Should keep every merge made before the oversized group: there is no rollback."""
    d = {}
    with pytest.raises(ValueError):
        glom(d, [("A:1", "B:1"), ("A:1", "B:2", "B:3"), ("C:1", "D:1")], unique_prefixes=[])
    assert partition(d) == {frozenset({"A:1", "B:1"})}


# UNIQUE PREFIXES
#
# A merge is refused -- the whole pair is skipped -- if the clique it would produce holds two
# different identifiers with a prefix in unique_prefixes. Nothing records the refusal (#1041), and
# which pair wins depends only on which comes first (#894, #945).


@pytest.mark.unit
def test_unique_prefix_conflict_keeps_the_first_pair():
    """Should keep whichever competing pair it sees first, so concord row order decides the clique."""
    forward, backward = {}, {}
    glom(forward, [("B:1", "A:1"), ("B:1", "A:2")], unique_prefixes=["A"])
    glom(backward, [("B:1", "A:2"), ("B:1", "A:1")], unique_prefixes=["A"])
    assert forward["B:1"] == {"B:1", "A:1"}
    assert backward["B:1"] == {"B:1", "A:2"}


@pytest.mark.unit
def test_a_refused_pair_adds_nothing():
    """Should drop a refused pair whole, so its new identifier is in no clique at all, not even a singleton."""
    d = {}
    glom(d, [("A:1", "B:1"), ("B:1", "A:2")], unique_prefixes=["A"])
    assert "A:2" not in d


@pytest.mark.unit
def test_a_pair_of_two_unique_prefix_identifiers_is_refused():
    """Should refuse a pair whose own two members share a unique prefix."""
    d = {}
    glom(d, [("A:1", "A:2")], unique_prefixes=["A"])
    assert d == {}


@pytest.mark.unit
def test_the_check_covers_the_whole_merged_clique():
    """Should refuse a pair joining two cliques that each hold one unique-prefix identifier."""
    d = {}
    glom(d, [("A:1", "B:1"), ("A:2", "C:1"), ("B:1", "C:1")], unique_prefixes=["A"])
    assert partition(d) == {frozenset({"A:1", "B:1"}), frozenset({"A:2", "C:1"})}


@pytest.mark.unit
def test_a_clique_already_over_the_limit_refuses_every_later_merge():
    """Should refuse any merge into a clique that already holds two unique-prefix identifiers.

    Such a clique can only come from an earlier call without the restriction. Every later pair
    touching it then fails the check, even one adding a different prefix.
    """
    d = {}
    glom(d, [("A:1", "A:2")], unique_prefixes=[])
    glom(d, [("A:2", "B:1")], unique_prefixes=["A"])
    assert "B:1" not in d


@pytest.mark.unit
def test_unique_prefixes_match_the_whole_prefix_case_sensitively():
    """Should compare the text before the first colon exactly: 'a' does not restrict 'A', nor 'A' restrict 'A.X'."""
    d = {}
    glom(d, [("A:1", "B:1"), ("A:2", "B:1"), ("A.X:1", "C:1"), ("A.X:2", "C:1")], unique_prefixes=["a", "A.X"])
    assert d["B:1"] == {"A:1", "A:2", "B:1"}
    assert d["C:1"] == {"A.X:1", "C:1"}


@pytest.mark.unit
def test_unique_prefixes_is_required():
    """Should raise TypeError, before touching the dict, when unique_prefixes is not given.

    It used to default to (INCHIKEY,), which drugchemical and geneprotein inherited without saying so
    (#882); every caller now names its restriction, and every pipeline's is in config.yaml.
    """
    d = {}
    with pytest.raises(TypeError, match="unique_prefixes"):
        glom(d, [("INCHIKEY:A", "X:1"), ("INCHIKEY:B", "X:1")])
    assert d == {}


@pytest.mark.unit
def test_unique_prefixes_is_keyword_only():
    """Should raise TypeError when unique_prefixes is passed positionally, so a call always names it."""
    with pytest.raises(TypeError):
        glom({}, [("A:1", "B:1")], ["A"])


@pytest.mark.unit
@pytest.mark.parametrize("groups", [[("UBERON:1", "UBERON:2"), ("U:1", "U:2")], []], ids=["with-groups", "no-groups"])
def test_a_string_unique_prefixes_raises(groups):
    """Should raise ValueError for a string unique_prefixes, before merging anything, even with nothing to merge.

    This inverts a pinned quirk: a string used to be read as its characters, so "UBERON" restricted
    U, B, E, R, O and N and left UBERON itself unrestricted, with nothing to say so.
    """
    d = {}
    with pytest.raises(ValueError, match=r"did you mean \['UBERON'\]"):
        glom(d, groups, unique_prefixes="UBERON")
    assert d == {}


# Values glom() used to accept and then restrict the wrong prefixes, or none, without a word; see
# validate_unique_prefixes() for how each failed.
MALFORMED_UNIQUE_PREFIXES = [
    pytest.param(b"UBERON", id="bytes"),
    pytest.param(None, id="none"),
    pytest.param(7, id="not-iterable"),
    pytest.param({"UBERON": True}, id="mapping"),
    pytest.param([b"UBERON"], id="bytes-element"),
    pytest.param([None], id="none-element"),
    pytest.param([["UBERON"]], id="list-element"),
    pytest.param([""], id="empty-prefix"),
    pytest.param(["UBERON:"], id="prefix-with-colon"),
]


@pytest.mark.unit
@pytest.mark.parametrize("groups", [[("UBERON:1", "X:1"), ("UBERON:2", "X:1")], []], ids=["with-groups", "no-groups"])
@pytest.mark.parametrize("unique_prefixes", MALFORMED_UNIQUE_PREFIXES)
def test_a_malformed_unique_prefixes_raises(unique_prefixes, groups):
    """Should raise ValueError for anything but a collection of non-empty, colon-free prefix strings, before merging."""
    d = {}
    with pytest.raises(ValueError, match="unique_prefixes"):
        glom(d, groups, unique_prefixes=unique_prefixes)
    assert d == {}


@pytest.mark.unit
@pytest.mark.parametrize(
    "unique_prefixes",
    [
        pytest.param(["UBERON"], id="list"),
        pytest.param(("UBERON",), id="tuple"),
        pytest.param({"UBERON"}, id="set"),
        pytest.param(frozenset({"UBERON"}), id="frozenset"),
        pytest.param(dict.fromkeys(["UBERON"]).keys(), id="dict-keys"),
        # A one-shot iterator used to be used up by the first group, leaving every later group in
        # the call unrestricted, so X:1 took UBERON:2 as well.
        pytest.param(iter(["UBERON"]), id="iterator"),
        pytest.param((p for p in ["UBERON"]), id="generator"),
    ],
)
def test_any_non_string_collection_of_prefixes_is_accepted(unique_prefixes):
    """Should accept any non-string collection of prefixes, even a one-shot iterator, and restrict each prefix whole for every group."""
    d = {}
    glom(d, [("UBERON:1", "X:1"), ("UBERON:2", "X:1"), ("U:1", "U:2")], unique_prefixes=unique_prefixes)
    assert d["X:1"] == {"UBERON:1", "X:1"}
    assert d["U:1"] == {"U:1", "U:2"}


@pytest.mark.unit
def test_the_unique_check_counts_distinct_identifiers_across_several_prefixes():
    """Should refuse a merge for whichever restricted prefix it would duplicate, whatever the others hold."""
    d = {}
    glom(
        d,
        [("A:1", "B:1"), ("B:1", "C:1"), ("C:1", "B:2"), ("C:1", "A:2"), ("C:1", "D:1")],
        unique_prefixes=["A", "B", "C"],
    )
    assert d["C:1"] == {"A:1", "B:1", "C:1", "D:1"}
    assert "B:2" not in d and "A:2" not in d


# THE CLOSE GUARD
#
# close maps a prefix to a dict of {identifier: identifiers it must not share a clique with}.
# Disease passes {MONDO: <MONDO_close>} (see diseasephenotype.build_compendium).


@pytest.mark.unit
def test_close_refuses_a_merge_that_brings_in_a_close_partner():
    """Should refuse a merge whose clique would hold an identifier and one of its close partners."""
    close = {"MONDO": defaultdict(set, {"MONDO:1": {"MONDO:2"}})}
    d = {}
    glom(d, [("MONDO:1", "UMLS:1"), ("UMLS:1", "MONDO:2"), ("UMLS:1", "HP:1")], unique_prefixes=[], close=close)
    assert d["UMLS:1"] == {"MONDO:1", "UMLS:1", "HP:1"}
    assert "MONDO:2" not in d


@pytest.mark.unit
def test_close_applies_to_identifiers_without_the_prefix():
    """Should refuse a partner of any prefix: the prefix only selects which members' partners are looked up."""
    close = {"MONDO": defaultdict(set, {"MONDO:1": {"UMLS:9"}})}
    d = {}
    glom(d, [("MONDO:1", "UMLS:9")], unique_prefixes=[], close=close)
    assert d == {}


@pytest.mark.unit
def test_quirk_close_matches_prefixes_with_startswith():
    """Quirk: should apply a close map keyed "MONDO" to any identifier starting with "MONDO", such as "MONDOX:1"."""
    close = {"MONDO": defaultdict(set, {"MONDOX:1": {"X:1"}})}
    d = {}
    glom(d, [("MONDOX:1", "X:1")], unique_prefixes=[], close=close)
    assert d == {}


@pytest.mark.unit
def test_quirk_a_defaultdict_close_map_gains_an_entry_for_every_member_looked_up():
    """Quirk: should insert an empty entry into the caller's defaultdict for each prefixed member it checks.

    glom() looks partners up by index, so the close map passed in grows as a side effect -- even for a
    group the unique_prefixes check had not refused but the close guard then does.
    """
    close = {"MONDO": defaultdict(set, {"MONDO:1": {"X:1"}})}
    glom({}, [("MONDO:1", "X:1"), ("MONDO:2", "Y:1")], unique_prefixes=[], close=close)
    assert dict(close["MONDO"]) == {"MONDO:1": {"X:1"}, "MONDO:2": set()}


@pytest.mark.unit
def test_quirk_a_plain_dict_close_map_raises_on_an_unlisted_identifier():
    """Quirk: should raise KeyError when a member has the prefix but no entry, so callers pass a defaultdict."""
    with pytest.raises(KeyError):
        glom({}, [("MONDO:1", "X:1")], unique_prefixes=[], close={"MONDO": {}})


# FORBIDDEN PREFIXES


@pytest.mark.unit
@pytest.mark.parametrize("curie", ["KEGG:C00001", "PUBCHEM:962"])
def test_a_bare_kegg_or_pubchem_prefix_raises(curie):
    """Should raise on the ambiguous bare KEGG and PUBCHEM prefixes, which no source should still emit."""
    with pytest.raises(Exception, match="garbage"):
        glom({}, [(curie, "X:1")], unique_prefixes=[])


@pytest.mark.unit
def test_the_forbidden_prefix_check_runs_before_the_unique_check():
    """Should raise even on a pair the unique_prefixes check would have refused anyway."""
    d = {}
    glom(d, [("A:1", "X:1")], unique_prefixes=["A"])
    with pytest.raises(Exception, match="garbage"):
        glom(d, [("X:1", "A:2"), ("PUBCHEM:1", "A:3")], unique_prefixes=["A"])


@pytest.mark.unit
def test_dotted_kegg_and_pubchem_prefixes_are_fine():
    """Should accept KEGG.COMPOUND and PUBCHEM.COMPOUND: only the exact bare prefixes are forbidden."""
    d = {}
    glom(d, [("KEGG.COMPOUND:C00001", "PUBCHEM.COMPOUND:962")], unique_prefixes=[])
    assert d["KEGG.COMPOUND:C00001"] == {"KEGG.COMPOUND:C00001", "PUBCHEM.COMPOUND:962"}


# UNUSED PARAMETERS


@pytest.mark.unit
def test_quirk_pref_changes_nothing():
    """Quirk: should ignore pref, which is read only by code that no longer runs."""
    pairs = [("A:1", "B:1"), ("B:1", "A:2"), ("C:1", "B:1")]
    with_hp, with_other = {}, {}
    glom(with_hp, pairs, unique_prefixes=["A"], pref="HP")
    glom(with_other, pairs, unique_prefixes=["A"], pref="A")
    assert with_hp == with_other


# REFERENCE MODEL

FORBIDDEN_PREFIXES = {"KEGG", "PUBCHEM"}


def reference_glom(cliques, groups, unique_prefixes, close):
    """The whole glom() contract, as plainly as it can be written. Not used outside these tests.

    For each group of at most two identifiers, in order: take the union of the group and every
    clique already holding one of its members. Raise if any identifier in it has a bare KEGG or
    PUBCHEM prefix. Skip the group -- adding nothing -- if the union holds two identifiers with the
    same prefix from unique_prefixes, or an identifier and one of its close partners. Otherwise make
    the union the clique of every member. Before any group, raise ValueError unless unique_prefixes
    is a non-string, non-bytes, non-mapping iterable of non-empty prefix strings without a colon; it
    is read once, so a one-shot iterator restricts every group.

    Close partners are looked up by index for every member of the union with a close prefix, even
    once one has refused the group, because glom() does: so a plain-dict close map raises KeyError
    on a member it doesn't list, and a defaultdict one gains an empty entry for each member looked up.
    """
    if isinstance(unique_prefixes, (str, bytes, bytearray, dict)) or not hasattr(unique_prefixes, "__iter__"):
        raise ValueError(unique_prefixes)
    unique_prefixes = list(unique_prefixes)
    if not all(isinstance(prefix, str) and prefix and ":" not in prefix for prefix in unique_prefixes):
        raise ValueError(unique_prefixes)
    if close is None:
        close = {}
    for group in groups:
        if len(group) > 2:
            raise ValueError(group)
        merged = set(group)
        for member in group:
            merged |= cliques.get(member, set())
        if any(member.split(":")[0] in FORBIDDEN_PREFIXES for member in merged):
            raise Exception("garbage")
        if any(len({m for m in merged if m.split(":")[0] == prefix}) > 1 for prefix in unique_prefixes):
            continue
        refused = False
        for close_prefix, partners in close.items():
            for member in merged:
                if member.startswith(close_prefix) and partners[member] & merged:
                    refused = True
        if refused:
            continue
        for member in merged:
            cliques[member] = merged


# Every container a builder has handed glom() a group in. A self-pair is one element as a set but
# two as a tuple or list, so the container is drawn independently of the members.
GROUP_CONTAINERS = (tuple, tuple, tuple, list, set, frozenset)


def random_groups(rng, forbidden=False):
    """Random groups over a few small namespaces, dense enough to collide often.

    Mostly pairs, with singletons, self-pairs and the odd empty group, each in a random container
    from GROUP_CONTAINERS. With ``forbidden``, about one group in forty names a bare KEGG or PUBCHEM
    identifier, so the sequence usually raises partway through.
    """
    identifiers = [f"{prefix}:{n}" for prefix in ("A", "B", "C", "MONDO") for n in range(6)]
    groups = []
    for _ in range(rng.randrange(1, 40)):
        roll = rng.random()
        if roll < 0.03:
            members = []
        elif roll < 0.08:
            members = [rng.choice(identifiers)] * 2
        else:
            members = rng.sample(identifiers, rng.choice((1, 2, 2, 2)))
        if forbidden and members and rng.random() < 0.025:
            members[-1] = f"{rng.choice(sorted(FORBIDDEN_PREFIXES))}:{rng.randrange(6)}"
        groups.append(rng.choice(GROUP_CONTAINERS)(members))
    return groups


# Every form unique_prefixes is drawn in: the containers callers pass, and a one-shot iterator, which
# the first group used to use up. Each builds a fresh value, so glom() and the model never share one.
UNIQUE_PREFIX_CONTAINERS = (list, list, list, tuple, set, frozenset, iter, lambda prefixes: (p for p in prefixes))
# Malformed forms, each of which must make both implementations raise ValueError before any group.
MALFORMED_UNIQUE_PREFIX_BUILDERS = (
    lambda prefixes: "".join(prefixes) or "A",
    lambda prefixes: None,
    lambda prefixes: [f"{p}:" for p in prefixes] or [":"],
)


def random_unique_prefixes_builder(rng):
    """A function turning a prefix list into a unique_prefixes value: one in twenty-five is malformed."""
    if rng.random() < 0.04:
        return rng.choice(MALFORMED_UNIQUE_PREFIX_BUILDERS)
    return rng.choice(UNIQUE_PREFIX_CONTAINERS)


def run_and_catch(fn, *args, **kwargs):
    """Call fn, returning the exception type it raised (or None), so two implementations' failures compare."""
    try:
        fn(*args, **kwargs)
    except Exception as err:
        return type(err)
    return None


@pytest.mark.unit
@pytest.mark.parametrize("seed", range(300))
def test_glom_matches_the_reference_model(seed):
    """Should build exactly the cliques the reference model does, over random groups, unique prefixes and close maps.

    The groups come in every container builders use, and some sequences hit a forbidden prefix
    partway through, or an unlisted MONDO member of a plain-dict close map: then both must raise,
    with the same cliques left behind. Both must also leave the close map in the same state.
    unique_prefixes comes in every accepted form, a one-shot iterator included, and is occasionally
    malformed, when both must raise before merging anything.
    """
    rng = random.Random(seed)
    groups = random_groups(rng, forbidden=True)
    # Usually one unique_prefixes for both calls, as most builders do; otherwise a second draw, so
    # the second call meets cliques the first left over its limit, which only a looser earlier call
    # can produce (test_a_clique_already_over_the_limit_refuses_every_later_merge).
    first_uniques = rng.sample(["A", "B", "MONDO"], rng.randrange(0, 4))
    second_uniques = first_uniques if rng.random() < 0.5 else rng.sample(["A", "B", "MONDO"], rng.randrange(0, 4))
    # Builders pass a defaultdict (diseasephenotype.build_compendium); one case in ten passes a plain
    # dict instead, which raises KeyError on the first MONDO member it doesn't list
    # (test_quirk_a_plain_dict_close_map_raises_on_an_unlisted_identifier).
    close_map = defaultdict(set) if rng.random() < 0.9 else {}
    for n in rng.sample(range(6), rng.randrange(0, 4)):
        close_map[f"MONDO:{n}"] = {f"{rng.choice('ABC')}:{rng.randrange(6)}", f"MONDO:{rng.randrange(6)}"}
    # Each side gets its own copy up front, so neither sees the entries the other inserts.
    close = {"MONDO": copy.deepcopy(close_map)}
    expected_close = {"MONDO": copy.deepcopy(close_map)}

    # Split into two calls, as builders do (ids files, then concords), so state carried between
    # calls is covered too. A forbidden identifier raises; both must raise the same way at the same
    # group, leaving the same partial state behind (glom() has no rollback), and stop there.
    cut = rng.randrange(len(groups) + 1)
    actual, expected = {}, {}
    for part, uniques in ((groups[:cut], first_uniques), (groups[cut:], second_uniques)):
        build = random_unique_prefixes_builder(rng)
        raised = run_and_catch(glom, actual, part, unique_prefixes=build(uniques), close=close)
        expected_raised = run_and_catch(reference_glom, expected, part, build(uniques), expected_close)
        assert raised == expected_raised
        if raised is not None:
            break

    assert actual == expected
    assert close == expected_close  # Including the empty entries a defaultdict gains.
    for key, members in actual.items():
        assert all(actual[member] is members for member in members), key


@pytest.mark.unit
@pytest.mark.parametrize("seed", range(50))
def test_without_restrictions_the_result_is_the_connected_components(seed):
    """Should, with no unique prefixes or close map, build the graph's connected components in any order.

    Order only matters once a merge can be refused; without restrictions glom() is plain union-find.
    """
    rng = random.Random(seed)
    groups = random_groups(rng)

    # Connected components, computed independently of glom().
    neighbours = defaultdict(set)
    for group in groups:
        for member in group:
            neighbours[member].update(group)
    components, seen = set(), set()
    for start in neighbours:
        if start in seen:
            continue
        component, frontier = set(), [start]
        while frontier:
            node = frontier.pop()
            if node not in component:
                component.add(node)
                frontier.extend(neighbours[node] - component)
        seen |= component
        components.add(frozenset(component))

    for _ in range(3):
        rng.shuffle(groups)
        d = {}
        glom(d, groups, unique_prefixes=[])
        assert partition(d) == components
