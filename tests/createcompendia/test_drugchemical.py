"""
Unit tests for src/createcompendia/drugchemical.py.

These exercise _validate_and_apply_manual_concords, which validates manual
concord pairs against the chemical compendia and normalises their CURIEs, and
ConflationExclusionRecorder, which records every dropped subject/object pair to a
gzipped TSV so a missing cross-reference can be diagnosed from a past run.
"""

import csv
import gzip
import logging

import pytest

from src.createcompendia.drugchemical import ConflationExclusionRecorder, _validate_and_apply_manual_concords

CONCORD_FILE = "input_data/manual_concords/drugchemical.tsv"

# A small preferred-CURIE map: each CURIE maps to its clique leader.
PREFERRED = {
    "CHEMBL:123": "CHEMBL:123",
    "DRUGBANK:DB001": "CHEMBL:123",  # alias → same leader as CHEMBL:123
    "CHEBI:456": "CHEBI:456",
}


@pytest.mark.unit
def test_valid_pair_is_normalised_and_appended():
    """A pair where both CURIEs are in the compendia is normalised and appended to pairs."""
    pairs: list[tuple[str, str]] = []
    skipped, applied_curies = _validate_and_apply_manual_concords(
        [("DRUGBANK:DB001", "CHEBI:456")], PREFERRED, pairs, CONCORD_FILE
    )
    assert skipped == 0
    assert pairs == [("CHEMBL:123", "CHEBI:456")]
    assert applied_curies == {"CHEMBL:123", "CHEBI:456"}


@pytest.mark.unit
def test_missing_subject_is_skipped_with_warning(caplog):
    """A pair whose subject is absent from the compendia is skipped; the subject CURIE appears in the warning."""
    pairs: list[tuple[str, str]] = []
    with caplog.at_level(logging.WARNING, logger="src.createcompendia.drugchemical"):
        skipped, _ = _validate_and_apply_manual_concords([("MISSING:001", "CHEBI:456")], PREFERRED, pairs, CONCORD_FILE)
    assert skipped == 1
    assert pairs == []
    assert "MISSING:001" in caplog.text
    assert CONCORD_FILE in caplog.text


@pytest.mark.unit
def test_missing_object_is_skipped_with_warning(caplog):
    """A pair whose object is absent from the compendia is skipped; the object CURIE appears in the warning."""
    pairs: list[tuple[str, str]] = []
    with caplog.at_level(logging.WARNING, logger="src.createcompendia.drugchemical"):
        skipped, _ = _validate_and_apply_manual_concords(
            [("CHEMBL:123", "MISSING:002")], PREFERRED, pairs, CONCORD_FILE
        )
    assert skipped == 1
    assert pairs == []
    assert "MISSING:002" in caplog.text
    assert CONCORD_FILE in caplog.text


@pytest.mark.unit
def test_both_missing_warns_for_each_and_counts_once(caplog):
    """When both CURIEs in a pair are absent, a warning is emitted for each but the pair is counted as one skip."""
    pairs: list[tuple[str, str]] = []
    with caplog.at_level(logging.WARNING, logger="src.createcompendia.drugchemical"):
        skipped, _ = _validate_and_apply_manual_concords(
            [("MISSING:001", "MISSING:002")], PREFERRED, pairs, CONCORD_FILE
        )
    assert skipped == 1
    assert pairs == []
    assert "MISSING:001" in caplog.text
    assert "MISSING:002" in caplog.text


@pytest.mark.unit
def test_mixed_pairs_counts_correctly(caplog):
    """Skipped pairs do not prevent valid pairs from being appended; counts are independent."""
    pairs: list[tuple[str, str]] = []
    concords = [
        ("CHEMBL:123", "CHEBI:456"),  # valid
        ("MISSING:001", "CHEBI:456"),  # bad subject
        ("CHEMBL:123", "MISSING:002"),  # bad object
    ]
    with caplog.at_level(logging.WARNING, logger="src.createcompendia.drugchemical"):
        skipped, _ = _validate_and_apply_manual_concords(concords, PREFERRED, pairs, CONCORD_FILE)
    assert skipped == 2
    assert pairs == [("CHEMBL:123", "CHEBI:456")]


