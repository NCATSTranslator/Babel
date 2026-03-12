"""Session-scoped fixtures for pipeline tests.

Pipeline tests download their own prerequisite files (or check network connectivity).
If a prerequisite is unavailable, all dependent tests are skipped automatically.

All tests in this package are marked `pipeline` and are skipped by default.
Run with:  PYTHONPATH=. uv run pytest tests/pipeline/ --pipeline --no-cov -v

## Adding a new vocabulary

1. Add a download/connectivity fixture (e.g. `my_vocab_source`) to this file.
2. Add a processing fixture (e.g. `my_vocab_pipeline_outputs`) that depends on it and
   returns a dict of {compendium_name: output_path}.
3. Add one entry to VOCABULARY_REGISTRY: `"MYVOCAB": "my_vocab_pipeline_outputs"`.
That's it — test_vocabulary_partitioning.py picks it up automatically.
"""
import os

import pytest

from src.babel_utils import make_local_name
from src.createcompendia import anatomy, chemicals, diseasephenotype, protein, taxon
from src.datahandlers.mesh import Mesh, pull_mesh

# ---------------------------------------------------------------------------
# Shared helper (not a fixture — importable by test files)
# ---------------------------------------------------------------------------


def _read_ids(path: str) -> set[str]:
    """Return the set of CURIEs (first column) from a TSV output file."""
    ids = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(line.split("\t")[0])
    return ids


# ---------------------------------------------------------------------------
# Generic download helper
# ---------------------------------------------------------------------------


def _download_or_skip(label: str, pull_fn, expected_path: str) -> str:
    """Download expected_path via pull_fn() if absent; pytest.skip() on failure."""
    if not os.path.exists(expected_path):
        try:
            pull_fn()
        except Exception as e:
            pytest.skip(f"Could not download {label}: {e}")
    return expected_path


# ---------------------------------------------------------------------------
# MESH download + processing fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mesh_nt():
    """Download babel_downloads/MESH/mesh.nt, or skip if unavailable."""
    return _download_or_skip(
        "MESH mesh.nt",
        pull_mesh,
        make_local_name("mesh.nt", subpath="MESH"),
    )


@pytest.fixture(scope="session")
def mesh_pipeline_outputs(mesh_nt, tmp_path_factory):
    """Run write_mesh_ids for all five compendia; skip if mesh_nt unavailable."""
    outdir = tmp_path_factory.mktemp("mesh_ids")

    def out(name):
        return str(outdir / f"{name}_MESH")

    chemicals.write_mesh_ids(out("chemicals"))
    protein.write_mesh_ids(out("protein"))
    anatomy.write_mesh_ids(out("anatomy"))
    diseasephenotype.write_mesh_ids(out("diseasephenotype"))
    taxon.write_mesh_ids(out("taxon"))

    m = Mesh()
    excluded_tree_terms = set()
    for tree in ["D05", "D08", "D12.776"]:
        excluded_tree_terms.update(m.get_terms_in_tree(tree))

    return {
        "chemicals":        out("chemicals"),
        "protein":          out("protein"),
        "anatomy":          out("anatomy"),
        "diseasephenotype": out("diseasephenotype"),
        "taxon":            out("taxon"),
        "excluded_tree_terms": excluded_tree_terms,
    }


# ---------------------------------------------------------------------------
# UMLS download + processing fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def umls_rrf_files():
    """Ensure MRCONSO.RRF and MRSTY.RRF are present; skip if files are absent and download fails."""
    mrconso = make_local_name("MRCONSO.RRF", subpath="UMLS")
    mrsty = make_local_name("MRSTY.RRF", subpath="UMLS")

    if not os.path.exists(mrconso) or not os.path.exists(mrsty):
        # UMLS_API_KEY is only required when the files are not yet cached.
        if not os.environ.get("UMLS_API_KEY"):
            pytest.skip("UMLS_API_KEY not set and UMLS files not cached; cannot download UMLS files")
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


@pytest.fixture(scope="session")
def umls_pipeline_outputs(umls_rrf_files, tmp_path_factory):
    """Run write_umls_ids for all seven compendia; returns dict of output paths."""
    from src.createcompendia import gene, processactivitypathway
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


