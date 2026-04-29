"""Unit tests for src/datahandlers/ec.py (ECgraph)."""
import pyoxigraph
import pytest

from src.categories import MOLECULAR_ACTIVITY
from src.datahandlers.ec import ECgraph
from src.prefixes import EC

_EC_NS = "http://purl.uniprot.org/enzyme/"
_UC_NS = "http://purl.uniprot.org/core/"
_SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
_RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def _nn(iri: str) -> pyoxigraph.NamedNode:
    return pyoxigraph.NamedNode(iri)


def _lit(val: str) -> pyoxigraph.Literal:
    return pyoxigraph.Literal(val)


def _quad(s, p, o) -> pyoxigraph.Quad:
    return pyoxigraph.Quad(s, p, o, pyoxigraph.DefaultGraph())


def _make_ec_store() -> pyoxigraph.Store:
    """In-memory Store with two EC entries covering prefLabel, altLabel, and rdfs:label."""
    store = pyoxigraph.Store()
    rdf_type = _nn(f"{_RDF_NS}type")
    enzyme = _nn(f"{_UC_NS}Enzyme")
    pref_label = _nn(f"{_SKOS_NS}prefLabel")
    alt_label = _nn(f"{_SKOS_NS}altLabel")
    rdfs_label = _nn(f"{_RDFS_NS}label")
    ec1 = _nn(f"{_EC_NS}1.2.3.4")
    ec2 = _nn(f"{_EC_NS}5.6.7.8")

    store.add(_quad(ec1, rdf_type, enzyme))
    store.add(_quad(ec1, pref_label, _lit("Alcohol dehydrogenase")))
    store.add(_quad(ec1, alt_label, _lit("ADH")))
    store.add(_quad(ec2, rdf_type, enzyme))
    store.add(_quad(ec2, rdfs_label, _lit("Some enzyme")))
    return store


def _make_ecgraph(store: pyoxigraph.Store) -> ECgraph:
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
    lines = open(out).read().splitlines()
    assert f"{EC}:1.2.3.4\t{MOLECULAR_ACTIVITY}" in lines
    assert f"{EC}:5.6.7.8\t{MOLECULAR_ACTIVITY}" in lines


@pytest.mark.unit
def test_pull_EC_labels_preflabel_in_both_files(ecgraph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    ecgraph.pull_EC_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    syns = open(sf).read()
    # EC writes label = str(row["label"]) without stripping quotes, so output includes them.
    assert f'{EC}:1.2.3.4\t"Alcohol dehydrogenase"' in labels
    assert f'{EC}:1.2.3.4\tskos:prefLabel\t"Alcohol dehydrogenase"' in syns


@pytest.mark.unit
def test_pull_EC_labels_altlabel_in_syn_only(ecgraph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    ecgraph.pull_EC_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    syns = open(sf).read()
    assert "ADH" not in labels
    assert f'{EC}:1.2.3.4\tskos:altLabel\t"ADH"' in syns


@pytest.mark.unit
def test_pull_EC_labels_rdfs_label_in_both_files(ecgraph, tmp_path):
    lf = str(tmp_path / "labels.tsv")
    sf = str(tmp_path / "syns.tsv")
    ecgraph.pull_EC_labels_and_synonyms(lf, sf)
    labels = open(lf).read()
    syns = open(sf).read()
    assert f'{EC}:5.6.7.8\t"Some enzyme"' in labels
    assert f'{EC}:5.6.7.8\trdfs:label\t"Some enzyme"' in syns
