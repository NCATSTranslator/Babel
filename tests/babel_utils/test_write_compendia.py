"""Unit tests for label-selection logic in write_compendium().

The helper under test is choose_preferred_name(), which is the extracted core of
the label-selection algorithm previously embedded in write_compendium().

Issue context:
  https://github.com/NCATSTranslator/Babel/issues/597  — original report: good names demoted
  https://github.com/NCATSTranslator/Babel/issues/714  — MONDO:0011479 "postural orthostatic
      tachycardia syndrome" wrongly demoted to "Irritable heart"
  https://github.com/NCATSTranslator/Babel/issues/711  — HP:0001508 "Failure to thrive"
      wrongly demoted to "Undergrowth"
  https://github.com/NCATSTranslator/Babel/issues/723  — MONDO:0005578 "arthritic joint
      disease" wrongly demoted to "arthritis"
"""

import pytest

from src import categories
from src.babel_utils import choose_preferred_name


def _node(identifiers):
    """Build a minimal node dict from a list of (curie, label_or_None) tuples."""
    ids = []
    for curie, label in identifiers:
        entry = {"identifier": curie}
        if label is not None:
            entry["label"] = label
        ids.append(entry)
    return {"identifiers": ids}


# ---------------------------------------------------------------------------
# Ancestor lists (mirrors what node_factory.get_ancestors() returns)
# ---------------------------------------------------------------------------

DISEASE_ANCESTORS = [
    categories.DISEASE,
    "biolink:DiseaseOrPhenotypicFeature",
    "biolink:BiologicalEntity",
    "biolink:NamedThing",
]

PHENOTYPIC_FEATURE_ANCESTORS = [
    categories.PHENOTYPIC_FEATURE,
    "biolink:DiseaseOrPhenotypicFeature",
    "biolink:BiologicalEntity",
    "biolink:NamedThing",
]

CHEMICAL_ENTITY_ANCESTORS = [
    categories.CHEMICAL_ENTITY,
    "biolink:PhysicalEssence",
    "biolink:NamedThing",
]

SMALL_MOLECULE_ANCESTORS = [
    categories.SMALL_MOLECULE,
    categories.CHEMICAL_ENTITY,
    "biolink:PhysicalEssence",
    "biolink:NamedThing",
]

DRUG_ANCESTORS = [
    categories.DRUG,
    categories.CHEMICAL_ENTITY,
    "biolink:PhysicalEssence",
    "biolink:NamedThing",
]

DEMOTE_CHEMICALS_25 = {categories.CHEMICAL_ENTITY: 25}


# ---------------------------------------------------------------------------
# Regression tests from GitHub issues
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pots_label_not_demoted():
    """MONDO:0011479 — "postural orthostatic tachycardia syndrome" (40 chars) must not be
    demoted to "Irritable heart" (14 chars) for biolink:Disease.
    https://github.com/NCATSTranslator/Babel/issues/714
    """
    node = _node(
        [
            ("MONDO:0011479", "postural orthostatic tachycardia syndrome"),
            ("UMLS:C2930833", "Irritable heart"),
        ]
    )
    result = choose_preferred_name(node, DISEASE_ANCESTORS, {}, DEMOTE_CHEMICALS_25)
    assert result == "postural orthostatic tachycardia syndrome"


@pytest.mark.unit
def test_failure_to_thrive_not_demoted():
    """HP:0001508 — "Failure to thrive" (18 chars) must not be demoted to "Undergrowth"
    (10 chars) for biolink:PhenotypicFeature.
    https://github.com/NCATSTranslator/Babel/issues/711
    """
    node = _node(
        [
            ("HP:0001508", "Failure to thrive"),
            ("UMLS:C4531021", "Undergrowth"),
        ]
    )
    result = choose_preferred_name(node, PHENOTYPIC_FEATURE_ANCESTORS, {}, DEMOTE_CHEMICALS_25)
    assert result == "Failure to thrive"


@pytest.mark.unit
def test_arthritic_joint_disease_not_demoted():
    """MONDO:0005578 — "arthritic joint disease" (22 chars) must not be demoted to
    "arthritis" (9 chars) for biolink:Disease.
    https://github.com/NCATSTranslator/Babel/issues/723
    """
    node = _node(
        [
            ("MONDO:0005578", "arthritic joint disease"),
            ("DOID:848", "arthritis"),
        ]
    )
    result = choose_preferred_name(node, DISEASE_ANCESTORS, {}, DEMOTE_CHEMICALS_25)
    assert result == "arthritic joint disease"


