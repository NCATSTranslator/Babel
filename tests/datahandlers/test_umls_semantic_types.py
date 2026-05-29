"""Tests for the unified UMLS semantic-type -> Biolink-class registry.

Three concerns:

1. **No accidental drift** -- the registry must reproduce the partition maps that used to be
   hardcoded in each ``createcompendia`` module, except for the one intentional change we made
   (Neoplastic Process -> PhenotypicFeature, #111). ``test_category_map_*`` are the golden snapshot.
2. **Overrides are respected** -- ``test_resolver_prefers_registry`` proves the leftover resolver
   returns Babel's registry value over whatever the Biolink Model would say.
3. **Overrides are retired** -- ``test_disagreement_still_needed`` (network) fails (or xfails)
   once the Biolink Model itself adopts our mapping, telling us to delete the registry override.
"""

import pytest

from src.categories import (
    ANATOMICAL_ENTITY,
    BIOLOGICAL_PROCESS,
    CELL,
    CELLULAR_COMPONENT,
    CHEMICAL_ENTITY,
    DISEASE,
    DRUG,
    MOLECULAR_ACTIVITY,
    ORGANISM_TAXON,
    PHENOTYPIC_FEATURE,
    PROTEIN,
)
from src.datahandlers.umls import semantic_types as ust
from src.util import get_biolink_model_toolkit, get_config

BIOLINK_VERSION = get_config()["biolink_version"]

# ---------------------------------------------------------------------------
# Golden snapshots: exactly the umlsmap dicts that lived in each createcompendia module before
# centralization. The ONLY intentional difference is diseasephenotype's B2.2.1.2.1.2 (Neoplastic
# Process), which we deliberately moved Disease -> PhenotypicFeature per #111.
# ---------------------------------------------------------------------------
LEGACY_CATEGORY_MAPS: dict[str, dict[str, str]] = {
    "anatomy": {
        "A1.2": ANATOMICAL_ENTITY,
        "A1.2.1": ANATOMICAL_ENTITY,
        "A1.2.3.1": ANATOMICAL_ENTITY,
        "A1.2.3.2": ANATOMICAL_ENTITY,
        "A2.1.4.1": ANATOMICAL_ENTITY,
        "A2.1.5.1": ANATOMICAL_ENTITY,
        "A2.1.5.2": ANATOMICAL_ENTITY,
        "A1.2.3.3": CELL,
        "A1.2.3.4": CELLULAR_COMPONENT,
    },
    "chemicals": {
        "A1.4.1.1.1.1": CHEMICAL_ENTITY,
        "A1.4.1.1.3.2": CHEMICAL_ENTITY,
        "A1.4.1.1.3.4": CHEMICAL_ENTITY,
        "A1.4.1.1.3.5": CHEMICAL_ENTITY,
        "A1.4.1.1.4": CHEMICAL_ENTITY,
        "A1.4.1.2": CHEMICAL_ENTITY,
        "A1.4.1.2.1": CHEMICAL_ENTITY,
        "A1.4.1.2.1.5": CHEMICAL_ENTITY,
        "A1.4.1.2.2": CHEMICAL_ENTITY,
        "A1.4.1.2.3": CHEMICAL_ENTITY,
        "A1.3.3": DRUG,
    },
    "protein": {
        "A1.4.1.2.1.7": PROTEIN,
        "A1.4.1.1.3.6": PROTEIN,
        "A1.4.1.1.3.3": PROTEIN,
    },
    "diseasephenotype": {
        "B2.2.1.2.1": DISEASE,
        "A1.2.2.1": DISEASE,
        "A1.2.2.2": DISEASE,
        "B2.3": DISEASE,
        "B2.2.1.2": DISEASE,
        "B2.2.1.2.1.1": DISEASE,
        "B2.2.1.2.2": DISEASE,
        "A1.2.2": DISEASE,
        "B2.2.1.2.1.2": DISEASE,  # #111 proposes PhenotypicFeature, but it is not applied yet.
        "A2.2": PHENOTYPIC_FEATURE,
        "A2.2.1": PHENOTYPIC_FEATURE,
        "A2.2.2": PHENOTYPIC_FEATURE,
        "A2.3": PHENOTYPIC_FEATURE,
    },
    "process": {
        "B2.2.1.1.4": MOLECULAR_ACTIVITY,
        "B2.2.1.1": BIOLOGICAL_PROCESS,
        "B2.2.1.1.1": BIOLOGICAL_PROCESS,
        "B2.2.1.1.2": BIOLOGICAL_PROCESS,
        "B2.2.1.1.3": BIOLOGICAL_PROCESS,
        "B2.2.1.1.4.1": BIOLOGICAL_PROCESS,
    },
    "taxon": {
        x: ORGANISM_TAXON
        for x in [
            "A1.1.3",
            "A1.1.2",
            "A1.1.3.3",
            "A1.1.3.2",
            "A1.1.3.1.1.3",
            "A1.1.3.1.1.2",
            "A1.1.4",
            "A1.1.3.1.1.4",
            "A1.1.3.1.1.5",
            "A1.1.3.1.1.1",
            "A1.1.1",
            "A1.1.3.1",
            "A1.1",
            "A1.1.3.1.1",
        ]
    },
}


@pytest.mark.unit
@pytest.mark.parametrize("compendium", sorted(LEGACY_CATEGORY_MAPS))
def test_category_map_matches_legacy(compendium):
    """The registry-derived partition map reproduces the legacy hardcoded map exactly."""
    assert ust.category_map_for(compendium) == LEGACY_CATEGORY_MAPS[compendium]


