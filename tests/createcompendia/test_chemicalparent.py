"""
Unit tests for src/createcompendia/chemicalparent.py (the ChemicalParent charge-state conflation) and the
conflation ordering it shares with DrugChemical (drugchemical.conflation_member_sort_key()).

InChIKeys and CURIE pairs come from the 2025dec11 build; each is named where it is used. The compendium fixture
``tests/data/chemicalparent/ChemicalEntity-2025dec11-excerpt.txt`` is five lines copied verbatim from that build's
``compendia/ChemicalEntity.txt``: the cliques led by CHEBI:29205, CHEBI:29262, CHEBI:33463 (diphosphonic acid and
its two anions) and CHEBI:58975, CHEBI:58976 (p-azobenzenesulfonic acid and its anion).
"""

import json
from pathlib import Path

import pytest
import yaml

from src.createcompendia import chemicalparent
from src.createcompendia.chemicalparent import (
    build_conflation,
    group_cliques_by_parent_key,
    order_group,
    parent_key_for_clique,
    split_inchikey,
)
from src.createcompendia.drugchemical import (
    MISSING_CLIQUE_IC,
    UNRANKED_PREFIX_ORDER,
    conflation_member_sort_key,
)

FIXTURE = Path(__file__).parent.parent / "data" / "chemicalparent" / "ChemicalEntity-2025dec11-excerpt.txt"

# Real InChIKeys from 2025dec11 (the INCHIKEY member of each named clique).
VALPROIC_ACID = ("CHEBI:39867", "INCHIKEY:NIJJYAXOARWZEE-UHFFFAOYSA-N")
VALPROATE = ("CHEBI:60654", "INCHIKEY:NIJJYAXOARWZEE-UHFFFAOYSA-M")
DEXAMETHASONE = ("CHEBI:41879", "INCHIKEY:UREBDLICKHMUKA-CXSFZGCWSA-N")
BETAMETHASONE = ("CHEBI:3077", "INCHIKEY:UREBDLICKHMUKA-DVTGEIKXSA-N")
D_GLUCOSE = ("CHEBI:17234", "INCHIKEY:GZCGUPFRVQAUEE-SLPGGIOYSA-N")
GALACTOSE = ("CHEBI:17118", "INCHIKEY:GZCGUPFRVQAUEE-KCDKBNATSA-N")

# A hand-made prefix order for ordering tests, so they don't need the Biolink Model (a network fetch).
PREFIX_ORDER = {"CHEBI": 0, "UNII": 1, "PUBCHEM.COMPOUND": 2}


# SPLITTING INCHIKEYS


@pytest.mark.unit
def test_split_inchikey_separates_protonation_block():
    """Valproate's key should split into the parent key (first two blocks) and its protonation character."""
    assert split_inchikey(VALPROATE[1]) == ("NIJJYAXOARWZEE-UHFFFAOYSA", "M")


@pytest.mark.unit
@pytest.mark.parametrize(
    "curie",
    [
        "INCHIKEY:NIJJYAXOARWZEE-UHFFFAOYSA",  # no protonation block
        "INCHIKEY:nijjyaxoarwzee-uhfffaoysa-n",  # lower case
        "INCHIKEY:NIJJYAXOARWZEE-UHFFFAOYSA-N ",  # trailing whitespace
        "CHEBI:39867",  # not an InChIKey
    ],
)
def test_split_inchikey_rejects_malformed(curie):
    """Anything but a well-formed INCHIKEY CURIE should raise rather than be grouped or silently skipped."""
    with pytest.raises(ValueError):
        split_inchikey(curie)


@pytest.mark.unit
def test_parent_key_for_clique_without_inchikey_is_none():
    """A clique with no InChIKey has nothing to group on."""
    assert parent_key_for_clique([]) is None


@pytest.mark.unit
def test_parent_key_for_clique_with_several_structures_is_none():
    """A clique whose InChIKeys have different parent keys holds several structures and should not be grouped."""
    assert parent_key_for_clique([VALPROATE[1], DEXAMETHASONE[1]]) is None


