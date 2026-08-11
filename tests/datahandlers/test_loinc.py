# Tests for src/datahandlers/loinc.py — LOINC ingest for the ClinicalFinding compendium.
#
# IMPORTANT — SYNTHETIC FIXTURE. The real LOINC release (loinc.csv) is available only under a free LOINC
# account (https://loinc.org/downloads) and cannot be downloaded anonymously, so tests/data/loinc_sample.csv
# is a SYNTHETIC fixture: it uses the documented LOINC Table Structure columns with placeholder codes
# (1111-1, ...) to exercise the parser mechanics (by-name column lookup, the CLASSTYPE=2 Clinical filter,
# dedup, RFC-4180 quoting, empty-field handling). It is NOT a verbatim extract of real LOINC records and
# asserts no guarantee about real LOINC data. The ingest must be validated against the real loinc.csv
# (with credentials) on a build machine before use.
import os

import pytest

from src.datahandlers.loinc import _loinc_has_header, write_loinc_ids, write_loinc_labels

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "loinc_sample.csv")
TUVA_FIXTURE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "loinc_tuva_sample.csv")

# The fixture's CLASSTYPE=2 (Clinical) codes; 3333-3 (lab=1), 4444-4 (survey=4), 5555-5 (claims=3) and
# 8888-8 (empty CLASSTYPE) are all excluded.
CLINICAL_IDS = {"LOINC:1111-1", "LOINC:2222-2", "LOINC:6666-6", "LOINC:7777-7"}

# The Tuva fixture's CLASSTYPE=2 (Clinical) codes; 3333-3 (lab=1) and 4444-4 (survey=4) are excluded.
# 2222-2 appears twice (dedup) — only the first label is kept.
TUVA_CLINICAL_IDS = {"LOINC:1111-1", "LOINC:2222-2"}


@pytest.mark.unit
def test_write_loinc_ids_should_include_only_clinical_class_terms(tmp_path):
    """Only CLASSTYPE=2 (Clinical) rows become ids, typed biolink:ClinicalFinding; the Laboratory (1),
    Claims (3), Surveys (4), and empty-CLASSTYPE rows are all excluded."""
    outfile = tmp_path / "ids"
    write_loinc_ids(FIXTURE, str(outfile))
    rows = [line.split("\t") for line in outfile.read_text().splitlines()]
    ids = {curie for curie, _type in rows}
    assert ids == CLINICAL_IDS
    assert all(biolink_type == "biolink:ClinicalFinding" for _curie, biolink_type in rows)


@pytest.mark.unit
def test_write_loinc_ids_should_dedup_a_repeated_loinc_num(tmp_path):
    """A LOINC_NUM appearing in multiple clinical rows (2222-2) is written exactly once."""
    outfile = tmp_path / "ids"
    write_loinc_ids(FIXTURE, str(outfile))
    lines = outfile.read_text().splitlines()
    assert sum(1 for line in lines if line.startswith("LOINC:2222-2\t")) == 1
    assert len(lines) == len(CLINICAL_IDS)


@pytest.mark.unit
def test_write_loinc_labels_should_label_clinical_terms_from_long_common_name(tmp_path):
    """Clinical-class terms get a CURIE\\tlabel row from LONG_COMMON_NAME; a term with an empty
    LONG_COMMON_NAME (7777-7) gets an id but no label, and a duplicate keeps its first label."""
    outfile = tmp_path / "labels"
    write_loinc_labels(FIXTURE, str(outfile))
    labels = dict(line.split("\t") for line in outfile.read_text().splitlines())
    assert labels == {
        "LOINC:1111-1": "Clinical finding example one",
        "LOINC:2222-2": "Clinical finding example two",  # first label wins over the duplicate row
        "LOINC:6666-6": "Clinical finding, with a comma",
    }
    assert "LOINC:7777-7" not in labels  # empty LONG_COMMON_NAME -> no label


@pytest.mark.unit
def test_write_loinc_labels_should_parse_a_quoted_label_containing_a_comma(tmp_path):
    """A LONG_COMMON_NAME with an embedded comma is RFC-4180-quoted in loinc.csv and must survive intact
    (real LOINC names contain commas)."""
    outfile = tmp_path / "labels"
    write_loinc_labels(FIXTURE, str(outfile))
    labels = dict(line.split("\t") for line in outfile.read_text().splitlines())
    assert labels["LOINC:6666-6"] == "Clinical finding, with a comma"


