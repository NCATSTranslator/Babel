"""Pipeline tests for the EC (Enzyme Commission) data handler.

Skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_ec.py --pipeline --no-cov -v
"""
import pytest

from src.categories import MOLECULAR_ACTIVITY
from tests.conftest import assert_ids_file_valid, assert_labels_file_valid, assert_synonyms_file_valid


@pytest.mark.pipeline
def test_ec_labels_file_valid(ec_pipeline_outputs):
    rows = assert_labels_file_valid(ec_pipeline_outputs["labels"])
    assert any(r[0].startswith("EC:") for r in rows), "No EC: CURIEs found in labels"


@pytest.mark.pipeline
def test_ec_synonyms_file_valid(ec_pipeline_outputs):
    assert_synonyms_file_valid(ec_pipeline_outputs["synonyms"])


@pytest.mark.pipeline
def test_ec_ids_file_valid(ec_pipeline_outputs):
    rows = assert_ids_file_valid(ec_pipeline_outputs["ids"])
    assert all(r[1] == MOLECULAR_ACTIVITY for r in rows), "EC ids contain unexpected biolink type"
