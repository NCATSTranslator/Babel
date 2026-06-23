"""
Tests for the manual UMLS semantic-type overrides used when building the leftover UMLS compendium
(src/createcompendia/leftover_umls.py).

These are marked ``network`` because they build a Biolink Model Toolkit, which fetches
``biolink-model.yaml`` from GitHub on first use (for the biolink_version pinned in config.yaml).
"""

import pytest

from src.categories import ACTIVITY, COHORT, DRUG, PHENOMENON, PHYSICAL_ENTITY
from src.createcompendia.leftover_umls import (
    STY_OVERRIDES,
    TYPE_COMBO_OVERRIDES,
    DuplicateUmlsTracker,
    apply_generic_demotion,
    summarize_compendium_umls_by_semantic_type,
    tui_to_biolink_type,
    writable_output_types,
)
from src.node import NodeFactory
from src.prefixes import UMLS
from src.util import get_biolink_model_toolkit, get_config

BIOLINK_VERSION = get_config()["biolink_version"]

# The Biolink type that bmt currently assigns to each overridden UMLS semantic type (STY:<code>),
# recorded when the override was added, for the biolink_version pinned in config.yaml. Only the STY
# mappings are recorded -- that is all the drift check needs. If the live Biolink mapping diverges
# from these, the override must be re-reviewed; if it has come to equal the override, the override is
# redundant and can be removed.
RECORDED_STY_BASELINE: dict[str, str | None] = {
    "T033": None,  # https://github.com/NCATSTranslator/Babel/issues/569 -- "Finding": Biolink has no STY mapping.
    "T034": PHENOMENON,  # https://github.com/NCATSTranslator/Babel/issues/569 -- "Laboratory or Test Result".
    "T058": ACTIVITY,  # https://github.com/NCATSTranslator/Babel/issues/90 -- "Health Care Activity".
    "T045": None,  # https://github.com/NCATSTranslator/Babel/issues/421 -- "Genetic Function": no STY mapping.
    "T021": None,  # https://github.com/NCATSTranslator/Babel/issues/421 -- "Fully Formed Anatomical Structure": no STY mapping.
    "T120": None,  # https://github.com/NCATSTranslator/Babel/issues/421 -- "Chemical Viewed Functionally": no STY mapping.
    "T122": None,  # https://github.com/NCATSTranslator/Babel/issues/421 -- "Biomedical or Dental Material": no STY mapping.
    "T168": None,  # https://github.com/NCATSTranslator/Babel/issues/421 -- "Food": no STY mapping.
    "T090": None,  # https://github.com/NCATSTranslator/Babel/issues/817 -- "Occupation or Discipline": no STY mapping.
    "T091": None,  # https://github.com/NCATSTranslator/Babel/issues/817 -- "Biomedical Occupation or Discipline": no STY mapping.
    "T097": COHORT,  # https://github.com/NCATSTranslator/Babel/issues/817 -- "Professional or Occupational Group": bmt maps to Cohort, overridden to PopulationOfIndividualOrganisms for consistency.
    "T072": PHYSICAL_ENTITY,  # https://github.com/NCATSTranslator/Babel/issues/840 -- "Physical Object": kept as PhysicalEntity (writable via extra_prefixes=[UMLS]).
    "T073": PHYSICAL_ENTITY,  # https://github.com/NCATSTranslator/Babel/issues/840 -- "Manufactured Object": kept as PhysicalEntity (writable via extra_prefixes=[UMLS]).
}

# STY codes whose override is intentionally pinned to the raw Biolink mapping (rather than correcting
# it). For these the drift test must NOT treat "override == live Biolink mapping" as redundant: we
# keep the explicit entry so the type participates in GENERIC_TYPES demotion in leftover_umls.py.
INTENTIONAL_BIOLINK_PINS: frozenset[str] = frozenset({"T072", "T073"})


@pytest.mark.network
def test_recorded_baseline_covers_all_overrides():
    """Every STY override must record a baseline, otherwise drift cannot be detected for it."""
    missing = set(STY_OVERRIDES) - set(RECORDED_STY_BASELINE)
    assert not missing, f"STY_OVERRIDES entries missing from RECORDED_STY_BASELINE: {sorted(missing)}"