@pytest.mark.unit
def test_write_loinc_ids_should_resolve_columns_by_name(tmp_path):
    """The parser reads LOINC_NUM/CLASSTYPE/LONG_COMMON_NAME by header name from a wide CSV (the real
    loinc.csv has ~100 columns), not by a fixed position — a column reorder must not break it."""
    import csv

    with open(FIXTURE, newline="") as inf:
        rows = list(csv.DictReader(inf))
    reordered = tmp_path / "reordered.csv"
    fieldnames = list(reversed(rows[0].keys()))
    with open(reordered, "w", newline="") as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    outfile = tmp_path / "ids"
    write_loinc_ids(str(reordered), str(outfile))
    assert {line.split("\t")[0] for line in outfile.read_text().splitlines()} == CLINICAL_IDS


@pytest.mark.unit
def test_write_loinc_ids_should_raise_when_no_clinical_rows_are_parsed(tmp_path):
    """A loinc.csv with no CLASSTYPE=2 rows (e.g. a failed download saved as an HTML login page) fails
    loudly rather than silently producing an empty compendium."""
    no_clinical = tmp_path / "no_clinical.csv"
    no_clinical.write_text("LOINC_NUM,CLASSTYPE,LONG_COMMON_NAME\n3333-3,1,Laboratory test example\n")
    outfile = tmp_path / "ids"
    with pytest.raises(RuntimeError, match="No CLASSTYPE=2"):
        write_loinc_ids(str(no_clinical), str(outfile))


### Tuva mirror (headerless) format tests

# The Tuva Project mirrors the LOINC release as a headerless CSV (no column names) on a public S3
# bucket — the anonymous fallback when loinc_download_url is not set. The _loinc_has_header helper
# detects this format and _iter_clinical_loinc switches to positional column access.


@pytest.mark.unit
def test_loinc_has_header_should_detect_headered_loinc_csv():
    """The official loinc.csv (with a LOINC_NUM header row) is detected as headered so DictReader is
    used; the Tuva mirror (headerless) is detected as headerless so positional access is used."""
    assert _loinc_has_header(FIXTURE) is True
    assert _loinc_has_header(TUVA_FIXTURE) is False


@pytest.mark.unit
def test_write_loinc_ids_should_include_only_clinical_class_terms_tuva(tmp_path):
    """Only CLASSTYPE=2 (Clinical) rows become ids, typed biolink:ClinicalFinding, from the headerless
    Tuva-format CSV — Laboratory (1) and Surveys (4) rows are excluded."""
    outfile = tmp_path / "ids"
    write_loinc_ids(TUVA_FIXTURE, str(outfile))
    rows = [line.split("\t") for line in outfile.read_text().splitlines()]
    ids = {curie for curie, _type in rows}
    assert ids == TUVA_CLINICAL_IDS
    assert all(biolink_type == "biolink:ClinicalFinding" for _curie, biolink_type in rows)


@pytest.mark.unit
def test_write_loinc_ids_should_dedup_a_repeated_loinc_num_tuva(tmp_path):
    """A LOINC_NUM appearing in multiple clinical rows (2222-2) is written exactly once from the
    headerless Tuva-format CSV."""
    outfile = tmp_path / "ids"
    write_loinc_ids(TUVA_FIXTURE, str(outfile))
    lines = outfile.read_text().splitlines()
    assert sum(1 for line in lines if line.startswith("LOINC:2222-2\t")) == 1
    assert len(lines) == len(TUVA_CLINICAL_IDS)


@pytest.mark.unit
def test_write_loinc_labels_should_label_clinical_terms_from_long_common_name_tuva(tmp_path):
    """Clinical-class terms get a CURIE\tlabel row from LONG_COMMON_NAME (col 2) of the headerless
    Tuva-format CSV; a duplicate code keeps its first label."""
    outfile = tmp_path / "labels"
    write_loinc_labels(TUVA_FIXTURE, str(outfile))
    labels = dict(line.split("\t") for line in outfile.read_text().splitlines())
    assert labels == {
        "LOINC:1111-1": "Clinical finding example one",
        "LOINC:2222-2": "Clinical finding example two",  # first label wins over the duplicate row
    }


@pytest.mark.unit
def test_write_loinc_ids_should_raise_when_no_clinical_rows_are_parsed_tuva(tmp_path):
    """A headerless (Tuva-format) CSV with no CLASSTYPE=2 rows fails loudly rather than silently
    producing an empty compendium."""
    no_clinical = tmp_path / "no_clinical.csv"
    no_clinical.write_text(
        "3333-3,short,Laboratory test example,comp,MCnt,time,sys,Quant,method,CHEM,Laboratory desc,1,Laboratory,,Observation,,Copyright,ACTIVE,2.68,2.68\n"
    )
    outfile = tmp_path / "ids"
    with pytest.raises(RuntimeError, match="No CLASSTYPE=2"):
        write_loinc_ids(str(no_clinical), str(outfile))