# ---------------------------------------------------------------------------
# Chemical demotion — should still apply
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_chemical_long_iupac_demoted():
    """For biolink:ChemicalEntity, a long IUPAC name should be demoted in favour of a short
    common name when a shorter label is available.
    """
    node = _node(
        [
            ("CHEBI:17334", "(2S)-2-amino-3-hydroxypropanoic acid"),
            ("PUBCHEM.COMPOUND:5951", "serine"),
        ]
    )
    result = choose_preferred_name(node, CHEMICAL_ENTITY_ANCESTORS, {}, DEMOTE_CHEMICALS_25)
    assert result == "serine"


@pytest.mark.unit
def test_chemical_demotion_via_small_molecule_ancestor():
    """Demotion configured on biolink:ChemicalEntity should apply to biolink:SmallMolecule
    (a subtype) via ancestor traversal.
    """
    node = _node(
        [
            ("CHEBI:17234", "(2R,3S,4S,5R)-2,3,4,5,6-pentahydroxyhexanal"),  # very long IUPAC
            ("PUBCHEM.COMPOUND:107526", "glucose"),
        ]
    )
    result = choose_preferred_name(node, SMALL_MOLECULE_ANCESTORS, {}, DEMOTE_CHEMICALS_25)
    assert result == "glucose"


@pytest.mark.unit
def test_chemical_within_limit_not_demoted_via_drug_ancestor():
    """Demotion config reaches biolink:Drug via ancestor traversal, but acetylsalicylic acid
    (20 chars) is within the 25-char limit so no demotion occurs and it is returned first."""
    node = _node(
        [
            ("DRUGBANK:DB00945", "acetylsalicylic acid"),  # 20 chars — within limit
            ("PUBCHEM.COMPOUND:2244", "aspirin"),
        ]
    )
    result = choose_preferred_name(node, DRUG_ANCESTORS, {}, DEMOTE_CHEMICALS_25)
    assert result == "acetylsalicylic acid"


@pytest.mark.unit
def test_chemical_all_labels_long_keeps_first():
    """If all labels exceed the demotion limit, no demotion occurs and the first label is kept."""
    node = _node(
        [
            ("CHEBI:100001", "some-very-long-iupac-name-that-exceeds-the-limit"),
            ("PUBCHEM.COMPOUND:99999", "another-very-long-chemical-name-here"),
        ]
    )
    result = choose_preferred_name(node, CHEMICAL_ENTITY_ANCESTORS, {}, DEMOTE_CHEMICALS_25)
    assert result == "some-very-long-iupac-name-that-exceeds-the-limit"


# ---------------------------------------------------------------------------
# Empty / no-config cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_demotion_when_config_is_empty():
    """When demote_labels_longer_than is an empty dict, no demotion occurs for any type."""
    node = _node(
        [
            ("CHEBI:17334", "(2S)-2-amino-3-hydroxypropanoic acid"),
            ("PUBCHEM.COMPOUND:5951", "serine"),
        ]
    )
    result = choose_preferred_name(node, CHEMICAL_ENTITY_ANCESTORS, {}, {})
    assert result == "(2S)-2-amino-3-hydroxypropanoic acid"


@pytest.mark.unit
def test_no_labels_returns_empty_string():
    """A node with no labels should return an empty string."""
    node = _node([("MONDO:0000001", None)])
    result = choose_preferred_name(node, DISEASE_ANCESTORS, {}, DEMOTE_CHEMICALS_25)
    assert result == ""


# ---------------------------------------------------------------------------
# Interaction between boost prefixes and demotion
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_boost_prefix_then_demotion():
    """preferred_name_boost_prefixes reorders labels; demotion then filters by length.
    DRUGBANK is boosted for ChemicalEntity, so a long DRUGBANK label is moved to the front —
    but demotion should then skip it in favour of the shorter alternative.
    """
    boost = {categories.CHEMICAL_ENTITY: ["DRUGBANK", "CHEBI"]}
    node = _node(
        [
            ("CHEBI:27899", "cisplatin"),  # 9 chars — short, not boosted first
            ("DRUGBANK:DB00515", "cis-diaminedichloroplatinum(II)"),  # 31 chars — boosted first but too long
        ]
    )
    result = choose_preferred_name(node, CHEMICAL_ENTITY_ANCESTORS, boost, DEMOTE_CHEMICALS_25)
    assert result == "cisplatin"
