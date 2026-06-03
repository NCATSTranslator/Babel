"""Pipeline tests for the ChEMBL data handler.

Skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_chembl.py --pipeline --no-cov -v
"""

import pytest

from tests.conftest import assert_labels_file_valid, read_tsv


@pytest.mark.pipeline
def test_chembl_labels_file_valid(chembl_pipeline_outputs):
    rows = assert_labels_file_valid(chembl_pipeline_outputs["labels"])
    assert any(r[0].startswith("CHEMBL.COMPOUND:") for r in rows), "No CHEMBL.COMPOUND: CURIEs found in labels"


@pytest.mark.pipeline
def test_chembl_smiles_file_non_empty(chembl_pipeline_outputs):
    rows = read_tsv(chembl_pipeline_outputs["smiles"])
    assert rows, "ChEMBL smiles file is empty"
    assert all(len(r) == 2 for r in rows), "ChEMBL smiles rows should have 2 columns"
    assert any(r[0].startswith("CHEMBL.COMPOUND:") for r in rows), "No CHEMBL.COMPOUND: CURIEs in smiles file"
