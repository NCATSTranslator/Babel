"""Unit tests for src/datahandlers/ec.py (ECgraph)."""
from pathlib import Path

import pytest

from src.categories import MOLECULAR_ACTIVITY
from src.datahandlers.ec import ECgraph
from src.prefixes import EC
from tests.datahandlers.conftest import lit, nn, quad

_EC_NS = "http://purl.uniprot.org/enzyme/"
_UC_NS = "http://purl.uniprot.org/core/"
_SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
_RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def _make_ec_store():
    """In-memory Store with two EC entries covering prefLabel, altLabel, and rdfs:label."""
    import pyoxigraph

    store = pyoxigraph.Store()
    store.add(quad(nn(f"{_EC_NS}1.2.3.4"), nn(f"{_RDF_NS}type"), nn(f"{_UC_NS}Enzyme")))
    store.add(quad(nn(f"{_EC_NS}1.2.3.4"), nn(f"{_SKOS_NS}prefLabel"), lit("Alcohol dehydrogenase")))
    store.add(quad(nn(f"{_EC_NS}1.2.3.4"), nn(f"{_SKOS_NS}altLabel"), lit("ADH")))
    store.add(quad(nn(f"{_EC_NS}5.6.7.8"), nn(f"{_RDF_NS}type"), nn(f"{_UC_NS}Enzyme")))
    store.add(quad(nn(f"{_EC_NS}5.6.7.8"), nn(f"{_RDFS_NS}label"), lit("Some enzyme")))
    return store


def _make_ecgraph(store) -> ECgraph:
    obj = ECgraph.__new__(ECgraph)
    obj.m = store
    return obj


@pytest.fixture(scope="module")
def ecgraph():
    return _make_ecgraph(_make_ec_store())


@pytest.mark.unit
def test_pull_EC_ids_writes_enzyme_ids(ecgraph, tmp_path):
    out = str(tmp_path / "ids.tsv")
    ecgraph.pull_EC_ids(out)
    lines = Path(out).read_text().splitlines()
    assert f"{EC}:1.2.3.4\t{MOLECULAR_ACTIVITY}" in lines
    assert f"{EC}:5.6.7.8\t{MOLECULAR_ACTIVITY}" in lines


@pytest.mark.unit
def test_pull_EC_labels_preflabel_in_both_files(ecgraph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    ecgraph.pull_EC_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    syns = Path(sf).read_text()
    assert f"{EC}:1.2.3.4\tAlcohol dehydrogenase" in labels
    assert f"{EC}:1.2.3.4\tskos:prefLabel\tAlcohol dehydrogenase" in syns


@pytest.mark.unit
def test_pull_EC_labels_altlabel_in_syn_only(ecgraph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    ecgraph.pull_EC_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    syns = Path(sf).read_text()
    assert "ADH" not in labels
    assert f"{EC}:1.2.3.4\tskos:altLabel\tADH" in syns


@pytest.mark.unit
def test_pull_EC_labels_rdfs_label_in_both_files(ecgraph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    ecgraph.pull_EC_labels_and_synonyms(lf, sf)
    labels = Path(lf).read_text()
    syns = Path(sf).read_text()
    assert f"{EC}:5.6.7.8\tSome enzyme" in labels
    assert f"{EC}:5.6.7.8\trdfs:label\tSome enzyme" in syns
