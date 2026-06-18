"""Pipeline tests for the Rhea data handler.

Skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_rhea.py --pipeline --no-cov -v
"""

import pytest

from tests.conftest import assert_concordance_file_valid, assert_labels_file_valid


@pytest.mark.pipeline
def test_rhea_labels_file_valid(rhea_pipeline_outputs):
    rows = assert_labels_file_valid(rhea_pipeline_outputs["labels"])
    assert any(r[0].startswith("RHEA:") for r in rows), "No RHEA: CURIEs found in labels"


@pytest.mark.pipeline
def test_rhea_concords_file_valid(rhea_pipeline_outputs):
    rows = assert_concordance_file_valid(rhea_pipeline_outputs["concords"])
    assert any(r[0].startswith("RHEA:") and r[2].startswith("EC:") for r in rows), (
        "No RHEA→EC mappings found in concords"
    )