@pytest.mark.unit
def test_aliases_normalizing_to_same_curie_are_skipped(caplog):
    """A pair whose two CURIEs both map to the same preferred CURIE is skipped as a self-pair."""
    pairs: list[tuple[str, str]] = []
    # CHEMBL:123 and DRUGBANK:DB001 both map to CHEMBL:123 in PREFERRED.
    with caplog.at_level(logging.WARNING, logger="src.createcompendia.drugchemical"):
        skipped, applied_curies = _validate_and_apply_manual_concords(
            [("CHEMBL:123", "DRUGBANK:DB001")], PREFERRED, pairs, CONCORD_FILE
        )
    assert skipped == 1
    assert pairs == []
    assert applied_curies == set()
    assert "CHEMBL:123" in caplog.text


def _read_exclusions(path):
    """Read a gzipped exclusion-report TSV back into a list of dict rows."""
    with gzip.open(path, "rt", newline="") as inf:
        return list(csv.DictReader(inf, dialect=csv.excel_tab))


@pytest.mark.unit
def test_exclusion_recorder_writes_header_rows_and_counts(tmp_path):
    """The recorder writes a header, one row per dropped pair, and tracks per-(source, reason) counts."""
    outfile = tmp_path / "excluded_pairs.tsv.gz"
    with ConflationExclusionRecorder(outfile) as recorder:
        recorder.record(source="RXNORM", reason="rxcui_not_in_any_clique", subject="RXCUI:1", obj="RXCUI:2")
        recorder.record(source="RXNORM", reason="rxcui_not_in_any_clique", subject="RXCUI:3", obj="RXCUI:4")
        recorder.record(
            source="PUBCHEM_RXNORM",
            reason="non_chemical_type",
            subject="CHEBI:5",
            obj="PUBCHEM.COMPOUND:6",
            subject_type="biolink:Gene",
            detail="subject type is not a biolink:ChemicalEntity descendant",
        )
        assert recorder.total() == 3

    rows = _read_exclusions(outfile)
    assert len(rows) == 3
    assert set(rows[0].keys()) == set(ConflationExclusionRecorder.COLUMNS)
    assert rows[0]["source"] == "RXNORM"
    assert rows[0]["subject"] == "RXCUI:1"
    assert rows[2]["subject_type"] == "biolink:Gene"
    assert rows[2]["object"] == "PUBCHEM.COMPOUND:6"
    assert recorder.counts[("RXNORM", "rxcui_not_in_any_clique")] == 2
    assert recorder.counts[("PUBCHEM_RXNORM", "non_chemical_type")] == 1


@pytest.mark.unit
def test_validate_records_missing_curie_exclusion(tmp_path):
    """When a manual concord CURIE is absent from the compendia, a row is recorded with the missing CURIE."""
    outfile = tmp_path / "excluded_pairs.tsv.gz"
    pairs: list[tuple[str, str]] = []
    with ConflationExclusionRecorder(outfile) as recorder:
        _validate_and_apply_manual_concords([("MISSING:001", "CHEBI:456")], PREFERRED, pairs, CONCORD_FILE, recorder)
    rows = _read_exclusions(outfile)
    assert len(rows) == 1
    assert rows[0]["reason"] == "manual_concord_not_in_compendium"
    assert "MISSING:001" in rows[0]["detail"]


@pytest.mark.unit
def test_validate_records_self_pair_exclusion(tmp_path):
    """A manual concord whose CURIEs collapse to the same leader is recorded as a self-pair."""
    outfile = tmp_path / "excluded_pairs.tsv.gz"
    pairs: list[tuple[str, str]] = []
    with ConflationExclusionRecorder(outfile) as recorder:
        # CHEMBL:123 and DRUGBANK:DB001 both normalize to CHEMBL:123.
        _validate_and_apply_manual_concords(
            [("CHEMBL:123", "DRUGBANK:DB001")], PREFERRED, pairs, CONCORD_FILE, recorder
        )
    rows = _read_exclusions(outfile)
    assert len(rows) == 1
    assert rows[0]["reason"] == "manual_concord_self_pair"
    assert rows[0]["subject"] == "CHEMBL:123"