@pytest.mark.network
def test_sty_overrides_have_not_drifted():
    """
    Hard-fail when the live Biolink STY mapping no longer matches the recorded baseline (Biolink
    changed underneath us, so the override must be re-reviewed). Warn -- but do not fail -- when
    Biolink has come to agree with the override, since the override is then redundant.
    """
    toolkit = get_biolink_model_toolkit(BIOLINK_VERSION)
    for tui, override in STY_OVERRIDES.items():
        current = tui_to_biolink_type(tui, toolkit=toolkit)
        baseline = RECORDED_STY_BASELINE[tui]
        if tui in INTENTIONAL_BIOLINK_PINS:
            # We deliberately pin these to the Biolink value, so "override == live mapping" is
            # expected, not redundant. Check both that Biolink hasn't drifted from the baseline
            # and that the override itself still matches the baseline (guards against accidental
            # changes to STY_OVERRIDES that would silently break the pin).
            assert current == baseline, (
                f"Biolink STY:{tui} now maps to {current!r}, but the recorded baseline is {baseline!r}. "
                f"Re-review the intentional pin (currently {override!r}) and update RECORDED_STY_BASELINE."
            )
            assert override == baseline, (
                f"STY_OVERRIDES[{tui!r}] is {override!r} but an intentional pin must match the Biolink "
                f"baseline {baseline!r}. Restore the override or remove {tui!r} from INTENTIONAL_BIOLINK_PINS."
            )
            continue
        if current == override:
            pytest.fail(
                f"Biolink STY:{tui} now maps to {current!r}, which equals the manual override. "
                f"Fix: delete the STY_OVERRIDES[{tui!r}] entry and its RECORDED_STY_BASELINE entry."
            )
        else:
            assert current == baseline, (
                f"Biolink STY:{tui} now maps to {current!r}, but the recorded baseline is {baseline!r}. "
                f"Re-review the override (currently {override!r}) and update RECORDED_STY_BASELINE."
            )


@pytest.mark.network
def test_type_combo_overrides_reference_real_biolink_classes():
    """Every Biolink type named in TYPE_COMBO_OVERRIDES must be a real class in the pinned model."""
    toolkit = get_biolink_model_toolkit(BIOLINK_VERSION)
    referenced = set()
    for combo, value in TYPE_COMBO_OVERRIDES.items():
        referenced.update(combo)
        referenced.add(value)
    for biolink_type in sorted(referenced):
        assert toolkit.get_element(biolink_type) is not None, (
            f"{biolink_type} is not a class in Biolink {BIOLINK_VERSION}"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "input_types, expected",
    [
        # Generic type alongside a specific type: generic is dropped.
        ({PHYSICAL_ENTITY, DRUG}, {DRUG}),
        # Generic type alone: kept as-is (no specific co-type to prefer).
        ({PHYSICAL_ENTITY}, {PHYSICAL_ENTITY}),
        # Two non-generic types: demotion does not fire.
        ({DRUG, PHENOMENON}, {DRUG, PHENOMENON}),
        # Single non-generic type: unchanged.
        ({DRUG}, {DRUG}),
    ],
)
def test_generic_types_demotion(input_types, expected):
    """GENERIC_TYPES are dropped when a more specific co-type is present; kept when alone."""
    assert apply_generic_demotion(input_types) == expected


@pytest.mark.network
def test_all_override_target_types_are_writable():
    """
    Reproduces the production failure in seconds: every Biolink type the leftover UMLS rule can emit
    from its manual override tables must be writable by NodeFactory.create_node() when the rule's
    extra_prefixes=[UMLS] is supplied. Some of these (e.g. biolink:Phenomenon, biolink:PhysicalEntity)
    have no id_prefixes of their own; before the fix these raised "No Biolink prefixes for ..." deep
    inside write_compendium() after a ~5h HPC run. create_node() with empty identifiers exercises the
    same get_prefixes() call and then returns None without touching any labels or files.
    """
    factory = NodeFactory(label_dir=None, biolink_version=BIOLINK_VERSION)
    for output_type in sorted(writable_output_types()):
        # Must not raise. (Returns None because input_identifiers is empty.)
        factory.create_node(input_identifiers=[], node_type=output_type, labels={}, extra_prefixes=[UMLS])


