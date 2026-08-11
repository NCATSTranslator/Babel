# Tests for src/datahandlers/clinvar.py — ClinVar ingest for the SequenceVariant compendium.
#
# VERBATIM FIXTURE. ClinVar's variant_summary.txt is a public NCBI download (no credentials), so
# tests/data/clinvar_variant_summary_sample.tsv is a VERBATIM extract: the real ~40-column header (whose
# first column ClinVar prefixes with '#', '#AlleleID') and 7 real rows — VariationIDs 2/3/4 each appearing
# twice (the GRCh37/GRCh38 assembly duplicates, exercising VariationID dedup) plus VariationID 25 whose
# RS# (dbSNP) is '-1' (no dbSNP id, exercising the no-rs skip). Re-derive from
# https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz.
import os

import pytest

from src.datahandlers.clinvar import (
    _rs_curies,
    build_clinvar_dbsnp_relationships,
    write_clinvar_ids,
    write_clinvar_labels,
)
from tests.conftest import assert_concordance_file_valid

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "clinvar_variant_summary_sample.tsv")

# The fixture's distinct VariationIDs (2/3/4 each appear twice -> deduped; 25 once).
VARIATION_IDS = {"CLINVAR:2", "CLINVAR:3", "CLINVAR:4", "CLINVAR:25"}


# IDS


@pytest.mark.unit
def test_write_clinvar_ids_should_emit_one_id_per_variation_deduped_by_assembly(tmp_path):
    """Each VariationID becomes one CLINVAR:<VariationID> id typed biolink:SequenceVariant; the GRCh37/
    GRCh38 duplicate rows collapse to a single id per variation."""
    outfile = tmp_path / "ids"
    write_clinvar_ids(FIXTURE, str(outfile))
    rows = [line.split("\t") for line in outfile.read_text().splitlines()]
    ids = [curie for curie, _type in rows]
    assert set(ids) == VARIATION_IDS
    assert len(ids) == len(VARIATION_IDS)  # no duplicates despite the assembly-duplicate rows
    assert all(biolink_type == "biolink:SequenceVariant" for _curie, biolink_type in rows)


@pytest.mark.unit
def test_write_clinvar_ids_should_raise_on_an_empty_download(tmp_path):
    """A header-only (empty) variant_summary fails loudly rather than silently emptying the compendium."""
    empty = tmp_path / "empty.tsv"
    empty.write_text("#AlleleID\tType\tName\tVariationID\tRS# (dbSNP)\n")
    outfile = tmp_path / "ids"
    with pytest.raises(RuntimeError, match="No ClinVar variations"):
        write_clinvar_ids(str(empty), str(outfile))


# LABELS


@pytest.mark.unit
def test_write_clinvar_labels_should_use_the_hgvs_name(tmp_path):
    """Each variation is labeled with its HGVS Name (one label per VariationID)."""
    outfile = tmp_path / "labels"
    write_clinvar_labels(FIXTURE, str(outfile))
    labels = dict(line.split("\t") for line in outfile.read_text().splitlines())
    assert labels == {
        "CLINVAR:2": "NM_014855.3(AP5Z1):c.80_83delinsTGCTGTAAACTGTAACTGTAAA (p.Arg27_Ile28delinsLeuLeuTer)",
        "CLINVAR:3": "NM_014855.3(AP5Z1):c.1413_1426del (p.Leu473fs)",
        "CLINVAR:4": "NM_014630.3(ZNF592):c.3136G>A (p.Gly1046Arg)",
        "CLINVAR:25": "NM_015600.4(ABHD12):c.-6898_191+7002delinsCC",
    }


# CONCORD (CLINVAR <-> DBSNP)


@pytest.mark.unit
def test_build_clinvar_dbsnp_relationships_should_link_to_rs_prefixed_dbsnp(tmp_path):
    """Each variation with an rs id is linked eq to DBSNP:rs<N> (the bare RS number gets the 'rs' prefix
    per the Bioregistry dbsnp pattern ^rs\\d+$); the variation with RS='-1' gets no edge."""
    outfile = tmp_path / "concord"
    metadata = tmp_path / "meta.yaml"
    build_clinvar_dbsnp_relationships(FIXTURE, str(outfile), str(metadata))

    rows = assert_concordance_file_valid(str(outfile))
    edges = {(row[0], row[1], row[2]) for row in rows}
    assert edges == {
        ("CLINVAR:2", "eq", "DBSNP:rs397704705"),
        ("CLINVAR:3", "eq", "DBSNP:rs397704709"),
        ("CLINVAR:4", "eq", "DBSNP:rs150829393"),
    }
    assert not any(subject == "CLINVAR:25" for subject, _rel, _obj in edges)  # RS=-1 -> no edge


@pytest.mark.unit
def test_rs_curies_should_prefix_handle_commas_and_skip_missing():
    """_rs_curies rs-prefixes bare numbers, passes through rs-prefixed values, splits comma-separated
    lists, and returns [] for the no-rs sentinels."""
    assert _rs_curies("397704705") == ["DBSNP:rs397704705"]
    assert _rs_curies("rs123") == ["DBSNP:rs123"]
    assert _rs_curies("123,456") == ["DBSNP:rs123", "DBSNP:rs456"]
    assert _rs_curies("-1") == []
    assert _rs_curies("") == []
    assert _rs_curies(None) == []
    assert _rs_curies("-2") == []  # malformed (not rs<digits>) -> skipped


# HEADER ROBUSTNESS (BOM + leading '#')


@pytest.mark.unit
def test_write_clinvar_ids_should_strip_a_bom_and_hash_prefixed_header(tmp_path):
    """A BOM-prefixed file (utf-8-sig) whose first column ClinVar prefixes with '#' (synthetic 3-column
    mechanism test) still parses: the BOM and the leading '#' are both stripped."""
    bom_csv = tmp_path / "bom.tsv"
    with open(bom_csv, "w", encoding="utf-8-sig") as outf:  # utf-8-sig writes a BOM
        outf.write("#AlleleID\tVariationID\tRS# (dbSNP)\n1\t2\t397704705\n")
    outfile = tmp_path / "ids"
    write_clinvar_ids(str(bom_csv), str(outfile))
    assert outfile.read_text().splitlines() == ["CLINVAR:2\tbiolink:SequenceVariant"]
