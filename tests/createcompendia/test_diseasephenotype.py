"""
Unit tests for src/createcompendia/diseasephenotype.py.

These exercise the UMLS semantic-type-tree → Biolink category map that
``write_umls_ids`` hands to ``umls.write_umls_ids``. The map is built inline,
so we capture it by mocking the downstream ``umls.write_umls_ids`` call rather
than running a real MRSTY parse -- keeping these tests fast and offline.
"""

from unittest.mock import patch

import pytest

from src.categories import DISEASE, PHENOTYPIC_FEATURE
from src.createcompendia import diseasephenotype


def _capture_umlsmap(tmp_path):
    """Run write_umls_ids with the downstream call mocked, returning the category map it built."""
    badumlsfile = tmp_path / "badumls.txt"
    badumlsfile.write_text("# no blocked CUIs\n")
    with patch.object(diseasephenotype.umls, "write_umls_ids") as mock_write:
        diseasephenotype.write_umls_ids(
            mrsty=str(tmp_path / "MRSTY.RRF"),  # never read: write_umls_ids is mocked
            outfile=str(tmp_path / "out"),
            badumlsfile=str(badumlsfile),
        )
    assert mock_write.call_count == 1, "expected diseasephenotype to delegate to umls.write_umls_ids exactly once"
    # umls.write_umls_ids(mrsty, category_map, outfile, ...): the map is the 2nd positional arg.
    return mock_write.call_args.args[1]


@pytest.mark.unit
def test_finding_and_lab_result_trees_are_not_claimed(tmp_path):
    """
    Regression guard for #569: the disease/phenotype compendium must NOT claim UMLS
    "Finding" (A2.2 / T033) or "Laboratory or Test Result" (A2.2.1 / T034). Leaving them
    unmapped is what lets them fall through to the leftover UMLS sweep, where STY_OVERRIDES
    re-types them (T033 → biolink:Phenomenon, T034 → biolink:ClinicalFinding). If either
    tree is re-added here the override never fires, so fail loudly.
    """
    umlsmap = _capture_umlsmap(tmp_path)
    assert "A2.2" not in umlsmap, 'A2.2 "Finding" (T033) must stay unclaimed so leftover re-types it -- see #569'
    assert "A2.2.1" not in umlsmap, (
        'A2.2.1 "Lab/Test Result" (T034) must stay unclaimed so leftover re-types it -- see #569'
    )


@pytest.mark.unit
def test_phenotype_trees_remain_claimed(tmp_path):
    """A2.2.2 (Sign or Symptom) and A2.3 (Organism Attribute) genuinely are phenotypic features."""
    umlsmap = _capture_umlsmap(tmp_path)
    assert umlsmap.get("A2.2.2") == PHENOTYPIC_FEATURE
    assert umlsmap.get("A2.3") == PHENOTYPIC_FEATURE


@pytest.mark.unit
def test_disease_trees_remain_claimed(tmp_path):
    """The core disease semantic-type trees must still map to biolink:Disease."""
    umlsmap = _capture_umlsmap(tmp_path)
    for tree in [
        "B2.2.1.2.1",
        "A1.2.2.1",
        "A1.2.2.2",
        "B2.3",
        "B2.2.1.2",
        "B2.2.1.2.1.1",
        "B2.2.1.2.2",
        "A1.2.2",
        "B2.2.1.2.1.2",
    ]:
        assert umlsmap.get(tree) == DISEASE, f"{tree} should map to {DISEASE}"
