"""Unit tests for src/datahandlers/efo.py (EFOgraph)."""
import io
from pathlib import Path

import pyoxigraph
import pytest

from src.categories import DISEASE
from src.datahandlers.efo import EFOgraph
from src.prefixes import EFO
from tests.datahandlers.conftest import lit, nn, quad

_EFO_NS = "http://www.ebi.ac.uk/efo/EFO_"
_SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
_RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
_MONDO_NS = "http://purl.obolibrary.org/obo/MONDO_"
_MONDOH_NS = "http://purl.obolibrary.org/obo/mondo#"
_OBO_NS = "http://www.geneontology.org/formats/oboInOwl#"
_ORPHANET_IRI = "http://www.orpha.net/ORDO/Orphanet_123456"


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
    root = nn(f"{_EFO_NS}0000001")
    child = nn(f"{_EFO_NS}0001234")
    not_efo = nn("http://example.org/NOTANEFO")

    # Labels on root
    store.add(quad(root, nn(f"{_SKOS_NS}prefLabel"), lit("Liver disease")))
    store.add(quad(root, nn(f"{_SKOS_NS}altLabel"), lit("hepatic disease")))
    store.add(quad(root, nn(f"{_RDFS_NS}label"), lit("Liver disease", language="en")))

    # non-EFO_ entity — should be ignored
    store.add(quad(not_efo, nn(f"{_SKOS_NS}prefLabel"), lit("Something else")))

    # Hierarchy: child subClassOf root
    store.add(quad(child, nn(f"{_RDFS_NS}subClassOf"), root))
    store.add(quad(child, nn(f"{_SKOS_NS}prefLabel"), lit("Child term")))

    # Exact matches on root
    store.add(quad(root, nn(f"{_SKOS_NS}exactMatch"), nn(f"{_MONDO_NS}0001234")))
    store.add(quad(root, nn(f"{_SKOS_NS}exactMatch"), nn(_ORPHANET_IRI)))
    # mondo#exactMatch is normalised to skos:exactMatch in output
    store.add(quad(root, nn(f"{_MONDOH_NS}exactMatch"), nn(f"{_MONDO_NS}9999999")))

    # xrefs on root
    store.add(quad(root, nn(f"{_OBO_NS}hasDbXref"), lit("MESH:D001234")))
    store.add(quad(root, nn(f"{_OBO_NS}hasDbXref"), lit("not-a-curie")))

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
    labels = Path(lf).read_text()
    syns = Path(sf).read_text()
    assert f"{EFO}:0000001\tLiver disease" in labels
    assert f"{EFO}:0000001\tskos:prefLabel\tLiver disease" in syns


@pytest.mark.unit
def test_pull_EFO_labels_altlabel_in_syn_only(efograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    efograph.pull_EFO_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    syns = Path(sf).read_text()
    assert "hepatic disease" not in labels
    assert f"{EFO}:0000001\tskos:altLabel\thepatic disease" in syns


@pytest.mark.unit
def test_pull_EFO_labels_strips_language_tag(efograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    efograph.pull_EFO_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    assert "@en" not in labels
    assert f"{EFO}:0000001\tLiver disease" in labels


@pytest.mark.unit
def test_pull_EFO_labels_skips_non_efo_prefix(efograph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    efograph.pull_EFO_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    assert "Something else" not in labels


# ---------------------------------------------------------------------------
# pull_EFO_ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_EFO_ids_writes_descendants(efograph, tmp_path):
    out = str(tmp_path / "ids.tsv")
    roots = [("EFO:0000001", DISEASE)]
    efograph.pull_EFO_ids(roots, out)
    lines = Path(out).read_text().splitlines()
    curies = [line.split("\t")[0] for line in lines]
    assert f"{EFO}:0000001" in curies
    assert f"{EFO}:0001234" in curies


# ---------------------------------------------------------------------------
# get_exacts
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_exacts_skos_exactmatch(efograph):
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    content = out.getvalue()
    assert "EFO:0000001\tskos:exactMatch\tMONDO:0001234" in content


@pytest.mark.unit
def test_get_exacts_mondo_exactmatch(efograph):
    # mondo#exactMatch is normalised to skos:exactMatch by EFOgraph.get_exacts
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    content = out.getvalue()
    assert "EFO:0000001\tskos:exactMatch\tMONDO:9999999" in content


@pytest.mark.unit
def test_get_exacts_filters_orphanet(efograph):
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    content = out.getvalue()
    for line in content.splitlines():
        assert "orphanet" not in line.lower(), f"Unexpected Orphanet line: {line}"


# ---------------------------------------------------------------------------
# get_xrefs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_xrefs_writes_valid_curie(efograph):
    out = io.StringIO()
    efograph.get_xrefs("EFO:0000001", out)
    content = out.getvalue()
    assert "EFO:0000001\toboInOwl:hasDbXref\tMESH:D001234" in content


@pytest.mark.unit
def test_get_xrefs_skips_non_curie(efograph):
    out = io.StringIO()
    efograph.get_xrefs("EFO:0000001", out)
    content = out.getvalue()
    assert "not-a-curie" not in content
