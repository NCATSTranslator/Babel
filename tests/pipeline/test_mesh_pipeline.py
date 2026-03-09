"""Pipeline tests for MeSH chemical/protein ID separation (issue #675).

These tests verify that:
1. chemicals.write_mesh_ids() produces non-empty output
2. protein.write_mesh_ids() produces non-empty output
3. The two outputs share no IDs (the core correctness property of issue #675)
4. The chemicals output excludes all D05/D08/D12.776 descriptor terms

All tests require babel_downloads/MESH/mesh.nt to be pre-populated and are
skipped by default. Run with: pytest tests/pipeline/ --pipeline --no-cov -v
"""
import pytest


def _read_ids(path: str) -> set[str]:
    """Read a TSV output file and return the set of CURIEs (first column)."""
    ids = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(line.split("\t")[0])
    return ids


@pytest.mark.pipeline
def test_chemicals_mesh_ids_non_empty(mesh_pipeline_outputs):
    chem_ids = _read_ids(mesh_pipeline_outputs["chemicals"])
    assert len(chem_ids) > 0, "chemicals.write_mesh_ids() produced no output"


@pytest.mark.pipeline
def test_protein_mesh_ids_non_empty(mesh_pipeline_outputs):
    prot_ids = _read_ids(mesh_pipeline_outputs["protein"])
    assert len(prot_ids) > 0, "protein.write_mesh_ids() produced no output"


@pytest.mark.pipeline
def test_no_overlap_between_chemicals_and_protein_mesh_ids(mesh_pipeline_outputs):
    """Core correctness test for issue #675: no ID should appear in both outputs."""
    chem_ids = _read_ids(mesh_pipeline_outputs["chemicals"])
    prot_ids = _read_ids(mesh_pipeline_outputs["protein"])
    overlap = chem_ids & prot_ids
    assert len(overlap) == 0, (
        f"Found {len(overlap)} IDs in both chemicals and protein MeSH outputs: "
        f"{sorted(overlap)[:10]}"
    )


@pytest.mark.pipeline
def test_chemicals_excludes_all_protein_descriptor_trees(mesh_pipeline_outputs):
    """Chemicals output must not contain any D05/D08/D12.776 descriptor terms.

    This catches terms in "in-neither" subtrees (e.g. D05.750 Polymers, D08.211
    Coenzymes) that should be excluded from chemicals even though they are not
    captured by protein.write_mesh_ids().
    """
    chem_ids = _read_ids(mesh_pipeline_outputs["chemicals"])
    excluded_tree_terms = mesh_pipeline_outputs["excluded_tree_terms"]
    overlap = chem_ids & excluded_tree_terms
    assert len(overlap) == 0, (
        f"Found {len(overlap)} D05/D08/D12.776 descriptor terms in chemicals output: "
        f"{sorted(overlap)[:10]}"
    )
