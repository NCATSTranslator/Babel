"""Pipeline tests for the ChEMBL data handler.

Skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_chembl.py --pipeline --no-cov -v

These tests build their fixture by bulk-loading the ~17 GB ChEMBL molecule TTL
into an in-memory pyoxigraph store (see ChemblRDF in src/datahandlers/chembl.py),
so they need a large-memory host.  They are marked min_memory_gb(128) to match
the chembl_labels_and_smiles Snakemake rule's mem="128G" allocation and are
auto-skipped on smaller machines (a 32 GB laptop swap-thrashes and never finishes).
"""

import pytest

from tests.conftest import assert_labels_file_valid, read_tsv

# Minimum RAM (GiB) to attempt the ChEMBL TTL load; kept in sync with the
# chembl_labels_and_smiles rule's mem="128G" in src/snakefiles/datacollect.snakefile.
CHEMBL_MIN_MEMORY_GB = 128


@pytest.mark.pipeline
@pytest.mark.slow  # the 17 GB TTL bulk-load blows past the default pipeline timeout
@pytest.mark.min_memory_gb(CHEMBL_MIN_MEMORY_GB)
def test_chembl_labels_file_valid(chembl_pipeline_outputs):
    rows = assert_labels_file_valid(chembl_pipeline_outputs["labels"])
    assert any(r[0].startswith("CHEMBL.COMPOUND:") for r in rows), "No CHEMBL.COMPOUND: CURIEs found in labels"


@pytest.mark.pipeline
@pytest.mark.slow  # the 17 GB TTL bulk-load blows past the default pipeline timeout
@pytest.mark.min_memory_gb(CHEMBL_MIN_MEMORY_GB)
def test_chembl_smiles_file_non_empty(chembl_pipeline_outputs):
    rows = read_tsv(chembl_pipeline_outputs["smiles"])
    assert rows, "ChEMBL smiles file is empty"
    assert all(len(r) == 2 for r in rows), "ChEMBL smiles rows should have 2 columns"
    assert any(r[0].startswith("CHEMBL.COMPOUND:") for r in rows), "No CHEMBL.COMPOUND: CURIEs in smiles file"
