"""Regression checks for the disease/phenotype compendium.

Four kinds of assertions live here, each backed by its own per-issue table:

  EXPECTED_IN_DISEASE / NOT_IN_DISEASE
    -- ID-presence checks: is a CURIE in the disease intermediate ID files?
    -- Depends on `disease_id_pipeline_outputs`; uses Snakemake to materialise
       any missing disease/ids/<VOCAB> files.

  EXPECTED_XREF / EXPECTED_NO_XREF
    -- Direct cross-reference checks: are two CURIEs a direct xref pair in any
       disease concord file?
    -- Only *direct* xref pairs are checked.  For multi-hop equivalences use
       the clique checks below instead.

  CLIQUE_CHECKS
    -- Same-equivalence-class checks: after full glom over all available disease
       concord files (including indirect / multi-hop chains), do two CURIEs land
       in the same clique?  This is the assertion that catches the case
       direct-xref checks miss.

  LABEL_CHECKS
    -- Final-label checks: simulate write_compendium's label-selection step for a
       CURIE's clique and assert the chosen label matches an expected string.
       Uses the same NodeFactory.create_node() + _select_preferred_label() path
       write_compendium would use.

Each entry is a NamedTuple that includes the GitHub issue URL that motivated the
check.  Append a new tuple to the appropriate list to add a new regression check.

Run:
    uv run pytest tests/pipeline/checks/test_disease.py --pipeline --no-cov -v
"""
from typing import NamedTuple

import pytest

from tests.pipeline.conftest import _any_concord_xrefs, _read_ids_with_types, simulate_label

# ---------------------------------------------------------------------------
# Check types
# ---------------------------------------------------------------------------


class DiseaseCheck(NamedTuple):
    curie: str
    expected_type: str   # Biolink type used in failure messages; also asserted against
                         # the second column of the intermediate file if present.
    issue: str


class ConcordCheck(NamedTuple):
    curie1: str
    curie2: str
    should_xref: bool    # True = must be a direct xref pair; False = must NOT be
    issue: str


class CliqueCheck(NamedTuple):
    curie1: str
    curie2: str
    same_clique: bool    # True = must land in the same clique after full glom
    issue: str


class LabelCheck(NamedTuple):
    curie: str
    expected_label: str
    biolink_type: str    # The compendium's biolink type, e.g. biolink:Disease
    issue: str


# ---------------------------------------------------------------------------
# Per-issue check tables
# ---------------------------------------------------------------------------


EXPECTED_IN_DISEASE: list[DiseaseCheck] = []
NOT_IN_DISEASE:    list[DiseaseCheck] = []

EXPECTED_XREF:     list[ConcordCheck] = []
EXPECTED_NO_XREF:  list[ConcordCheck] = []

CLIQUE_CHECKS: list[CliqueCheck] = [
    CliqueCheck(
        "MONDO:0011479",
        "UMLS:C2930833",
        True,
        "https://github.com/NCATSTranslator/Babel/issues/714",
    ),
]

LABEL_CHECKS: list[LabelCheck] = [
    LabelCheck(
        "MONDO:0011479",
        "postural orthostatic tachycardia syndrome",
        "biolink:Disease",
        "https://github.com/NCATSTranslator/Babel/issues/714",
    ),
    LabelCheck(
        "HP:0001508",
        "Failure to thrive",
        "biolink:PhenotypicFeature",
        "https://github.com/NCATSTranslator/Babel/issues/711",
    ),
    LabelCheck(
        "MONDO:0005578",
        "arthritic joint disease",
        "biolink:Disease",
        "https://github.com/NCATSTranslator/Babel/issues/723",
    ),
]


# ---------------------------------------------------------------------------
# Tests: ID presence
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
@pytest.mark.parametrize("check", EXPECTED_IN_DISEASE, ids=[c.curie for c in EXPECTED_IN_DISEASE] or None)
def test_curie_in_disease(disease_id_pipeline_outputs, check) -> None:
    """CURIE must appear in at least one disease intermediate ID file."""
    if not isinstance(check, DiseaseCheck):
        pytest.skip("EXPECTED_IN_DISEASE is empty -- add entries to activate this test")
    for vocab, path in disease_id_pipeline_outputs.items():
        ids = _read_ids_with_types(path)
        if check.curie in ids:
            actual_type = ids[check.curie]
            if actual_type is not None and actual_type != check.expected_type:
                raise AssertionError(
                    f"{check.curie} found in disease/{vocab} but type mismatch: "
                    f"expected {check.expected_type}, got {actual_type} (see {check.issue})"
                )
            return
    raise AssertionError(
        f"{check.curie} not found in any disease ID file "
        f"(expected type {check.expected_type}; see {check.issue})"
    )


