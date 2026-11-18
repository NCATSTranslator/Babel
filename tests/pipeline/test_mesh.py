"""MeSH-specific pipeline tests (issue #675).

The generic non-empty and mutual-exclusivity tests for all five MeSH compendia
(chemicals, protein, anatomy, disease/phenotype, taxon) are in
test_vocabulary_partitioning.py.  This file contains only the MeSH-specific
targeted tests that have no generic equivalent.

All pipeline tests are skipped by default unless PyTest is run with `--pipeline`.  Run with:
    uv run pytest tests/pipeline/test_mesh.py --pipeline --no-cov -v
"""

import pytest

from src.datahandlers.mesh import read_mesh_ids_with_ncbitaxon
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
        f"Found {len(overlap)} D05/D08/D12.776 descriptor terms in chemicals output: {sorted(overlap)[:10]}"
    )


@pytest.mark.pipeline
def test_every_mesh_record_with_an_ncbitaxon_registry_number_is_taxon_only(mesh_pipeline_outputs, mesh_registry):
    """Every MeSH record NLM gives an NCBI Taxon registry number ("txid...") should be in the taxon ids/MESH and
    in no other pipeline's (#1240). Another pipeline claiming one would put its MeSH ID in two compendia, the
    second time through the NCBI_MESH concord into an NCBITaxon-led clique. Against MeSH 2026 there were 8 such
    SCR_Chemical virus records, e.g. MESH:C000626778 "maize chlorotic mottle virus"."""
    with_ncbitaxon = read_mesh_ids_with_ncbitaxon(mesh_registry)
    assert with_ncbitaxon, "No MeSH records with an NCBI Taxon registry number; has the registry format changed?"
    missing_from_taxon = with_ncbitaxon - get_curies_from_ids_file(mesh_pipeline_outputs["taxon"])
    assert not missing_from_taxon, f"{len(missing_from_taxon)} not in taxon: {sorted(missing_from_taxon)[:10]}"
    for pipeline, ids_file in mesh_pipeline_outputs.items():
        if pipeline != "taxon":
            claimed = with_ncbitaxon & get_curies_from_ids_file(ids_file)
            assert not claimed, f"{pipeline} claims {len(claimed)}: {sorted(claimed)[:10]}"
