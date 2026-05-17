"""Unit tests for src/datahandlers/clo.py (CLOgraph)."""
import io
from pathlib import Path

import pyoxigraph
import pytest

from src.categories import CELL_LINE
from src.datahandlers.clo import CLOgraph
from src.prefixes import CLO
from tests.datahandlers.conftest import lit, nn, quad

_CLO_NS = "http://purl.obolibrary.org/obo/CLO_"
_SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
_RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
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

    # Labels on root
    store.add(quad(root, nn(f"{_SKOS_NS}prefLabel"), lit("HeLa cell")))
    store.add(quad(root, nn(f"{_SKOS_NS}altLabel"), lit("HeLa")))
    store.add(quad(root, nn(f"{_RDFS_NS}label"), lit("HeLa cell", language="en")))

    # non-CLO_ entity — should be ignored
    store.add(quad(not_clo, nn(f"{_SKOS_NS}prefLabel"), lit("Something else")))

    # Hierarchy: child subClassOf root
    store.add(quad(child, nn(f"{_RDFS_NS}subClassOf"), root))
    store.add(quad(child, nn(f"{_SKOS_NS}prefLabel"), lit("Child cell line")))

    # Exact matches on root using full IRIs (CLO prefix not declared in get_exacts query)
    store.add(quad(root, nn(f"{_SKOS_NS}exactMatch"), nn(f"{_MONDO_NS}0001234")))
    store.add(quad(root, nn(f"{_SKOS_NS}exactMatch"), nn(_ORPHANET_IRI)))
    store.add(quad(root, nn(f"{_MONDOH_NS}exactMatch"), nn(f"{_MONDO_NS}9999999")))

    # xrefs on root
    store.add(quad(root, nn(f"{_OBO_NS}hasDbXref"), lit("MESH:D001234")))
    store.add(quad(root, nn(f"{_OBO_NS}hasDbXref"), lit("not-a-curie")))

    return store


def _make_clograph(store: pyoxigraph.Store) -> CLOgraph:
    obj = CLOgraph.__new__(CLOgraph)
    obj.m = store
    return obj


@pytest.fixture(scope="module")
def clograph():
    return _make_clograph(_make_clo_store())


# ---------------------------------------------------------------------------
# pull_CLO_labels_and_synonyms
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_CLO_labels_writes_preflabel(clograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    clograph.pull_CLO_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    syns = Path(sf).read_text()
    assert f"{CLO}:0000001\tHeLa cell" in labels
    assert f"{CLO}:0000001\tskos:prefLabel\tHeLa cell" in syns


@pytest.mark.unit
def test_pull_CLO_labels_altlabel_in_syn_only(clograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    clograph.pull_CLO_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    syns = Path(sf).read_text()
    # altLabel "HeLa" must not appear in label file
    label_lines = [line for line in labels.splitlines() if "HeLa" in line and "HeLa cell" not in line]
    assert not label_lines
    assert f"{CLO}:0000001\tskos:altLabel\tHeLa" in syns


@pytest.mark.unit
def test_pull_CLO_labels_strips_language_tag(clograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    clograph.pull_CLO_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    assert "@en" not in labels


@pytest.mark.unit
def test_pull_CLO_labels_skips_non_clo_prefix(clograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    clograph.pull_CLO_labels_and_synonyms(lf, sf)
    assert "Something else" not in Path(lf).read_text()


# ---------------------------------------------------------------------------
# pull_CLO_ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_CLO_ids_writes_descendants(clograph, tmp_path):
    out = str(tmp_path / "ids.tsv")
    roots = [("CLO:0000001", CELL_LINE)]
    clograph.pull_CLO_ids(roots, out)
    lines = Path(out).read_text().splitlines()
    curies = [line.split("\t")[0] for line in lines]
    assert f"{CLO}:0000001" in curies
    assert f"{CLO}:0000002" in curies


# ---------------------------------------------------------------------------
# get_exacts  (uses full IRI in angle brackets because CLO prefix is not
# declared in the get_exacts SPARQL query)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_exacts_skos_exactmatch(clograph):
    iri = f"<{_CLO_NS}0000001>"
    out = io.StringIO()
    clograph.get_exacts(iri, out)
    content = out.getvalue()
    assert "skos:exactMatch\tMONDO:0001234" in content


@pytest.mark.unit
def test_get_exacts_filters_orphanet(clograph):
    iri = f"<{_CLO_NS}0000001>"
    out = io.StringIO()
    clograph.get_exacts(iri, out)
    content = out.getvalue()
    for line in content.splitlines():
        assert "orphanet" not in line.lower(), f"Unexpected Orphanet line: {line}"


# ---------------------------------------------------------------------------
# get_xrefs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_xrefs_writes_valid_curie(clograph):
    iri = f"<{_CLO_NS}0000001>"
    out = io.StringIO()
    clograph.get_xrefs(iri, out)
    content = out.getvalue()
    assert "oboInOwl:hasDbXref\tMESH:D001234" in content


@pytest.mark.unit
def test_get_xrefs_skips_non_curie(clograph):
    iri = f"<{_CLO_NS}0000001>"
    out = io.StringIO()
    clograph.get_xrefs(iri, out)
    content = out.getvalue()
    assert "not-a-curie" not in content