@pytest.mark.unit
def test_category_map_unknown_compendium_raises():
    with pytest.raises(ValueError):
        ust.category_map_for("not_a_real_compendium")


# ---------------------------------------------------------------------------
# Semantic Network translation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_semantic_network_is_a_bijection():
    trees = [tn for tn, _name in ust.SEMANTIC_NETWORK.values()]
    assert len(trees) == len(set(trees)), "Each TUI must map to a distinct tree number"
    assert len(ust.SEMANTIC_NETWORK) == 127


@pytest.mark.unit
def test_translation_round_trip():
    assert ust.tui_to_tree_number("T191") == "B2.2.1.2.1.2"
    assert ust.tree_number_to_tui("B2.2.1.2.1.2") == "T191"
    assert ust.tree_number_name("A2.2") == "Finding"
    with pytest.raises(ValueError):
        ust.tui_to_tree_number("T999")
    with pytest.raises(ValueError):
        ust.tree_number_to_tui("Z9.9")


# ---------------------------------------------------------------------------
# Overrides are respected by the leftover resolver
# ---------------------------------------------------------------------------


class _ExplodingToolkit:
    """A stand-in toolkit that fails if consulted -- proves the registry short-circuits."""

    def get_element_by_mapping(self, *args, **kwargs):  # noqa: D102
        raise AssertionError("Biolink Model should not be consulted when the registry has the type")


@pytest.mark.unit
def test_resolver_prefers_registry():
    # B2.2.1.2.1.2 (Neoplastic Process, T191) is in the registry as Disease. The resolver must
    # return Babel's registry value without consulting the Biolink Model (which maps it elsewhere).
    result = ust.umls_tree_number_to_biolink_type("B2.2.1.2.1.2", "T191", _ExplodingToolkit())
    assert result == DISEASE


@pytest.mark.unit
def test_resolver_falls_back_to_biolink_for_unregistered_tree():
    # A tree number Babel does not partition (e.g. T071 "Entity", A) is not in the registry, so the
    # resolver must defer to the Biolink Model.
    sentinel = "biolink:SomethingFromBiolink"

    class FakeToolkit:
        def get_element_by_mapping(self, mapping, **kwargs):
            assert mapping == "STY:T071"
            return sentinel

    assert "A" not in ust.UMLS_TYPE_MAP
    assert ust.umls_tree_number_to_biolink_type("A", "T071", FakeToolkit()) == sentinel


# ---------------------------------------------------------------------------
# Registry validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_registry_is_internally_consistent():
    # The real registry must already pass validation (it runs at import, but assert explicitly).
    ust._validate()
    for tree_number, a in ust.UMLS_TYPE_MAP.items():
        assert tree_number in ust._TREE_NUMBER_TO_TUI
        if a.disagrees_with_biolink:
            assert a.issue, f"{tree_number} disagrees with Biolink but has no tracking issue"


@pytest.mark.unit
def test_duplicate_tree_number_rejected():
    dup = [
        ust.UMLSTypeAssignment("A1.2", ANATOMICAL_ENTITY, "anatomy"),
        ust.UMLSTypeAssignment("A1.2", DISEASE, "diseasephenotype"),
    ]
    with pytest.raises(ValueError, match="assigned twice"):
        ust._build_type_map(assignments=dup, overlay={})


@pytest.mark.unit
def test_unknown_biolink_class_rejected():
    bad = {"A1.2": ust.UMLSTypeAssignment("A1.2", "biolink:NotARealClass", "anatomy")}
    with pytest.raises(ValueError, match="not a known src.categories constant"):
        ust._validate(type_map=bad)


@pytest.mark.unit
def test_disagreement_without_issue_rejected():
    bad = {"A1.2": ust.UMLSTypeAssignment("A1.2", ANATOMICAL_ENTITY, "anatomy", proposed_biolink_type=DISEASE)}
    with pytest.raises(ValueError, match="no issue"):
        ust._validate(type_map=bad)


# ---------------------------------------------------------------------------
# Overrides are retired once the Biolink Model adopts them (network)
# ---------------------------------------------------------------------------

DISAGREEMENTS = [a for a in ust.UMLS_TYPE_MAP.values() if a.disagrees_with_biolink]


@pytest.fixture(scope="module")
def biolink_toolkit():
    return get_biolink_model_toolkit(BIOLINK_VERSION)


@pytest.mark.network
def test_there_are_disagreements_to_check():
    # Guards against the parametrized test below silently collecting zero cases.
    assert DISAGREEMENTS, "Expected at least one disagrees_with_biolink entry to track"


@pytest.mark.network
@pytest.mark.parametrize("assignment", DISAGREEMENTS, ids=lambda a: a.tree_number)
def test_disagreement_still_needed(assignment, biolink_toolkit):
    """Fail once the Biolink Model adopts our proposed mapping -- the registry entry is then
    redundant and should be removed."""
    tui = ust.tree_number_to_tui(assignment.tree_number)
    biolink_says = biolink_toolkit.get_element_by_mapping(f"STY:{tui}", most_specific=True, formatted=True, mixin=True)
    redundant = biolink_says == assignment.proposed_biolink_type
    msg = (
        f"Biolink Model {BIOLINK_VERSION} now maps STY:{tui} ({assignment.tree_number}) to our "
        f"proposed {assignment.proposed_biolink_type}; the registry entry is redundant -- remove it "
        f"from src/datahandlers/umls/semantic_types.py. Tracking issue: {assignment.issue}"
    )
    if redundant and assignment.allow_xfail_when_adopted:
        pytest.xfail(msg)
    assert not redundant, msg
