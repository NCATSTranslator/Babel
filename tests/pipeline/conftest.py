"""Session-scoped fixtures for pipeline tests.

Processing fixtures write intermediate ID files to the same stable paths that Snakemake
uses: {intermediate_directory}/{snakemake_dir}/ids/{vocab}, where snakemake_dir is the
compendium name unless overridden by compendium_directories in config.yaml (e.g.
diseasephenotype → disease).  Example: babel_outputs/intermediate/anatomy/ids/UMLS.

By default, if a file already exists it is reused without re-running write_X_ids().
Pass --regenerate to force re-processing even when files are present.

Prerequisites vary by vocabulary:
- MESH, OMIM: fixtures auto-download the required file if absent.
- UMLS: requires UMLS_API_KEY when files are not already cached.
- NCIT, GO: require a live UberGraph SPARQL endpoint (no file download).
If a prerequisite is unavailable, all dependent tests are skipped automatically.

All tests in this package are marked `pipeline` and are skipped by default.
Run with:  uv run pytest tests/pipeline/ --pipeline --no-cov -v

## Adding a new vocabulary

1. Add a download/connectivity fixture (e.g. `my_vocab_source`) to this file.
2. Add a processing fixture (e.g. `my_vocab_pipeline_outputs`) that calls all
   write_X_ids() functions for that vocabulary and returns {compendium_name: output_path}.
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


def _read_ids_with_types(path: str) -> dict[str, str | None]:
    """Return {CURIE: biolink_type_or_None} from an intermediate ID file.

    The optional second column is a Biolink type hint written by write_umls_ids() and
    similar functions.  If absent (e.g. MESH), the value is None.
    """
    result = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split("\t")
                result[parts[0]] = parts[1] if len(parts) > 1 else None
    return result


def _intermediate_concord_path(compendium: str, vocab: str) -> str:
    """Stable concord path: {intermediate_directory}/{snakemake_dir}/concords/{vocab}."""
    from src.util import get_config
    cfg = get_config()
    directory_map = cfg.get("compendium_directories", {})
    snakemake_dir = directory_map.get(compendium, compendium)
    return os.path.join(cfg["intermediate_directory"], snakemake_dir, "concords", vocab)


def _any_concord_xrefs(concords_dir: str, curie1: str, curie2: str) -> bool:
    """Return True if curie1 and curie2 are a direct xref pair in ANY concord file under concords_dir.

    Scans every regular file in concords_dir (skipping .yaml metadata files and subdirectories).
    Concord files are tab-separated <curie1> <relation> <curie2> triples; this function checks
    the first and last columns only (skipping the relation), so column order does not matter.
    Indirect equivalences through multi-hop chains are not detected — this is intentional: it's
    fast for TDD and locates the specific concord file that is the source of a bad link.
    """
    for entry in os.scandir(concords_dir):
        if not entry.is_file() or entry.name.endswith(".yaml"):
            continue
        try:
            with open(entry.path) as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        curies = {parts[0], parts[-1]}
                        if curie1 in curies and curie2 in curies:
                            return True
        except (OSError, UnicodeDecodeError):
            continue
    return False


def _output_paths(outputs: dict) -> dict[str, str]:
    """Filter a vocab_outputs dict down to just the string-valued output paths.

    Some fixtures return extra non-path data alongside their output paths — for example,
    mesh_pipeline_outputs includes 'excluded_tree_terms' (a set of descriptor CURIEs) for
    use by test_mesh_pipeline.py.  This helper strips non-string values so callers can
    iterate over compendium output files without special-casing each vocabulary.
    """
    return {name: path for name, path in outputs.items() if isinstance(path, str)}


def _intermediate_id_path(compendium: str, vocab: str) -> str:
    """Return {intermediate_directory}/{snakemake_dir}/ids/{vocab}, matching the Snakemake path.

    snakemake_dir is looked up from compendium_directories in config.yaml and falls back to
    the compendium name (e.g. diseasephenotype → disease, processactivitypathway → process).
    Using the same paths as Snakemake means files from a prior pipeline run are reused directly.
    """
    from src.util import get_config
    cfg = get_config()
    directory_map = cfg.get("compendium_directories", {})
    snakemake_dir = directory_map.get(compendium, compendium)
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
# Snakemake-backed pipeline output fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pipeline_output(regenerate):
    """Factory: ensure a Snakemake rule has produced its output file; return the path.

    Reuses existing files without re-running (same caching contract as _maybe_run).
    If the file is absent, runs `uv run snakemake --cores 1 --until <rule>`.
    Skips all dependent tests if Snakemake fails or the output is not produced.

    Usage inside a fixture:
        @pytest.fixture(scope="session")
        def my_fixture(pipeline_output):
            return pipeline_output("my_snakemake_rule", "path/to/output")
    """
    import subprocess

    def _get(rule: str, path: str) -> str:
        if os.path.exists(path) and not regenerate:
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        result = subprocess.run(
            ["uv", "run", "snakemake", "--cores", "1", "--until", rule],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not os.path.exists(path):
            pytest.skip(
                f"Snakemake rule '{rule}' did not produce {path}.\n"
                f"Run:  uv run snakemake --cores N --until {rule}\n"
                f"stderr: {result.stderr[:400]}"
            )
        return path

    return _get


# ---------------------------------------------------------------------------
# Chemicals concords directory fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def chemicals_concords_dir(pipeline_output):
    """Ensure at least one chemicals concord file is present; return the concords directory path.

    Uses wikipedia_mesh_chebi as a sentinel: if absent, runs Snakemake's
    get_chemical_wikipedia_relationships rule (no large downloads required, fast).
    Other concord files (UNICHEM, CHEBI, …) are used if already present from a prior full
    pipeline run, but are not generated automatically — UNICHEM in particular requires ~512 GB RAM.
    """
    from src.util import get_config
    cfg = get_config()
    directory_map = cfg.get("compendium_directories", {})
    snakemake_dir = directory_map.get("chemicals", "chemicals")
    concords_dir = os.path.join(cfg["intermediate_directory"], snakemake_dir, "concords")
    sentinel = os.path.join(concords_dir, "wikipedia_mesh_chebi")
    pipeline_output("get_chemical_wikipedia_relationships", sentinel)
    return concords_dir


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

    # Build excluded_tree_terms for test_mesh_pipeline.py: all descriptor CURIEs under
    # D05/D08/D12.776, including non-protein subtrees (Polymers, Coenzymes) that belong
    # in neither compendium.  A fresh Mesh() instance is needed because write_ids()
    # creates its own internally and doesn't expose it; the cost is paid once per session.
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
    _maybe_run(p("processactivitypathway"), lambda: processactivitypathway.write_umls_ids(mrsty, p("processactivitypathway")),       regenerate)
    _maybe_run(p("taxon"),           lambda: taxon.write_umls_ids(mrsty, p("taxon")),                                  regenerate)
    _maybe_run(p("gene"),            lambda: gene.write_umls_ids(mrconso, mrsty, p("gene")),                           regenerate)

    return {name: p(name) for name in ["chemicals", "protein", "anatomy", "diseasephenotype", "processactivitypathway", "taxon", "gene"]}


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
    _maybe_run(p("processactivitypathway"), lambda: processactivitypathway.write_go_ids(p("processactivitypathway")), regenerate)

    return {"anatomy": p("anatomy"), "processactivitypathway": p("processactivitypathway")}


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