@pytest.mark.unit
def test_summarize_compendium_umls_by_semantic_type():
    """The per-compendium breakdown: unique CURIE counts, single-clique attribution, bucketing by
    (Biolink type, most-specific TUI set), the filename fallback type, and the per-CURIE occurrence
    map. Offline -- semantic_key is a stub, so no Biolink/MRSTY access is needed."""
    # Stub semantic_key: a fixed CURIE -> most-specific TUI set mapping.
    tuis_by_curie = {
        "UMLS:C1": frozenset({"T047"}),
        "UMLS:C2": frozenset({"T047"}),
        "UMLS:C3": frozenset({"T047", "T191"}),
        "UMLS:C4": frozenset(),  # no MRSTY entry
    }

    def semantic_key(curie):
        return tuis_by_curie[curie]

    clusters = [
        # Single-identifier UMLS-only clique -> counts as a single clique.
        {"type": "biolink:Disease", "preferred_name": "C1", "identifiers": [{"i": "UMLS:C1", "l": "c1"}]},
        # C2 sits with a non-UMLS partner -> not a single UMLS clique. C1 reappears (deduped).
        {
            "type": "biolink:Disease",
            "identifiers": [{"i": "UMLS:C1", "l": "c1"}, {"i": "MESH:D2", "l": "m2"}, {"i": "UMLS:C2", "l": "c2"}],
        },
        # Multi-TUI concept, single clique.
        {"type": "biolink:Disease", "identifiers": [{"i": "UMLS:C3", "l": "c3"}]},
        # Untyped concept (no "type"): falls back to the supplied filename type. Label missing.
        {"identifiers": [{"i": "UMLS:C4"}]},
    ]

    breakdown, occ_by_curie = summarize_compendium_umls_by_semantic_type(
        clusters, semantic_key, fallback_biolink_type="biolink:Disease"
    )

    assert set(occ_by_curie.keys()) == {"UMLS:C1", "UMLS:C2", "UMLS:C3", "UMLS:C4"}
    # Each occurrence is (biolink_type, clique_leader, preferred_name, label). C1 is in two Disease
    # cliques both led by UMLS:C1, so it has a single distinct (biolink_type, leader) membership.
    assert {(occ[0], occ[1]) for occ in occ_by_curie["UMLS:C1"]} == {("biolink:Disease", "UMLS:C1")}
    # C4 picked up the fallback type because its clique had no "type" field.
    assert occ_by_curie["UMLS:C4"] == {("biolink:Disease", "UMLS:C4", "", "")}

    # ("biolink:Disease", {T047}): C1 (single) + C2 (not single) = 2 CURIEs, 1 single.
    count, single, samples = breakdown[("biolink:Disease", frozenset({"T047"}))]
    assert count == 2
    assert single == 1
    assert sorted(samples) == [("UMLS:C1", "c1"), ("UMLS:C2", "c2")]

    # ("biolink:Disease", {T047, T191}): just C3, in a single clique.
    assert breakdown[("biolink:Disease", frozenset({"T047", "T191"}))] == [1, 1, [("UMLS:C3", "c3")]]

    # Empty set (untyped), fallback Biolink type: C4, missing label rendered as "".
    assert breakdown[("biolink:Disease", frozenset())] == [1, 1, [("UMLS:C4", "")]]

    # Per-compendium total is reproduced by summing curie_count over buckets.
    assert sum(entry[0] for entry in breakdown.values()) == len(occ_by_curie)


