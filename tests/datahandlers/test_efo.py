"""Unit tests for src/datahandlers/efo.py (EFOgraph)."""
import io

import pyoxigraph
import pytest

from src.datahandlers.efo import EFOgraph
from src.prefixes import EFO

_EFO_NS = "http://www.ebi.ac.uk/efo/EFO_"
_SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
_SKOSH_NS = "http://www.w3.org/2004/02/skos/core#"  # same, just alias
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


def _make_efo_store() -> pyoxigraph.Store:
    """In-memory Store covering all EFOgraph methods.

    EFO:0000001  — root entity; prefLabel + altLabel + lang-tagged rdfs:label
                   + SKOS exactMatch to MONDO:0001234
                   + SKOS exactMatch to Orphanet (should be filtered)
                   + hasDbXref "MESH:D001234" (valid CURIE string xref)
                   + hasDbXref "not-a-curie" (invalid, should be skipped)

    EFO:0001234  — subClassOf EFO:0000001
    EFO:NOTANEFO — non-EFO_ IRI; should be skipped by label/id methods
    """
    store = pyoxigraph.Store()
    rdfs_label = _nn(f"{_RDFS_NS}label")
    rdfs_sub = _nn(f"{_RDFS_NS}subClassOf")
    skos_pref = _nn(f"{_SKOS_NS}prefLabel")
    skos_alt = _nn(f"{_SKOS_NS}altLabel")
    skos_exact = _nn(f"{_SKOS_NS}exactMatch")
    mondoh_exact = _nn(f"{_MONDOH_NS}exactMatch")
    has_xref = _nn(f"{_OBO_NS}hasDbXref")

    root = _nn(f"{_EFO_NS}0000001")
    child = _nn(f"{_EFO_NS}0001234")
    not_efo = _nn("http://example.org/NOTANEFO")

    # Labels on root
    store.add(_quad(root, skos_pref, _lit("Liver disease")))
    store.add(_quad(root, skos_alt, _lit("hepatic disease")))
    store.add(_quad(root, rdfs_label, _lit("Liver disease", language="en")))

    # non-EFO_ entity — should be ignored
    store.add(_quad(not_efo, skos_pref, _lit("Something else")))

    # Hierarchy: child subClassOf root
    store.add(_quad(child, rdfs_sub, root))
    store.add(_quad(child, skos_pref, _lit("Child term")))

    # Exact matches on root
    store.add(_quad(root, skos_exact, _nn(f"{_MONDO_NS}0001234")))
    store.add(_quad(root, skos_exact, _nn(_ORPHANET_IRI)))
    store.add(_quad(root, mondoh_exact, _nn(f"{_MONDO_NS}9999999")))

    # xrefs on root
    store.add(_quad(root, has_xref, _lit("MESH:D001234")))
    store.add(_quad(root, has_xref, _lit("not-a-curie")))

    return store


def _make_efograph(store: pyoxigraph.Store) -> EFOgraph:
    obj = EFOgraph.__new__(EFOgraph)
    obj.m = store
    return obj


@pytest.fixture(scope="module")
def efograph():
    return _make_efograph(_make_efo_store())


# ---------------------------------------------------------------------------
# pull_EFO_labels_and_synonyms
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_EFO_labels_writes_preflabel(efograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    efograph.pull_EFO_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    syns = open(sf).read()
    assert f"{EFO}:0000001\tLiver disease" in labels
    assert f"{EFO}:0000001\tskos:prefLabel\tLiver disease" in syns


@pytest.mark.unit
def test_pull_EFO_labels_altlabel_in_syn_only(efograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    efograph.pull_EFO_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    syns = open(sf).read()
    assert "hepatic disease" not in labels
    assert f"{EFO}:0000001\tskos:altLabel\thepatic disease" in syns


@pytest.mark.unit
def test_pull_EFO_labels_strips_language_tag(efograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    efograph.pull_EFO_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    assert "@en" not in labels
    assert f"{EFO}:0000001\tLiver disease" in labels


@pytest.mark.unit
def test_pull_EFO_labels_skips_non_efo_prefix(efograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    efograph.pull_EFO_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    assert "Something else" not in labels


# ---------------------------------------------------------------------------
# pull_EFO_ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_EFO_ids_writes_descendants(efograph, tmp_path):
    out = str(tmp_path / "ids.tsv")
    from src.categories import DISEASE
    roots = [("EFO:0000001", DISEASE)]
    efograph.pull_EFO_ids(roots, out)
    lines = open(out).read().splitlines()
    curies = [l.split("\t")[0] for l in lines]
    assert f"{EFO}:0000001" in curies
    assert f"{EFO}:0001234" in curies


# ---------------------------------------------------------------------------
# get_exacts
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_exacts_skos_exactmatch(efograph, tmp_path):
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    content = out.getvalue()
    assert "EFO:0000001\tskos:exactMatch\tMONDO:0001234" in content


@pytest.mark.unit
def test_get_exacts_mondo_exactmatch(efograph, tmp_path):
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    content = out.getvalue()
    assert "EFO:0000001\tskos:exactMatch\tMONDO:9999999" in content


@pytest.mark.unit
def test_get_exacts_filters_orphanet(efograph, tmp_path):
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    content = out.getvalue()
    assert "Orphanet" not in content.lower() or "orphanet" not in content.lower()
    # Strictly: no Orphanet line should appear
    for line in content.splitlines():
        assert "orphanet" not in line.lower(), f"Unexpected Orphanet line: {line}"


# ---------------------------------------------------------------------------
# get_xrefs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_xrefs_writes_valid_curie(efograph, tmp_path):
    out = io.StringIO()
    efograph.get_xrefs("EFO:0000001", out)
    content = out.getvalue()
    assert "EFO:0000001\toboInOwl:hasDbXref\tMESH:D001234" in content


@pytest.mark.unit
def test_get_xrefs_skips_non_curie(efograph, tmp_path):
    out = io.StringIO()
    efograph.get_xrefs("EFO:0000001", out)
    content = out.getvalue()
    assert "not-a-curie" not in content
