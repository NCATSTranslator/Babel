"""Session-scoped fixtures for pipeline tests.

Pipeline tests download their own prerequisite files. If a download fails
(network down, auth error, etc.) all dependent tests are skipped automatically.

All tests in this package are marked `pipeline` and are skipped by default.
Run with:  PYTHONPATH=. uv run pytest tests/pipeline/ --pipeline --no-cov -v
"""
import os

import pytest

from src.babel_utils import make_local_name
from src.createcompendia import chemicals, protein
from src.datahandlers.mesh import Mesh, pull_mesh


def _download_or_skip(label: str, pull_fn, expected_path: str) -> str:
    """Download expected_path via pull_fn() if absent; pytest.skip() on failure."""
    if not os.path.exists(expected_path):
        try:
            pull_fn()
        except Exception as e:
            pytest.skip(f"Could not download {label}: {e}")
    return expected_path


# ---------------------------------------------------------------------------
# Per-datasource download fixtures (one per datahandler)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mesh_nt():
    """Download babel_downloads/MESH/mesh.nt, or skip if unavailable."""
    return _download_or_skip(
        "MESH mesh.nt",
        pull_mesh,
        make_local_name("mesh.nt", subpath="MESH"),
    )


# ---------------------------------------------------------------------------
# Per-compendium processing fixtures (depend on download fixtures above)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mesh_pipeline_outputs(mesh_nt, tmp_path_factory):
    """Run chemicals/protein MeSH ID extraction; skip if mesh_nt unavailable."""
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
