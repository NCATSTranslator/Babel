"""Session-scoped fixture for MeSH pipeline tests.

Requires babel_downloads/MESH/mesh.nt to be pre-populated.
All tests in this package are marked `pipeline` and are skipped by default.
Run with:  PYTHONPATH=. uv run pytest tests/pipeline/ --pipeline --no-cov -v
"""
import os

import pytest

from src.createcompendia import chemicals, protein
from src.datahandlers.mesh import Mesh

MESH_NT = "babel_downloads/MESH/mesh.nt"


@pytest.fixture(scope="session")
def mesh_pipeline_outputs(tmp_path_factory):
    if not os.path.exists(MESH_NT):
        pytest.skip(f"{MESH_NT} not found; populate babel_downloads/ before running pipeline tests")

    outdir = tmp_path_factory.mktemp("mesh_ids")
    chem_outfile = str(outdir / "chemical_MESH")
    prot_outfile = str(outdir / "protein_MESH")

    chemicals.write_mesh_ids(chem_outfile)
    protein.write_mesh_ids(prot_outfile)

    m = Mesh()
    excluded_tree_terms = set()
    for tree in ["D05", "D08", "D12.776"]:
        excluded_tree_terms.update(m.get_terms_in_tree(tree))

    return {
        "chemicals": chem_outfile,
        "protein": prot_outfile,
        "excluded_tree_terms": excluded_tree_terms,
    }
