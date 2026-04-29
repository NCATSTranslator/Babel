"""Unit tests for src/datahandlers/clo.py (CLOgraph)."""
import io

import pyoxigraph
import pytest

from src.datahandlers.clo import CLOgraph
from src.prefixes import CLO

_CLO_NS = "http://purl.obolibrary.org/obo/CLO_"
_SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
_RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
_MONDO_NS = "http://purl.obolibrary.org/obo/MONDO_"
_MONDOH_NS = "http://purl.obolibrary.org/obo/mondo#"
_OBO_NS = "http://www.geneontology.org/formats/oboInOwl#"
_ORPHANET_IRI = "http://www.orpha.net/ORDO/Orphanet_123456"


def _nn(iri: str) -> pyoxigraph.NamedNode:
    return pyoxigraph.NamedNode(iri)


def _lit(val: str, language: str | None = None) -> pyoxigraph.Literal:
    if language:
        return pyoxigraph.Literal(val, language=language)
    return pyoxigraph.Literal(val)


def _quad(s, p, o) -> pyoxigraph.Quad:
    return pyoxigraph.Quad(s, p, o, pyoxigraph.DefaultGraph())


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
    rdfs_label = _nn(f"{_RDFS_NS}label")
    rdfs_sub = _nn(f"{_RDFS_NS}subClassOf")
    skos_pref = _nn(f"{_SKOS_NS}prefLabel")
    skos_alt = _nn(f"{_SKOS_NS}altLabel")
    skos_exact = _nn(f"{_SKOS_NS}exactMatch")
    mondoh_exact = _nn(f"{_MONDOH_NS}exactMatch")
    has_xref = _nn(f"{_OBO_NS}hasDbXref")

    root = _nn(f"{_CLO_NS}0000001")
    child = _nn(f"{_CLO_NS}0000002")
    not_clo = _nn("http://example.org/NOTACLO")

    # Labels on root
    store.add(_quad(root, skos_pref, _lit("HeLa cell")))
    store.add(_quad(root, skos_alt, _lit("HeLa")))
    store.add(_quad(root, rdfs_label, _lit("HeLa cell", language="en")))

    # non-CLO_ entity — should be ignored
    store.add(_quad(not_clo, skos_pref, _lit("Something else")))

    # Hierarchy: child subClassOf root
    store.add(_quad(child, rdfs_sub, root))
    store.add(_quad(child, skos_pref, _lit("Child cell line")))

    # Exact matches on root using full IRIs (CLO prefix not declared in get_exacts query)
    store.add(_quad(root, skos_exact, _nn(f"{_MONDO_NS}0001234")))
    store.add(_quad(root, skos_exact, _nn(_ORPHANET_IRI)))
    store.add(_quad(root, mondoh_exact, _nn(f"{_MONDO_NS}9999999")))

    # xrefs on root
    store.add(_quad(root, has_xref, _lit("MESH:D001234")))
    store.add(_quad(root, has_xref, _lit("not-a-curie")))

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
    labels = open(lf).read()
    syns = open(sf).read()
    assert f"{CLO}:0000001\tHeLa cell" in labels
    assert f"{CLO}:0000001\tskos:prefLabel\tHeLa cell" in syns


@pytest.mark.unit
def test_pull_CLO_labels_altlabel_in_syn_only(clograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    clograph.pull_CLO_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    syns = open(sf).read()
    # altLabel "HeLa" must not appear in label file
    label_lines = [l for l in labels.splitlines() if "HeLa" in l and "HeLa cell" not in l]
    assert not label_lines
    assert f"{CLO}:0000001\tskos:altLabel\tHeLa" in syns


@pytest.mark.unit
def test_pull_CLO_labels_strips_language_tag(clograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    clograph.pull_CLO_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    assert "@en" not in labels


@pytest.mark.unit
def test_pull_CLO_labels_skips_non_clo_prefix(clograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    clograph.pull_CLO_labels_and_synonyms(lf, sf)
    assert "Something else" not in open(lf).read()


# ---------------------------------------------------------------------------
# pull_CLO_ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_CLO_ids_writes_descendants(clograph, tmp_path):
    out = str(tmp_path / "ids.tsv")
    from src.categories import CELL_LINE
    roots = [("CLO:0000001", CELL_LINE)]
    clograph.pull_CLO_ids(roots, out)
    lines = open(out).read().splitlines()
    curies = [l.split("\t")[0] for l in lines]
    assert f"{CLO}:0000001" in curies
    assert f"{CLO}:0000002" in curies


# ---------------------------------------------------------------------------
# get_exacts  (uses full IRI in angle brackets because CLO prefix is not
# declared in the get_exacts SPARQL query)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_exacts_skos_exactmatch(clograph, tmp_path):
    iri = f"<{_CLO_NS}0000001>"
    out = io.StringIO()
    clograph.get_exacts(iri, out)
    content = out.getvalue()
    assert "skos:exactMatch\tMONDO:0001234" in content


@pytest.mark.unit
def test_get_exacts_filters_orphanet(clograph, tmp_path):
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
def test_get_xrefs_writes_valid_curie(clograph, tmp_path):
    iri = f"<{_CLO_NS}0000001>"
    out = io.StringIO()
    clograph.get_xrefs(iri, out)
    content = out.getvalue()
    assert "oboInOwl:hasDbXref\tMESH:D001234" in content


@pytest.mark.unit
def test_get_xrefs_skips_non_curie(clograph, tmp_path):
    iri = f"<{_CLO_NS}0000001>"
    out = io.StringIO()
    clograph.get_xrefs(iri, out)
    content = out.getvalue()
    assert "not-a-curie" not in content