@pytest.mark.unit
def test_parent_key_for_clique_with_several_charge_states_keeps_all_flags():
    """A clique already holding two charge states of one structure should group, carrying both flags."""
    assert parent_key_for_clique([VALPROIC_ACID[1], VALPROATE[1]]) == (
        "NIJJYAXOARWZEE-UHFFFAOYSA",
        frozenset({"N", "M"}),
    )


# GROUPING


@pytest.mark.unit
def test_charge_states_group_together():
    """Valproic acid and valproate (issue #1173) differ only in protonation and should form one group."""
    groups, counts = group_cliques_by_parent_key(
        [(VALPROIC_ACID[0], [VALPROIC_ACID[1]]), (VALPROATE[0], [VALPROATE[1]])]
    )
    assert groups == {"NIJJYAXOARWZEE-UHFFFAOYSA": [(VALPROIC_ACID[0], frozenset("N")), (VALPROATE[0], frozenset("M"))]}
    assert counts["groups"] == 1
    assert counts["cliques_in_groups"] == 2
    assert counts["groups_with_neutral_member"] == 1


@pytest.mark.unit
@pytest.mark.parametrize("pair", [(DEXAMETHASONE, BETAMETHASONE), (D_GLUCOSE, GALACTOSE)])
def test_stereoisomers_never_group(pair):
    """Different drugs sharing a skeleton (dexamethasone/betamethasone, D-glucose/galactose) must stay apart."""
    groups, counts = group_cliques_by_parent_key([(curie, [key]) for curie, key in pair])
    assert groups == {}
    assert counts["groups"] == 0


@pytest.mark.unit
def test_clique_with_several_structures_is_counted_and_left_out():
    """A clique with two parent keys should be skipped and counted, and not join either structure's group."""
    groups, counts = group_cliques_by_parent_key(
        [
            ("MIXED:1", [VALPROATE[1], DEXAMETHASONE[1]]),
            (VALPROIC_ACID[0], [VALPROIC_ACID[1]]),
        ]
    )
    assert groups == {}
    assert counts["cliques_skipped_multiple_parent_keys"] == 1


# ORDERING


@pytest.mark.unit
def test_member_sort_key_orders_by_prefix_then_ic_then_size_then_suffix():
    """Prefix rank should dominate, then lower IC, then larger clique, then smaller numerical suffix."""
    members = {
        "PUBCHEM.COMPOUND:1": (50.0, 10),  # worst prefix, despite best IC
        "CHEBI:9": (90.0, 2),
        "CHEBI:8": (80.0, 2),  # lower IC than CHEBI:9
        "CHEBI:7": (80.0, 5),  # same IC as CHEBI:8, larger clique
        "CHEBI:6": (80.0, 5),  # ties CHEBI:7 except for the smaller suffix
    }
    ordered = sorted(members, key=lambda c: conflation_member_sort_key(c, PREFIX_ORDER, *members[c]))
    assert ordered == ["CHEBI:6", "CHEBI:7", "CHEBI:8", "CHEBI:9", "PUBCHEM.COMPOUND:1"]


@pytest.mark.unit
def test_member_sort_key_puts_unranked_prefixes_and_missing_ic_last():
    """An unranked prefix sorts after every ranked one, and a clique with no IC after every scored one."""
    assert conflation_member_sort_key("NOTAPREFIX:1", PREFIX_ORDER, 1.0, 1)[0] == UNRANKED_PREFIX_ORDER
    assert conflation_member_sort_key("CHEBI:1", PREFIX_ORDER, None, 1) > conflation_member_sort_key(
        "CHEBI:2", PREFIX_ORDER, MISSING_CLIQUE_IC - 1, 1
    )