# ---------------------------------------------------------------------------
# OMIM download + processing fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def omim_mim2gene():
    """Download babel_downloads/OMIM/mim2gene.txt, or skip if unavailable."""
    from src.datahandlers.omim import pull_omim
    return _download_or_skip(
        "OMIM mim2gene.txt",
        pull_omim,
        make_local_name("mim2gene.txt", subpath="OMIM"),
    )


@pytest.fixture(scope="session")
def omim_pipeline_outputs(omim_mim2gene, tmp_path_factory):
    """Run write_omim_ids for disease/phenotype and gene; skip if mim2gene.txt unavailable."""
    from src.createcompendia import gene
    infile = omim_mim2gene
    outdir = tmp_path_factory.mktemp("omim_ids")

    def out(name):
        return str(outdir / f"{name}_OMIM")

    diseasephenotype.write_omim_ids(infile, out("diseasephenotype"))
    gene.write_omim_ids(infile, out("gene"))

    return {
        "diseasephenotype": out("diseasephenotype"),
        "gene":             out("gene"),
    }


# ---------------------------------------------------------------------------
# UberGraph connectivity fixture (shared prerequisite for NCIT and GO)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ubergraph_connection():
    """Verify the UberGraph SPARQL endpoint is reachable; skip if not.

    NCIT and GO use write_obo_ids() which queries UberGraph live — there is no
    local file to download.  This fixture acts as the prerequisite check that
    both ncit_pipeline_outputs and go_pipeline_outputs depend on.
    """
    try:
        from src.datahandlers.obo import UberGraph
        ug = UberGraph()
        # Minimal health check: GO:0005575 (cellular component) is a small, stable term.
        result = ug.get_subclasses_of("GO:0005575")
        if not result:
            pytest.skip("UberGraph returned empty result; endpoint may be unavailable")
    except Exception as e:
        pytest.skip(f"UberGraph not accessible: {e}")


# ---------------------------------------------------------------------------
# NCIT processing fixture (uses UberGraph, no file download)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ncit_pipeline_outputs(ubergraph_connection, tmp_path_factory):
    """Run write_ncit_ids for anatomy and disease/phenotype via UberGraph."""
    outdir = tmp_path_factory.mktemp("ncit_ids")

    def out(name):
        return str(outdir / f"{name}_NCIT")

    anatomy.write_ncit_ids(out("anatomy"))
    diseasephenotype.write_ncit_ids(out("diseasephenotype"))

    return {
        "anatomy":          out("anatomy"),
        "diseasephenotype": out("diseasephenotype"),
    }


# ---------------------------------------------------------------------------
# GO processing fixture (uses UberGraph, no file download)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def go_pipeline_outputs(ubergraph_connection, tmp_path_factory):
    """Run write_go_ids for anatomy and process/activity/pathway via UberGraph."""
    from src.createcompendia import processactivitypathway
    outdir = tmp_path_factory.mktemp("go_ids")

    def out(name):
        return str(outdir / f"{name}_GO")

    anatomy.write_go_ids(out("anatomy"))
    processactivitypathway.write_go_ids(out("processactivity"))

    return {
        "anatomy":       out("anatomy"),
        "processactivity": out("processactivity"),
    }


# ---------------------------------------------------------------------------
# Vocabulary registry + parametrized fixture for test_vocabulary_partitioning.py
# ---------------------------------------------------------------------------

# Maps vocabulary name → processing fixture name.
# Each processing fixture returns a {compendium_name: output_path} dict.
# To add a new vocabulary: add its fixtures above, then add one line here.
VOCABULARY_REGISTRY = {
    "MESH": "mesh_pipeline_outputs",
    "UMLS": "umls_pipeline_outputs",
    "OMIM": "omim_pipeline_outputs",
    "NCIT": "ncit_pipeline_outputs",
    "GO":   "go_pipeline_outputs",
}


@pytest.fixture(scope="session", params=list(VOCABULARY_REGISTRY.keys()))
def vocab_outputs(request):
    """Parametrized fixture yielding (vocab_name, outputs_dict) for each registered vocabulary.

    Uses request.getfixturevalue() so only the fixture for the current vocabulary is
    instantiated — a skip in UMLS does not prevent OMIM or MESH from running.
    """
    fixture_name = VOCABULARY_REGISTRY[request.param]
    outputs = request.getfixturevalue(fixture_name)
    return request.param, outputs
