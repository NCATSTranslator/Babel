"""MeSH-specific pipeline tests (issue #675).

The generic non-empty and mutual-exclusivity tests for all five MeSH compendia
(chemicals, protein, anatomy, disease/phenotype, taxon) are in
test_vocabulary_partitioning.py.  This file contains only the MeSH-specific
targeted test that has no generic equivalent.

All pipeline tests are skipped by default unless PyTest is run with `--pipeline`.  Run with:
    uv run pytest tests/pipeline/test_mesh_pipeline.py --pipeline --no-cov -v
"""
import pytest

from tests.pipeline.conftest import get_curies_from_ids_file


@pytest.mark.pipeline
def test_chemicals_excludes_protein_and_macromolecule_descriptor_trees(mesh_pipeline_outputs, excluded_mesh_tree_terms):
    """Chemicals must not contain D05 protein subtrees, D08 protein subtrees, or D12.776.

    Excluded from chemicals (→ protein compendium):
    - D05.500 Multiprotein Complexes, D05.875 Protein Aggregates
    - D08.811 Enzymes, D08.622 Enzyme Precursors, D08.244 Cytochromes
    - D12.776 Proteins

    Included in chemicals (NOT excluded):
    - D08.211 Coenzymes (e.g. NAD, Coenzyme A) — non-protein small molecules
    - D05.374 Micelles, D05.750 Polymers, D05.937 Smart Materials — included as
      CHEMICAL_ENTITY for now (TODO: assign a more specific Biolink type)

    The mutual-exclusivity test in test_vocabulary_partitioning.py only checks pairwise
    overlap between compendia; this test checks exclusion against the full tree.
    """
    chem_ids = get_curies_from_ids_file(mesh_pipeline_outputs["chemicals"])
    overlap = chem_ids & excluded_mesh_tree_terms
    assert len(overlap) == 0, (
        f"Found {len(overlap)} D05/D08/D12.776 descriptor terms in chemicals output: "
        f"{sorted(overlap)[:10]}"
    )
