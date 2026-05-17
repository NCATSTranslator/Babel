"""Pipeline tests for the CLO (Cell Line Ontology) data handler.

Skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_clo.py --pipeline --no-cov -v
"""
import pytest

from src.categories import CELL_LINE
from tests.conftest import assert_ids_file_valid, assert_labels_file_valid, assert_synonyms_file_valid


@pytest.mark.pipeline
def test_clo_labels_file_valid(clo_pipeline_outputs):
    rows = assert_labels_file_valid(clo_pipeline_outputs["labels"])
    assert any(r[0].startswith("CLO:") for r in rows), "No CLO: CURIEs found in labels"


@pytest.mark.pipeline
def test_clo_synonyms_file_valid(clo_pipeline_outputs):
    assert_synonyms_file_valid(clo_pipeline_outputs["synonyms"])


@pytest.mark.pipeline
def test_clo_ids_file_valid(clo_pipeline_outputs):
    rows = assert_ids_file_valid(clo_pipeline_outputs["ids"])
    assert all(r[1] == CELL_LINE for r in rows), "CLO ids contain unexpected biolink type"
