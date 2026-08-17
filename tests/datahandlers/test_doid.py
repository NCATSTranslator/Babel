"""Unit tests for src/datahandlers/doid.py.

The fixture `tests/data/doid_icd_xref_sample.json` holds one node copied verbatim from
`babel_downloads/DOID/doid.json`: [`DOID:2476`](http://purl.obolibrary.org/obo/DOID_2476)
"hereditary spastic paraplegia", the grouping term whose `ICD10:G11.4` xref -- shared with all 60
of its subtypes -- fused 61 mutually exclusive diseases into one 223-identifier clique. Its eight
xrefs cover both halves of the exclusion in a single record: two ICD targets that must go, and six
non-ICD targets that must stay, three of which (`NCI:`, `UMLS_CUI:`, `ICD10CM:`) are renamed by
`norm()` first. Re-derive it from the DOID release.
"""

import json
from pathlib import Path

import pytest

from src.datahandlers.doid import build_xrefs
from src.prefixes import ICD0, ICD9, ICD10, NCIT, UMLS
from tests.conftest import assert_concordance_file_valid

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "doid_icd_xref_sample.json"

# The `other_prefixes` renames the disease build passes (a subset covering this fixture's xrefs).
OTHER_PREFIXES = {"ICD10CM": ICD10, "ICD9CM": ICD9, "ICDO": ICD0, "NCI": NCIT, "UMLS_CUI": UMLS}

# Every target the fixture's node carries, after norm() applies OTHER_PREFIXES.
_NON_ICD_TARGETS = {
    "GARD:6637",
    "MESH:D015419",
    "MIM:PS303350",
    "NCIT:C140267",
    "SNOMEDCT_US_2025_09_01:267692008",
    "UMLS:C0037773",
}
_ICD_TARGETS = {"ICD10:G11.4", "ICD9:334.1"}


def _targets(outfile):
    rows = assert_concordance_file_valid(str(outfile))
    assert {r[0] for r in rows} <= {"DOID:2476"}
    return {r[2] for r in rows}


@pytest.mark.unit
def test_build_xrefs_drops_excluded_icd_prefixes(tmp_path):
    """ICD targets are dropped and every other target survives.

    This is also the post-`norm()` ordering guard: the exclusion names `ICD10`/`ICD9` while the
    source file says `ICD10CM`/`ICD9CM`, so moving the check above `norm()` resurrects both rows.
    """
    outfile = tmp_path / "DOID"
    build_xrefs(str(FIXTURE), str(outfile), other_prefixes=OTHER_PREFIXES, excluded_target_prefixes=[ICD10, ICD9])

    assert _targets(outfile) == _NON_ICD_TARGETS


@pytest.mark.unit
def test_build_xrefs_keeps_icd_by_default(tmp_path):
    """The filter is opt-in: with no `excluded_target_prefixes` the datahandler writes everything,
    so the policy lives at the disease build's call site rather than hidden in the handler."""
    outfile = tmp_path / "DOID"
    build_xrefs(str(FIXTURE), str(outfile), other_prefixes=OTHER_PREFIXES)

    assert _targets(outfile) == _NON_ICD_TARGETS | _ICD_TARGETS


@pytest.mark.unit
def test_build_xrefs_matches_excluded_prefixes_case_insensitively(tmp_path):
    """A lower-case entry must still match, so a caller's constant casing can't silently no-op --
    the failure mode ubergraph.build_sets() guards with an explicit upper-case assertion."""
    outfile = tmp_path / "DOID"
    build_xrefs(str(FIXTURE), str(outfile), other_prefixes=OTHER_PREFIXES, excluded_target_prefixes=["icd10", "icd9"])

    assert _targets(outfile) == _NON_ICD_TARGETS


@pytest.mark.unit
def test_fixture_is_verbatim_doid():
    """The fixture must stay a verbatim slice of doid.json: these are the raw pre-norm() spellings
    the ordering guard above depends on. If a DOID release changes them, re-derive the fixture."""
    node = json.loads(FIXTURE.read_text())["graphs"][0]["nodes"][0]
    assert node["id"] == "http://purl.obolibrary.org/obo/DOID_2476"
    assert [x["val"] for x in node["meta"]["xrefs"]] == [
        "GARD:6637",
        "ICD10CM:G11.4",
        "ICD9CM:334.1",
        "MESH:D015419",
        "MIM:PS303350",
        "NCI:C140267",
        "SNOMEDCT_US_2025_09_01:267692008",
        "UMLS_CUI:C0037773",
    ]
