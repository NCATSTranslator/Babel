"""Pipeline tests for the EFO (Experimental Factor Ontology) data handler.

Skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_efo.py --pipeline --no-cov -v
"""

import pytest

from tests.conftest import assert_ids_file_valid, assert_labels_file_valid, assert_synonyms_file_valid


@pytest.mark.pipeline
def test_efo_labels_file_valid(efo_pipeline_outputs):
    rows = assert_labels_file_valid(efo_pipeline_outputs["labels"])
    assert any(r[0].startswith("EFO:") for r in rows), "No EFO: CURIEs found in labels"


@pytest.mark.pipeline
def test_efo_synonyms_file_valid(efo_pipeline_outputs):
    assert_synonyms_file_valid(efo_pipeline_outputs["synonyms"])


@pytest.mark.pipeline
def test_efo_ids_file_valid(efo_pipeline_outputs):
    rows = assert_ids_file_valid(efo_pipeline_outputs["ids"])
    assert any(r[0].startswith("EFO:") for r in rows), "No EFO: CURIEs found in ids"
