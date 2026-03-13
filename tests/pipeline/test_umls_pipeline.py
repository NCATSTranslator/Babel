"""UMLS-specific pipeline tests (issue #675 extension).

The generic non-empty and mutual-exclusivity tests for all seven UMLS compendia
(chemicals, protein, anatomy, disease/phenotype, process/activity, taxon, gene)
are in test_vocabulary_partitioning.py.  This file contains only the
UMLS-specific targeted test that has no generic equivalent.

All tests require UMLS_API_KEY to be set for the initial download (or the
files to already be cached in babel_downloads/UMLS/).  They are skipped by
default.  Run with:
    PYTHONPATH=. uv run pytest tests/pipeline/test_umls_pipeline.py --pipeline --no-cov -v
"""
import pytest

from tests.pipeline.conftest import _read_ids


@pytest.mark.pipeline
def test_chemicals_excludes_protein_semantic_tree(umls_pipeline_outputs):
    """Chemicals must not contain any UMLS IDs that the protein compendium claimed.

    Guards against amino-acid/peptide/protein entries (semantic type tree
    A1.4.1.2.1.7) leaking into the chemical compendium.  The mutual-exclusivity
    test in test_vocabulary_partitioning.py also catches this, but this test
    names the specific semantic-tree invariant explicitly so a failure message
    is immediately actionable.
    """
    chem_ids = _read_ids(umls_pipeline_outputs["chemicals"])
    prot_ids = _read_ids(umls_pipeline_outputs["protein"])
    overlap = chem_ids & prot_ids
    assert len(overlap) == 0, (
        f"Found {len(overlap)} IDs in both chemicals and protein UMLS outputs: "
        f"{sorted(overlap)[:10]}"
    )
