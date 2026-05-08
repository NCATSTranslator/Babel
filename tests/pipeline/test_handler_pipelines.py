"""Pipeline tests for EC, Rhea, ChEMBL, CLO, and EFO handlers.

These tests are skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_handler_pipelines.py --pipeline --no-cov -v

Unlike the tests in test_vocabulary_partitioning.py (which use VOCABULARY_REGISTRY
and focus on cross-compendium invariants), these tests validate each handler's
output format and content directly.
"""
import pytest

from tests.datahandlers.conftest import (
    assert_concordance_file_valid,
    assert_ids_file_valid,
    assert_labels_file_valid,
    assert_synonyms_file_valid,
)

# ---------------------------------------------------------------------------
# EC
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
def test_ec_labels_file_valid(ec_pipeline_outputs):
    rows = assert_labels_file_valid(ec_pipeline_outputs["labels"])
    assert len(rows) > 0, "EC labels file is empty"
    assert any(r[0].startswith("EC:") for r in rows), "No EC: CURIEs found in labels"


@pytest.mark.pipeline
def test_ec_synonyms_file_valid(ec_pipeline_outputs):
    rows = assert_synonyms_file_valid(ec_pipeline_outputs["synonyms"])
    assert len(rows) > 0, "EC synonyms file is empty"


@pytest.mark.pipeline
def test_ec_ids_file_valid(ec_pipeline_outputs):
    from src.categories import MOLECULAR_ACTIVITY
    rows = assert_ids_file_valid(ec_pipeline_outputs["ids"])
    assert len(rows) > 0, "EC ids file is empty"
    assert all(r[1] == MOLECULAR_ACTIVITY for r in rows), "EC ids contain unexpected biolink type"


# ---------------------------------------------------------------------------
# Rhea
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
def test_rhea_labels_file_valid(rhea_pipeline_outputs):
    rows = assert_labels_file_valid(rhea_pipeline_outputs["labels"])
    assert len(rows) > 0, "Rhea labels file is empty"
    assert any(r[0].startswith("RHEA:") for r in rows), "No RHEA: CURIEs found in labels"


@pytest.mark.pipeline
def test_rhea_concords_file_valid(rhea_pipeline_outputs):
    rows = assert_concordance_file_valid(rhea_pipeline_outputs["concords"])
    assert len(rows) > 0, "Rhea concords file is empty"
    assert any(r[0].startswith("RHEA:") and r[2].startswith("EC:") for r in rows), (
        "No RHEA→EC mappings found in concords"
    )


# ---------------------------------------------------------------------------
# ChEMBL
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
def test_chembl_labels_file_valid(chembl_pipeline_outputs):
    rows = assert_labels_file_valid(chembl_pipeline_outputs["labels"])
    assert len(rows) > 0, "ChEMBL labels file is empty"
    assert any(r[0].startswith("CHEMBL.COMPOUND:") for r in rows), (
        "No CHEMBL.COMPOUND: CURIEs found in labels"
    )


@pytest.mark.pipeline
def test_chembl_smiles_file_non_empty(chembl_pipeline_outputs):
    from tests.datahandlers.conftest import read_tsv
    rows = read_tsv(chembl_pipeline_outputs["smiles"])
    assert len(rows) > 0, "ChEMBL smiles file is empty"
    assert all(len(r) == 2 for r in rows), "ChEMBL smiles rows should have 2 columns"
    assert any(r[0].startswith("CHEMBL.COMPOUND:") for r in rows), (
        "No CHEMBL.COMPOUND: CURIEs in smiles file"
    )


# ---------------------------------------------------------------------------
# CLO
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
def test_clo_labels_file_valid(clo_pipeline_outputs):
    rows = assert_labels_file_valid(clo_pipeline_outputs["labels"])
    assert len(rows) > 0, "CLO labels file is empty"
    assert any(r[0].startswith("CLO:") for r in rows), "No CLO: CURIEs found in labels"


@pytest.mark.pipeline
def test_clo_synonyms_file_valid(clo_pipeline_outputs):
    rows = assert_synonyms_file_valid(clo_pipeline_outputs["synonyms"])
    assert len(rows) > 0, "CLO synonyms file is empty"


@pytest.mark.pipeline
def test_clo_ids_file_valid(clo_pipeline_outputs):
    from src.categories import CELL_LINE
    rows = assert_ids_file_valid(clo_pipeline_outputs["ids"])
    assert len(rows) > 0, "CLO ids file is empty"
    assert all(r[1] == CELL_LINE for r in rows), "CLO ids contain unexpected biolink type"


# ---------------------------------------------------------------------------
# EFO
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
def test_efo_labels_file_valid(efo_pipeline_outputs):
    rows = assert_labels_file_valid(efo_pipeline_outputs["labels"])
    assert len(rows) > 0, "EFO labels file is empty"
    assert any(r[0].startswith("EFO:") for r in rows), "No EFO: CURIEs found in labels"


@pytest.mark.pipeline
def test_efo_synonyms_file_valid(efo_pipeline_outputs):
    rows = assert_synonyms_file_valid(efo_pipeline_outputs["synonyms"])
    assert len(rows) > 0, "EFO synonyms file is empty"


@pytest.mark.pipeline
def test_efo_ids_file_valid(efo_pipeline_outputs):
    rows = assert_ids_file_valid(efo_pipeline_outputs["ids"])
    assert len(rows) > 0, "EFO ids file is empty"
    assert any(r[0].startswith("EFO:") for r in rows), "No EFO: CURIEs found in ids"
