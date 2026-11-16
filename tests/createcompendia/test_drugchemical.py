"""
Unit tests for src/createcompendia/drugchemical.py.

These exercise _validate_and_apply_manual_concords, which validates manual
concord pairs against the chemical compendia and normalises their CURIEs, and
check the checked-in manual concord file itself.
"""

import csv
import logging

import pytest

from src.createcompendia.drugchemical import _validate_and_apply_manual_concords
from src.util import curie_format_problem

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


# THE CHECKED-IN MANUAL CONCORD FILE


@pytest.mark.unit
def test_every_manual_concord_row_is_well_formed_and_cites_an_issue():
    """Every row of the checked-in file should have exactly the five header columns, two well-formed
    CURIEs, and at least one GitHub issue URL.

    The issue is what says why the row exists and when it can be removed, and build_conflation()
    reads only subject and object, so it would accept a row without one. A short or over-long row
    (a stray tab in the notes) is what csv.DictReader reports as a None value or a None key.
    """
    with open(CONCORD_FILE) as f:
        rows = list(csv.DictReader(f, dialect=csv.excel_tab))
    assert rows, f"{CONCORD_FILE} has no rows"
    for line_number, row in enumerate(rows, start=2):
        where = f"{CONCORD_FILE} line {line_number}: {row}"
        assert list(row) == ["subject", "predicate", "object", "notes", "url"], where
        assert None not in row.values(), where
        for curie in (row["subject"], row["object"]):
            assert curie_format_problem(curie) is None, where
        assert row["predicate"].startswith("skos:"), where
        urls = row["url"].split("||")
        assert all(url.startswith("https://github.com/") and "/issues/" in url for url in urls), where
