"""MeSH-specific pipeline tests (issue #675).

The generic non-empty and mutual-exclusivity tests for all five MeSH compendia
(chemicals, protein, anatomy, disease/phenotype, taxon) are in
test_vocabulary_partitioning.py.  This file contains the MeSH-specific
targeted tests that have no generic equivalent.

All pipeline tests are skipped by default unless PyTest is run with `--pipeline`.  Run with:
    uv run pytest tests/pipeline/test_mesh.py --pipeline --no-cov -v
"""

from collections import Counter

import pytest

from src.createcompendia.chemicals import is_cas
from src.datahandlers.mesh import pull_mesh_registry
from tests.pipeline.conftest import get_curies_from_ids_file

# Lower bounds on the registry numbers MeSH's preferred concepts carry, at roughly 70% of the counts in
# the MeSH 2026 XML (desc2026/supp2026): 68,780 txid, 48,610 CAS and 17,954 other (mostly UNII). Low
# enough to survive normal churn between releases, high enough that losing the registry query's
# predicate -- which leaves it returning nothing at all -- fails loudly.
MIN_TXID_REGISTRY_NUMBERS = 50_000
MIN_CAS_REGISTRY_NUMBERS = 35_000
MIN_UNII_REGISTRY_NUMBERS = 12_000


@pytest.fixture(scope="session")
def mesh_registry(mesh_nt):
    """(MeSH CURIE, registry number) pairs from Mesh.get_registry(), the query the taxon and chemical
    pipelines build their MeSH -> NCBITaxon, CAS and UNII concords from."""
    return pull_mesh_registry()


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
def test_mesh_registry_links_taxa_to_ncbitaxon(mesh_registry):
    """The MeSH registry should yield txid registry numbers, which the NCBI_MESH taxon concord is made from.

    Mesh.get_registry() reads meshv:registryNumber on each record's preferred concept. A mesh.nt without
    that predicate makes it return nothing, which silently empties the MeSH -> NCBITaxon concord. The
    known pair is MeSH "Gymnopus dryophilus", which cites txid206318 in the MeSH 2026 XML.
    """
    txids = [reg for _, reg in mesh_registry if reg.startswith("txid")]
    assert len(txids) >= MIN_TXID_REGISTRY_NUMBERS, (
        f"only {len(txids):,} txid registry numbers in the MeSH registry (of {len(mesh_registry):,} in all)"
    )
    assert ("MESH:C000672803", "txid206318") in set(mesh_registry)


@pytest.mark.pipeline
def test_mesh_registry_has_cas_and_unii_numbers(mesh_registry):
    """The MeSH registry should yield CAS and UNII registry numbers for the chemical MeSH concords.

    chemicals.get_mesh_relationships() sorts the same registry into CAS and UNII concords, so it fails the
    same way the taxon concord does. The known pair is "Water", whose registry number is its UNII.
    """
    kinds = Counter(
        "txid" if reg.startswith("txid") else "EC" if reg.startswith("EC") else "CAS" if is_cas(reg) else "UNII"
        for _, reg in mesh_registry
    )
    assert kinds["CAS"] >= MIN_CAS_REGISTRY_NUMBERS, f"only {kinds['CAS']:,} CAS registry numbers: {dict(kinds)}"
    assert kinds["UNII"] >= MIN_UNII_REGISTRY_NUMBERS, f"only {kinds['UNII']:,} UNII registry numbers: {dict(kinds)}"
    assert ("MESH:D014867", "059QF0KO0R") in set(mesh_registry)
