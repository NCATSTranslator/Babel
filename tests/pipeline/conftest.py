"""Session-scoped fixtures for pipeline tests.

Pipeline tests download their own prerequisite files (or check network connectivity).
If a prerequisite is unavailable, all dependent tests are skipped automatically.

Processing fixtures write intermediate ID files to the same stable paths that
Snakemake uses: {intermediate_directory}/{semantic_type}/ids/{vocab}
(e.g. babel_outputs/intermediate/anatomy/ids/UMLS).  By default, if a file
already exists it is reused without re-running write_X_ids().  Pass --regenerate
to force re-processing even when files are present.

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
# Shared helpers (not fixtures — importable by test files)
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


# Fixture compendium keys whose Snakemake semantic-type directory differs from the key name.
_COMPENDIUM_TO_SNAKEMAKE_DIR = {
    "diseasephenotype": "disease",
    "processactivity":  "process",
}


def _intermediate_id_path(compendium: str, vocab: str) -> str:
    """Stable output path matching the Snakemake convention:
    {intermediate_directory}/{semantic_type}/ids/{vocab}

    Uses the same paths as the Snakemake pipeline so that a prior full pipeline
    run can be reused directly without re-running write_X_ids().
    """
    from src.util import get_config
    cfg = get_config()
    snakemake_dir = _COMPENDIUM_TO_SNAKEMAKE_DIR.get(compendium, compendium)
    return os.path.join(cfg["intermediate_directory"], snakemake_dir, "ids", vocab)


def _maybe_run(outfile: str, fn, regenerate: bool) -> str:
    """Run fn() to (re)generate outfile unless it exists and regenerate is False.

    fn is a zero-argument callable (typically a lambda) that writes to outfile.
    Creates parent directories as needed.  Always returns outfile.
    """
    if not os.path.exists(outfile) or regenerate:
        os.makedirs(os.path.dirname(outfile), exist_ok=True)
        fn()
    return outfile


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
# --regenerate fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def regenerate(request):
    """True when --regenerate was passed on the command line.

    Processing fixtures check this to decide whether to re-run write_X_ids()
    even when their output file already exists at the stable intermediate path.
    """
    return request.config.getoption("--regenerate")


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
def mesh_pipeline_outputs(mesh_nt, regenerate):
    """Run write_mesh_ids for all five compendia; skip if mesh_nt unavailable.

    Output files are written to babel_outputs/intermediate/{type}/ids/MESH and
    reused on subsequent runs unless --regenerate is passed.
    """
    def p(compendium):
        return _intermediate_id_path(compendium, "MESH")

    _maybe_run(p("chemicals"),        lambda: chemicals.write_mesh_ids(p("chemicals")),              regenerate)
    _maybe_run(p("protein"),          lambda: protein.write_mesh_ids(p("protein")),                  regenerate)
    _maybe_run(p("anatomy"),          lambda: anatomy.write_mesh_ids(p("anatomy")),                  regenerate)
    _maybe_run(p("diseasephenotype"), lambda: diseasephenotype.write_mesh_ids(p("diseasephenotype")), regenerate)
    _maybe_run(p("taxon"),            lambda: taxon.write_mesh_ids(p("taxon")),                      regenerate)

    m = Mesh()
    excluded_tree_terms = set()
    for tree in ["D05", "D08", "D12.776"]:
        excluded_tree_terms.update(m.get_terms_in_tree(tree))

    return {
        "chemicals":           p("chemicals"),
        "protein":             p("protein"),
        "anatomy":             p("anatomy"),
        "diseasephenotype":    p("diseasephenotype"),
        "taxon":               p("taxon"),
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
def umls_pipeline_outputs(umls_rrf_files, regenerate):
    """Run write_umls_ids for all seven compendia; returns dict of output paths.

    Output files are written to babel_outputs/intermediate/{type}/ids/UMLS and
    reused on subsequent runs unless --regenerate is passed.
    """
    from src.createcompendia import gene, processactivitypathway
    from src.util import get_config

    mrconso = umls_rrf_files["mrconso"]
    mrsty = umls_rrf_files["mrsty"]
    cfg = get_config()
    badumlsfile = os.path.join(cfg["input_directory"], "badumls")

    def p(compendium):
        return _intermediate_id_path(compendium, "UMLS")

    _maybe_run(p("chemicals"),       lambda: chemicals.write_umls_ids(mrsty, p("chemicals")),                          regenerate)
    _maybe_run(p("protein"),         lambda: protein.write_umls_ids(mrsty, p("protein")),                              regenerate)
    _maybe_run(p("anatomy"),         lambda: anatomy.write_umls_ids(mrsty, p("anatomy")),                              regenerate)
    _maybe_run(p("diseasephenotype"), lambda: diseasephenotype.write_umls_ids(mrsty, p("diseasephenotype"), badumlsfile), regenerate)
    _maybe_run(p("processactivity"), lambda: processactivitypathway.write_umls_ids(mrsty, p("processactivity")),       regenerate)
    _maybe_run(p("taxon"),           lambda: taxon.write_umls_ids(mrsty, p("taxon")),                                  regenerate)
    _maybe_run(p("gene"),            lambda: gene.write_umls_ids(mrconso, mrsty, p("gene")),                           regenerate)

    return {name: p(name) for name in ["chemicals", "protein", "anatomy", "diseasephenotype", "processactivity", "taxon", "gene"]}


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
def omim_pipeline_outputs(omim_mim2gene, regenerate):
    """Run write_omim_ids for disease/phenotype and gene; skip if mim2gene.txt unavailable.

    Output files are written to babel_outputs/intermediate/{type}/ids/OMIM and
    reused on subsequent runs unless --regenerate is passed.
    """
    from src.createcompendia import gene
    infile = omim_mim2gene

    def p(compendium):
        return _intermediate_id_path(compendium, "OMIM")

    _maybe_run(p("diseasephenotype"), lambda: diseasephenotype.write_omim_ids(infile, p("diseasephenotype")), regenerate)
    _maybe_run(p("gene"),             lambda: gene.write_omim_ids(infile, p("gene")),                         regenerate)

    return {"diseasephenotype": p("diseasephenotype"), "gene": p("gene")}


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
def ncit_pipeline_outputs(ubergraph_connection, regenerate):
    """Run write_ncit_ids for anatomy and disease/phenotype via UberGraph.

    Output files are written to babel_outputs/intermediate/{type}/ids/NCIT and
    reused on subsequent runs unless --regenerate is passed.
    """
    def p(compendium):
        return _intermediate_id_path(compendium, "NCIT")

    _maybe_run(p("anatomy"),          lambda: anatomy.write_ncit_ids(p("anatomy")),              regenerate)
    _maybe_run(p("diseasephenotype"), lambda: diseasephenotype.write_ncit_ids(p("diseasephenotype")), regenerate)

    return {"anatomy": p("anatomy"), "diseasephenotype": p("diseasephenotype")}


# ---------------------------------------------------------------------------
# GO processing fixture (uses UberGraph, no file download)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def go_pipeline_outputs(ubergraph_connection, regenerate):
    """Run write_go_ids for anatomy and process/activity/pathway via UberGraph.

    Output files are written to babel_outputs/intermediate/{type}/ids/GO and
    reused on subsequent runs unless --regenerate is passed.
    """
    from src.createcompendia import processactivitypathway

    def p(compendium):
        return _intermediate_id_path(compendium, "GO")

    _maybe_run(p("anatomy"),         lambda: anatomy.write_go_ids(p("anatomy")),                       regenerate)
    _maybe_run(p("processactivity"), lambda: processactivitypathway.write_go_ids(p("processactivity")), regenerate)

    return {"anatomy": p("anatomy"), "processactivity": p("processactivity")}


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
