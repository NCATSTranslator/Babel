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


# ---------------------------------------------------------------------------
# UMLS download fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def umls_rrf_files():
    """Ensure MRCONSO.RRF and MRSTY.RRF are present; skip if UMLS_API_KEY unset or download fails."""
    if not os.environ.get("UMLS_API_KEY"):
        pytest.skip("UMLS_API_KEY not set; cannot download UMLS files")

    mrconso = make_local_name("MRCONSO.RRF", subpath="UMLS")
    mrsty = make_local_name("MRSTY.RRF", subpath="UMLS")

    if not os.path.exists(mrconso) or not os.path.exists(mrsty):
        try:
            from src.datahandlers import umls as umls_handler
            from src.util import get_config
            cfg = get_config()
            umls_handler.download_umls(
                cfg["umls_version"],
                cfg["umls"]["subset"],
                cfg["download_directory"] + "/UMLS",
            )
        except Exception as e:
            pytest.skip(f"Could not download UMLS: {e}")

    return {"mrconso": mrconso, "mrsty": mrsty}


# ---------------------------------------------------------------------------
# UMLS processing fixture (depends on umls_rrf_files)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def umls_pipeline_outputs(umls_rrf_files, tmp_path_factory):
    """Run write_umls_ids for all seven compendia; returns dict of output paths."""
    from src.createcompendia import (
        anatomy, diseasephenotype, gene,
        processactivitypathway, taxon,
    )
    from src.util import get_config

    mrconso = umls_rrf_files["mrconso"]
    mrsty = umls_rrf_files["mrsty"]
    cfg = get_config()
    badumlsfile = os.path.join(cfg["input_directory"], "badumls")
    outdir = tmp_path_factory.mktemp("umls_ids")

    def out(name):
        return str(outdir / f"{name}_UMLS")

    chemicals.write_umls_ids(mrsty, out("chemicals"))
    protein.write_umls_ids(mrsty, out("protein"))
    anatomy.write_umls_ids(mrsty, out("anatomy"))
    diseasephenotype.write_umls_ids(mrsty, out("diseasephenotype"), badumlsfile)
    processactivitypathway.write_umls_ids(mrsty, out("processactivity"))
    taxon.write_umls_ids(mrsty, out("taxon"))
    gene.write_umls_ids(mrconso, mrsty, out("gene"))

    return {
        "chemicals":        out("chemicals"),
        "protein":          out("protein"),
        "anatomy":          out("anatomy"),
        "diseasephenotype": out("diseasephenotype"),
        "processactivity":  out("processactivity"),
        "taxon":            out("taxon"),
        "gene":             out("gene"),
    }
