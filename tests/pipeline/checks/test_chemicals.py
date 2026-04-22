"""Regression checks for the chemicals compendium.

Two kinds of assertions live here:

  EXPECTED_IN_CHEMICALS / NOT_IN_CHEMICALS
    — ID-presence checks: is a CURIE in the chemicals intermediate ID file?
    — These depend on existing vocab fixtures (mesh_pipeline_outputs,
      umls_pipeline_outputs, …) — only write_*_ids() is called, no Snakemake required.

  EXPECTED_XREF / EXPECTED_NO_XREF
    — Direct cross-reference checks: are two CURIEs a direct xref pair in any chemicals
      concord file?
    — IMPORTANT: only *direct* xref pairs are checked — indirect equivalences through
      multi-hop chains are out of scope.  This is intentional: it is fast enough for TDD
      and locates the concord file that is the root cause of any bad link.
    — These depend on chemicals_concords_dir, which runs Snakemake up to
      get_chemical_wikipedia_relationships.  Heavier concords (UNICHEM, CHEBI, …) are
      also scanned if already present from a prior full pipeline run.

Each entry is a NamedTuple that includes the GitHub issue URL that motivated the check.
To add a new check, append one tuple to the appropriate list — no other changes needed.
To add checks for a different vocabulary (e.g. UMLS), change the `fixture` field to the
appropriate session fixture name.

Run:
    uv run pytest tests/pipeline/checks/test_chemicals.py --pipeline --no-cov -v
"""
from typing import NamedTuple

import pytest

from tests.pipeline.conftest import _any_concord_xrefs, get_curies_and_types_from_ids_file

# ---------------------------------------------------------------------------
# ID-presence check type and tables
# ---------------------------------------------------------------------------


class ChemCheck(NamedTuple):
    fixture: str        # session fixture name, e.g. "mesh_pipeline_outputs"
    curie: str          # CURIE to look for in the chemicals ID file
    expected_type: str  # Biolink type (used in failure messages; also asserted if the
                        # intermediate file includes a type column, e.g. for UMLS)
    issue: str          # GitHub issue URL that motivated this check


EXPECTED_IN_CHEMICALS: list[ChemCheck] = [
    ChemCheck(
        "mesh_pipeline_outputs",
        "MESH:C000598555",
        "biolink:ChemicalEntity",
        "https://github.com/NCATSTranslator/Babel/issues/708",
    ),
    ChemCheck(
        "mesh_pipeline_outputs",
        "MESH:C100843",
        "biolink:Drug",
        "https://github.com/NCATSTranslator/Babel/issues/708",
    ),
    # D08.211 Coenzymes — non-protein small molecules that were previously excluded from
    # chemicals by a blanket D08 exclusion.  They should be CHEMICAL_ENTITY.
    ChemCheck(
        "mesh_pipeline_outputs",
        "MESH:D009243",  # Nicotinamide Adenine Dinucleotide (NAD) — D08.211.060
        "biolink:ChemicalEntity",
        "https://github.com/NCATSTranslator/Babel/issues/675",
    ),
    ChemCheck(
        "mesh_pipeline_outputs",
        "MESH:D003067",  # Coenzyme A — D08.211.190
        "biolink:ChemicalEntity",
        "https://github.com/NCATSTranslator/Babel/issues/675",
    ),
]

NOT_IN_CHEMICALS: list[ChemCheck] = []


# ---------------------------------------------------------------------------
# Direct-xref check type and tables
# ---------------------------------------------------------------------------


class ConcordCheck(NamedTuple):
    fixture: str        # session fixture providing the concords directory path
    curie1: str
    curie2: str
    should_xref: bool   # True = must be a direct xref pair; False = must NOT be
    issue: str          # GitHub issue URL that motivated this check


EXPECTED_XREF: list[ConcordCheck] = []

EXPECTED_NO_XREF: list[ConcordCheck] = [
    ConcordCheck(
        "chemicals_concords_dir",
        "MESH:C068616",
        "CHEBI:29103",
        False,
        "https://github.com/NCATSTranslator/Babel/issues/256",
    ),
]


# ---------------------------------------------------------------------------
# Tests: ID presence
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
@pytest.mark.parametrize("check", EXPECTED_IN_CHEMICALS, ids=[c.curie for c in EXPECTED_IN_CHEMICALS])
def test_curie_in_chemicals(request, check: ChemCheck) -> None:
    """CURIE must appear in the chemicals intermediate ID file."""
    outputs = request.getfixturevalue(check.fixture)
    ids = get_curies_and_types_from_ids_file(outputs["chemicals"])
    assert check.curie in ids, (
        f"{check.curie} not found in chemicals "
        f"(expected type {check.expected_type}; see {check.issue})"
    )
    actual_type = ids[check.curie]
    if actual_type is not None:
        assert actual_type == check.expected_type, (
            f"{check.curie} found in chemicals but type mismatch: "
            f"expected {check.expected_type}, got {actual_type} (see {check.issue})"
        )


@pytest.mark.pipeline
@pytest.mark.parametrize("check", NOT_IN_CHEMICALS, ids=[c.curie for c in NOT_IN_CHEMICALS] or None)
def test_curie_not_in_chemicals(request, check) -> None:
    """CURIE must NOT appear in the chemicals intermediate ID file."""
    if not isinstance(check, ChemCheck):
        pytest.skip("NOT_IN_CHEMICALS is empty — add entries to activate this test")
    outputs = request.getfixturevalue(check.fixture)
    ids = get_curies_and_types_from_ids_file(outputs["chemicals"])
    assert check.curie not in ids, (
        f"{check.curie} found in chemicals but should not be "
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
    ],
)
def test_direct_xref(request, check: ConcordCheck) -> None:
    """Check direct cross-reference presence or absence across all concord files.

    NOTE: only *direct* xref pairs are checked — indirect equivalences through
    multi-hop chains are out of scope.  This is intentional: it is fast enough for
    TDD and identifies the concord file that is the root cause of the problem.
    """
    concords_dir = request.getfixturevalue(check.fixture)
    has_xref = _any_concord_xrefs(concords_dir, check.curie1, check.curie2)
    if check.should_xref:
        assert has_xref, (
            f"{check.curie1} and {check.curie2} expected to be a direct xref pair in "
            f"a concord file but no such xref found (see {check.issue})"
        )
    else:
        assert not has_xref, (
            f"{check.curie1} and {check.curie2} must NOT be a direct xref pair in any "
            f"concord file but one was found (see {check.issue})"
        )