@pytest.mark.unit
def test_summarize_compendium_umls_splits_by_biolink_type():
    """A CURIE that appears under two Biolink types is counted once per type (one bucket each)."""
    clusters = [
        {"type": "biolink:Drug", "identifiers": [{"i": "UMLS:C1", "l": "c1"}]},
        {"type": "biolink:ChemicalEntity", "identifiers": [{"i": "UMLS:C1", "l": "c1"}]},
    ]
    breakdown, occ_by_curie = summarize_compendium_umls_by_semantic_type(
        clusters, lambda curie: frozenset({"T047"}), fallback_biolink_type="biolink:ChemicalEntity"
    )
    assert breakdown[("biolink:Drug", frozenset({"T047"}))] == [1, 1, [("UMLS:C1", "c1")]]
    assert breakdown[("biolink:ChemicalEntity", frozenset({"T047"}))] == [1, 1, [("UMLS:C1", "c1")]]
    # The CURIE records a distinct occurrence under each Biolink type.
    assert len(occ_by_curie["UMLS:C1"]) == 2


@pytest.mark.unit
def test_summarize_compendium_umls_caps_samples():
    """Samples are capped at the module sample limit even when a bucket has many CURIEs."""
    from src.createcompendia.leftover_umls import _SAMPLE_LIMIT

    n = _SAMPLE_LIMIT + 4
    clusters = [{"type": "biolink:Disease", "identifiers": [{"i": f"UMLS:C{i}", "l": f"c{i}"}]} for i in range(n)]
    breakdown, occ_by_curie = summarize_compendium_umls_by_semantic_type(
        clusters, lambda curie: frozenset({"T047"}), fallback_biolink_type="biolink:Disease"
    )
    count, single, samples = breakdown[("biolink:Disease", frozenset({"T047"}))]
    assert count == n
    assert single == n
    assert len(samples) == _SAMPLE_LIMIT


@pytest.mark.unit
def test_duplicate_umls_tracker():
    """DuplicateUmlsTracker flags cross-file and within-file duplicate UMLS CURIEs and nothing else."""
    tracker = DuplicateUmlsTracker()

    # Seen once -> not a duplicate, but is a member.
    tracker.record("UMLS:C1", "Disease.txt", "biolink:Disease", "UMLS:C1", "C1", "c1")
    # Re-seen in the *same* clique (e.g. another MRCONSO row) -> still not a duplicate.
    tracker.record("UMLS:C1", "Disease.txt", "biolink:Disease", "UMLS:C1", "C1", "c1")

    # Cross-file: same CURIE in two different compendium files.
    tracker.record("UMLS:C2", "Disease.txt", "biolink:Disease", "MONDO:1", "d", "lbl")
    tracker.record("UMLS:C2", "ChemicalEntity.txt", "biolink:ChemicalEntity", "CHEBI:1", "c", "lbl")

    # Within-file: same CURIE in two distinct cliques of one file (different leaders).
    tracker.record("UMLS:C3", "Disease.txt", "biolink:Disease", "MONDO:2", "x", "lbl")
    tracker.record("UMLS:C3", "Disease.txt", "biolink:Disease", "MONDO:3", "y", "lbl")

    # Both: cross-file *and* within-file.
    tracker.record("UMLS:C4", "Disease.txt", "biolink:Disease", "MONDO:4", "p", "lbl")
    tracker.record("UMLS:C4", "Disease.txt", "biolink:Disease", "MONDO:5", "q", "lbl")
    tracker.record("UMLS:C4", "PhenotypicFeature.txt", "biolink:PhenotypicFeature", "HP:1", "r", "lbl")

    # Membership and count cover every CURIE seen, duplicate or not.
    assert "UMLS:C1" in tracker
    assert "UMLS:C9" not in tracker
    assert len(tracker) == 4

    dups = {curie: scope for curie, _occ, scope in tracker.duplicates()}
    assert dups == {
        "UMLS:C2": "cross-file",
        "UMLS:C3": "within-file",
        "UMLS:C4": "both",
    }

    # duplicates() is sorted by CURIE.
    assert [curie for curie, _occ, _scope in tracker.duplicates()] == ["UMLS:C2", "UMLS:C3", "UMLS:C4"]

    # Occurrences are de-duped by (compendium, leader): C4 has 3 distinct cliques.
    occ_by_curie = {curie: occ for curie, occ, _scope in tracker.duplicates()}
    assert len({(o[0], o[2]) for o in occ_by_curie["UMLS:C4"]}) == 3
