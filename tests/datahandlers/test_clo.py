"""Unit tests for src/datahandlers/clo.py (CLOgraph)."""
import io

import pyoxigraph
import pytest

from src.categories import CELL_LINE
from src.datahandlers.clo import CLOgraph
from src.prefixes import CLO
from tests.datahandlers.conftest import RDFS_NS, SKOS_NS, lit, make_graph_from_store, nn, quad

_CLO_NS = "http://purl.obolibrary.org/obo/CLO_"
_MONDO_NS = "http://purl.obolibrary.org/obo/MONDO_"
_MONDOH_NS = "http://purl.obolibrary.org/obo/mondo#"
_OBO_NS = "http://www.geneontology.org/formats/oboInOwl#"
_ORPHANET_IRI = "http://www.orpha.net/ORDO/Orphanet_123456"


def _make_clo_store() -> pyoxigraph.Store:
    """In-memory Store covering all CLOgraph methods.

    CLO:0000001 — root; prefLabel + altLabel + lang-tagged rdfs:label
                  + SKOS exactMatch to MONDO (valid)
                  + SKOS exactMatch to Orphanet (should be filtered)
                  + hasDbXref "MESH:D001234" (valid CURIE xref)
                  + hasDbXref "not-a-curie" (invalid, skipped)

    CLO:0000002 — subClassOf CLO:0000001
    EX:NOTACLO  — non-CLO_ IRI; skipped by label/id methods
    """
    store = pyoxigraph.Store()
    root = nn(f"{_CLO_NS}0000001")
    child = nn(f"{_CLO_NS}0000002")
    not_clo = nn("http://example.org/NOTACLO")

    store.add(quad(root, nn(f"{SKOS_NS}prefLabel"), lit("HeLa cell")))
    store.add(quad(root, nn(f"{SKOS_NS}altLabel"), lit("HeLa")))
    store.add(quad(root, nn(f"{RDFS_NS}label"), lit("HeLa cell", language="en")))

    store.add(quad(not_clo, nn(f"{SKOS_NS}prefLabel"), lit("Something else")))

    store.add(quad(child, nn(f"{RDFS_NS}subClassOf"), root))
    store.add(quad(child, nn(f"{SKOS_NS}prefLabel"), lit("Child cell line")))

    store.add(quad(root, nn(f"{SKOS_NS}exactMatch"), nn(f"{_MONDO_NS}0001234")))
    store.add(quad(root, nn(f"{SKOS_NS}exactMatch"), nn(_ORPHANET_IRI)))
    store.add(quad(root, nn(f"{_MONDOH_NS}exactMatch"), nn(f"{_MONDO_NS}9999999")))

    store.add(quad(root, nn(f"{_OBO_NS}hasDbXref"), lit("MESH:D001234")))
    store.add(quad(root, nn(f"{_OBO_NS}hasDbXref"), lit("not-a-curie")))

    return store


@pytest.fixture(scope="module")
def clograph():
    return make_graph_from_store(CLOgraph, _make_clo_store())


@pytest.fixture(scope="module")
def clo_output(clograph, tmp_path_factory):
    """Run label/synonym extraction once and return the file contents."""
    tmp = tmp_path_factory.mktemp("clo")
    lf = str(tmp / "labels.tsv")
    sf = str(tmp / "syns.tsv")
    clograph.pull_CLO_labels_and_synonyms(lf, sf)
    return {"labels": (tmp / "labels.tsv").read_text(), "syns": (tmp / "syns.tsv").read_text()}


# ---------------------------------------------------------------------------
# pull_CLO_labels_and_synonyms
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_CLO_labels_writes_preflabel(clo_output):
    assert f"{CLO}:0000001\tHeLa cell" in clo_output["labels"]
    assert f"{CLO}:0000001\tskos:prefLabel\tHeLa cell" in clo_output["syns"]


@pytest.mark.unit
def test_pull_CLO_labels_altlabel_in_syn_only(clo_output):
    label_lines = [line for line in clo_output["labels"].splitlines() if "HeLa" in line and "HeLa cell" not in line]
    assert not label_lines
    assert f"{CLO}:0000001\tskos:altLabel\tHeLa" in clo_output["syns"]


@pytest.mark.unit
def test_pull_CLO_labels_strips_language_tag(clo_output):
    assert "@en" not in clo_output["labels"]


@pytest.mark.unit
def test_pull_CLO_labels_skips_non_clo_prefix(clo_output):
    assert "Something else" not in clo_output["labels"]


# ---------------------------------------------------------------------------
# pull_CLO_ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_CLO_ids_writes_descendants(clograph, tmp_path):
    out = str(tmp_path / "ids.tsv")
    clograph.pull_CLO_ids([("CLO:0000001", CELL_LINE)], out)
    curies = [line.split("\t")[0] for line in (tmp_path / "ids.tsv").read_text().splitlines()]
    assert f"{CLO}:0000001" in curies
    assert f"{CLO}:0000002" in curies


# ---------------------------------------------------------------------------
# get_exacts  (uses full IRI in angle brackets because CLO prefix is not
# declared in the get_exacts SPARQL query)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_exacts_skos_exactmatch(clograph):
    out = io.StringIO()
    clograph.get_exacts(f"<{_CLO_NS}0000001>", out)
    assert "skos:exactMatch\tMONDO:0001234" in out.getvalue()


@pytest.mark.unit
def test_get_exacts_filters_orphanet(clograph):
    out = io.StringIO()
    clograph.get_exacts(f"<{_CLO_NS}0000001>", out)
    for line in out.getvalue().splitlines():
        assert "orphanet" not in line.lower(), f"Unexpected Orphanet line: {line}"


# ---------------------------------------------------------------------------
# get_xrefs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_xrefs_writes_valid_curie(clograph):
    out = io.StringIO()
    clograph.get_xrefs(f"<{_CLO_NS}0000001>", out)
    assert "oboInOwl:hasDbXref\tMESH:D001234" in out.getvalue()


@pytest.mark.unit
def test_get_xrefs_skips_non_curie(clograph):
    out = io.StringIO()
    clograph.get_xrefs(f"<{_CLO_NS}0000001>", out)
    assert "not-a-curie" not in out.getvalue()
