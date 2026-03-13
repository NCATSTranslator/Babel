"""MeSH-specific pipeline tests (issue #675).

The generic non-empty and mutual-exclusivity tests for all five MeSH compendia
(chemicals, protein, anatomy, disease/phenotype, taxon) are in
test_vocabulary_partitioning.py.  This file contains only the MeSH-specific
targeted test that has no generic equivalent.

All tests are skipped by default.  Run with:
    PYTHONPATH=. uv run pytest tests/pipeline/test_mesh_pipeline.py --pipeline --no-cov -v
"""
import pytest

from tests.pipeline.conftest import _read_ids


@pytest.mark.pipeline
def test_chemicals_excludes_all_protein_descriptor_trees(mesh_pipeline_outputs):
    """Chemicals output must not contain any D05/D08/D12.776 descriptor terms.

    This catches terms in "in-neither" subtrees (e.g. D05.750 Polymers, D08.211
    Coenzymes) that should be excluded from chemicals even though they are not
    captured by protein.write_mesh_ids().  The mutual-exclusivity test in
    test_vocabulary_partitioning.py only checks pairwise overlap between
    compendia; this test checks exclusion against the full tree.
    """
    chem_ids = _read_ids(mesh_pipeline_outputs["chemicals"])
    excluded_tree_terms = mesh_pipeline_outputs["excluded_tree_terms"]
    overlap = chem_ids & excluded_tree_terms
    assert len(overlap) == 0, (
        f"Found {len(overlap)} D05/D08/D12.776 descriptor terms in chemicals output: "
        f"{sorted(overlap)[:10]}"
    )