@pytest.mark.unit
def test_neutral_form_leads_even_when_it_would_otherwise_sort_last():
    """The neutral clique should lead the group even with a worse prefix, higher IC and smaller clique."""
    members = [("CHEBI:1", frozenset("M")), ("PUBCHEM.COMPOUND:2", frozenset("N"))]
    clique_info = {"CHEBI:1": (10.0, 20), "PUBCHEM.COMPOUND:2": (99.0, 1)}
    assert order_group(members, clique_info, PREFIX_ORDER) == ["PUBCHEM.COMPOUND:2", "CHEBI:1"]


@pytest.mark.unit
def test_group_without_neutral_form_uses_drugchemical_order():
    """With no neutral member, the DrugChemical order alone should pick the leader."""
    members = [("PUBCHEM.COMPOUND:2", frozenset("O")), ("CHEBI:1", frozenset("M"))]
    clique_info = {"CHEBI:1": (50.0, 2), "PUBCHEM.COMPOUND:2": (50.0, 2)}
    assert order_group(members, clique_info, PREFIX_ORDER) == ["CHEBI:1", "PUBCHEM.COMPOUND:2"]


# BUILDING FROM COMPENDIA


@pytest.mark.unit
def test_build_conflation_from_real_compendium_lines(tmp_path):
    """The verbatim 2025dec11 lines should give two groups, each led by its neutral acid, in parent-key order."""
    outfile = tmp_path / "conflation" / "ChemicalParent.txt"
    metadata = tmp_path / "metadata" / "ChemicalParent.yaml"
    build_conflation([str(FIXTURE)], PREFIX_ORDER, str(outfile), str(metadata))

    # AJMNDPOSKIBVGX-BUHFOSPRSA sorts before XQRLCLUYWUNEEH-UHFFFAOYSA. Diphosphonate(2-) (CHEBI:29262, -L) and
    # (1-) (CHEBI:33463, -M) tie on prefix, IC and size, so the smaller suffix comes first.
    assert [json.loads(line) for line in outfile.read_text().splitlines()] == [
        ["CHEBI:58975", "CHEBI:58976"],
        ["CHEBI:29205", "CHEBI:29262", "CHEBI:33463"],
    ]
    counts = yaml.safe_load(metadata.read_text())["counts"]
    assert counts == {
        "cliques_with_inchikey": 5,
        "candidate_cliques": 5,
        "groups": 2,
        "cliques_in_groups": 5,
        "groups_with_neutral_member": 2,
    }


@pytest.mark.unit
def test_hash_collisions_do_not_merge_groups(tmp_path, monkeypatch):
    """If every parent key hashed alike, every clique becomes a candidate but the groups must not change."""
    monkeypatch.setattr(chemicalparent, "parent_key_hash", lambda parent_key: 0)
    outfile = tmp_path / "ChemicalParent.txt"
    build_conflation([str(FIXTURE)], PREFIX_ORDER, str(outfile), str(tmp_path / "ChemicalParent.yaml"))
    assert [json.loads(line) for line in outfile.read_text().splitlines()] == [
        ["CHEBI:58975", "CHEBI:58976"],
        ["CHEBI:29205", "CHEBI:29262", "CHEBI:33463"],
    ]


@pytest.mark.unit
def test_inchikey_outside_identifiers_fails_the_build(tmp_path):
    """If the line regex finds an InChIKey the JSON's identifiers don't hold, pass 1 can't be trusted: raise."""
    compendium = tmp_path / "Odd.txt"
    lines = [
        {"type": "biolink:ChemicalEntity", "identifiers": [{"i": "CHEBI:1"}], "extra": {"i": VALPROIC_ACID[1]}},
        {"type": "biolink:ChemicalEntity", "identifiers": [{"i": VALPROATE[0]}, {"i": VALPROATE[1]}]},
    ]
    compendium.write_text("".join(json.dumps(line) + "\n" for line in lines))
    with pytest.raises(RuntimeError, match="pass 1 may have missed cliques"):
        build_conflation([str(compendium)], PREFIX_ORDER, str(tmp_path / "out.txt"), str(tmp_path / "out.yaml"))
