"""Pipeline tests that run the build's UMLS/MeSH version checks ahead of a build, on the real downloads.

The build fails early when config.yaml's mesh_year has fallen behind its umls_version (rule check_umls_mesh_skew,
see docs/sources/MeSH/Ingestion.md, "Source data"). These tests run the same check against the configured
releases, so a version bump finds out before a cluster run. They download UMLS (about 5.5 GB for the full subset,
which needs UMLS_API_KEY) and MeSH if they are not already cached. Run with:
    uv run pytest tests/pipeline/test_umls_mesh_skew.py --pipeline --no-cov -v
"""

import json

import pytest

from src.babel_utils import make_local_name
from src.datahandlers.mesh import read_mesh_rdf_year
from src.reports.umls_mesh_skew import check_umls_mesh_skew, generate_umls_mesh_skew_report
from src.util import get_config
from tests.pipeline.conftest import cached_umls_release


@pytest.mark.pipeline
def test_cached_umls_is_the_configured_release(umls_rrf_files):
    """The UMLS files the other pipeline tests read should be config.yaml's umls_version and subset, not a
    release left over from before a version bump."""
    cfg = get_config()
    assert cached_umls_release(cfg["download_directory"] + "/UMLS") == (
        str(cfg["umls_version"]),
        str(cfg["umls"]["subset"]),
    )


@pytest.mark.pipeline
def test_configured_mesh_year_is_not_behind_configured_umls(umls_rrf_files, mesh_nt, mesh_labels, tmp_path):
    """The build's own skew check should pass on the configured UMLS and MeSH releases: at most
    umls_mesh_skew_max_missing_codes MSH codes in MRCONSO.RRF may lack a record in the mesh_year dump. If this
    fails after a umls_version bump, set mesh_year to the MeSH year that UMLS release carries (see
    check_umls_mesh_skew()'s message), rather than raising the limit to make the test pass."""
    cfg = get_config()
    report_path = tmp_path / "umls_mesh_skew.json"
    # The same inputs rule generate_umls_mesh_skew_report passes: the dump's labels, and its year as downloaded.
    mesh_year = read_mesh_rdf_year(make_local_name("rdf_source.json", subpath="MESH"))
    assert mesh_year == str(cfg["mesh_year"]), f"The cached mesh.nt is MeSH {mesh_year}, not the configured one"
    generate_umls_mesh_skew_report(umls_rrf_files["mrconso"], mesh_labels, cfg["umls_version"], mesh_year, report_path)
    report = json.loads(report_path.read_text())
    print(json.dumps({k: v for k, v in report.items() if k != "missing_sample"}, indent=2))
    check_umls_mesh_skew(report_path, cfg["umls_mesh_skew_max_missing_codes"], tmp_path / "umls_mesh_skew.checked")