@pytest.mark.pipeline
@pytest.mark.parametrize("check", NOT_IN_DISEASE, ids=[c.curie for c in NOT_IN_DISEASE] or None)
def test_curie_not_in_disease(disease_id_pipeline_outputs, check) -> None:
    """CURIE must NOT appear in any disease intermediate ID file."""
    if not isinstance(check, DiseaseCheck):
        pytest.skip("NOT_IN_DISEASE is empty -- add entries to activate this test")
    for vocab, path in disease_id_pipeline_outputs.items():
        ids = _read_ids_with_types(path)
        if check.curie in ids:
            raise AssertionError(
                f"{check.curie} found in disease/{vocab} but should not be "
                f"(expected type {check.expected_type} elsewhere; see {check.issue})"
            )


# ---------------------------------------------------------------------------
# Tests: direct cross-reference
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
@pytest.mark.parametrize(
    "check",
    EXPECTED_XREF + EXPECTED_NO_XREF,
    ids=[
        f"{c.curie1}__{'xref' if c.should_xref else 'no_xref'}__{c.curie2}"
        for c in EXPECTED_XREF + EXPECTED_NO_XREF
    ] or None,
)
def test_direct_xref(disease_concords_dir, check) -> None:
    """Check direct cross-reference presence or absence across all concord files."""
    if not isinstance(check, ConcordCheck):
        pytest.skip("EXPECTED_XREF/EXPECTED_NO_XREF are empty -- add entries to activate this test")
    has_xref = _any_concord_xrefs(disease_concords_dir, check.curie1, check.curie2)
    if check.should_xref:
        assert has_xref, (
            f"{check.curie1} and {check.curie2} expected to be a direct xref pair in "
            f"a disease concord file but no such xref found (see {check.issue})"
        )
    else:
        assert not has_xref, (
            f"{check.curie1} and {check.curie2} must NOT be a direct xref pair in any "
            f"disease concord file but one was found (see {check.issue})"
        )


# ---------------------------------------------------------------------------
# Tests: clique membership (multi-hop equivalence)
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
@pytest.mark.parametrize(
    "check",
    CLIQUE_CHECKS,
    ids=[
        f"{c.curie1}__{'same' if c.same_clique else 'diff'}__{c.curie2}"
        for c in CLIQUE_CHECKS
    ] or None,
)
def test_clique(disease_cliques, check: CliqueCheck) -> None:
    """After full glom over the disease concords, two CURIEs must (or must not)
    end up in the same equivalence class.

    This is the multi-hop check that direct-xref tests miss.  Failure messages
    include the actual clique each CURIE landed in so the cause is obvious.
    """
    curie_to_clique, _ = disease_cliques
    c1 = curie_to_clique.get(check.curie1)
    c2 = curie_to_clique.get(check.curie2)

    if check.same_clique:
        assert c1 is not None, f"{check.curie1} is not in any clique (see {check.issue})"
        assert c2 is not None, f"{check.curie2} is not in any clique (see {check.issue})"
        assert c1 == c2, (
            f"{check.curie1} and {check.curie2} should be in the same clique but are not "
            f"(see {check.issue}).\n  {check.curie1} is in clique: {sorted(c1)}\n"
            f"  {check.curie2} is in clique: {sorted(c2)}"
        )
    else:
        assert c1 != c2 or c1 is None, (
            f"{check.curie1} and {check.curie2} should NOT be in the same clique but are "
            f"(see {check.issue}).\n  Both are in clique: {sorted(c1 or [])}"
        )


# ---------------------------------------------------------------------------
# Tests: final preferred label
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
@pytest.mark.parametrize("check", LABEL_CHECKS, ids=[c.curie for c in LABEL_CHECKS])
def test_final_label(disease_cliques, babel_node_factory, check: LabelCheck) -> None:
    """Simulate write_compendium's label-selection step and assert the chosen label.

    Looks up `check.curie`'s clique, then runs NodeFactory.create_node() +
    _select_preferred_label() with the same config write_compendium uses.  The
    bmt fetch happens once per session via babel_node_factory.
    """
    curie_to_clique, curie_to_type = disease_cliques
    clique = curie_to_clique.get(check.curie)
    assert clique is not None, (
        f"{check.curie} is not in any clique -- cannot evaluate label "
        f"(see {check.issue})"
    )
    assigned_type = curie_to_type.get(check.curie)
    assert assigned_type == check.biolink_type, (
        f"{check.curie} was typed {assigned_type}, expected {check.biolink_type} "
        f"(see {check.issue})"
    )
    actual = simulate_label(check.curie, clique, check.biolink_type, babel_node_factory)
    assert actual == check.expected_label, (
        f"Preferred label for {check.curie}'s clique was {actual!r}, expected "
        f"{check.expected_label!r} (see {check.issue}).\n  Clique: {sorted(clique)}"
    )
