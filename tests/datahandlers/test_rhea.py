"""Unit tests for src/datahandlers/rhea.py (Rhea)."""
from unittest.mock import patch

import pyoxigraph
import pytest

from src.datahandlers.rhea import Rhea
from src.prefixes import EC, RHEA

_RH_NS = "http://rdf.rhea-db.org/"
_RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
_ENZ_NS = "http://purl.uniprot.org/enzyme/"


def _nn(iri: str) -> pyoxigraph.NamedNode:
    return pyoxigraph.NamedNode(iri)


def _lit(val: str) -> pyoxigraph.Literal:
    return pyoxigraph.Literal(val)


def _quad(s, p, o) -> pyoxigraph.Quad:
    return pyoxigraph.Quad(s, p, o, pyoxigraph.DefaultGraph())


def _make_rhea_store() -> pyoxigraph.Store:
    """In-memory Store with two Rhea reactions.

    Reaction R1: has label + accession.
    Reaction R2: has accession + ec link (for concordance test).
    """
    store = pyoxigraph.Store()
    rdfs_label = _nn(f"{_RDFS_NS}label")
    rh_acc = _nn(f"{_RH_NS}accession")
    rh_ec = _nn(f"{_RH_NS}ec")

    r1 = _nn(f"{_RH_NS}12345")
    r2 = _nn(f"{_RH_NS}67890")

    store.add(_quad(r1, rdfs_label, _lit("ATP hydrolysis")))
    store.add(_quad(r1, rh_acc, _lit("RHEA:12345")))
    store.add(_quad(r2, rh_acc, _lit("RHEA:67890")))
    store.add(_quad(r2, rh_ec, _nn(f"{_ENZ_NS}1.2.3.4")))
    return store


def _make_rhea(store: pyoxigraph.Store) -> Rhea:
    obj = Rhea.__new__(Rhea)
    obj.m = store
    obj.filename = "test_rhea.rdf"
    return obj


@pytest.fixture(scope="module")
def rhea():
    return _make_rhea(_make_rhea_store())


@pytest.mark.unit
def test_pull_rhea_labels_writes_label(rhea, tmp_path):
    out = str(tmp_path / "labels.tsv")
    rhea.pull_rhea_labels(out)
    lines = open(out).read().splitlines()
    assert f"{RHEA}:12345\tATP hydrolysis" in lines


@pytest.mark.unit
@patch("src.datahandlers.rhea.write_concord_metadata")
def test_pull_rhea_ec_concs_writes_concordance(mock_meta, rhea, tmp_path):
    out = str(tmp_path / "concs.tsv")
    meta = str(tmp_path / "meta.yaml")
    rhea.pull_rhea_ec_concs(out, meta)
    lines = open(out).read().splitlines()
    assert f"{RHEA}:67890\toio:equivalent\t{EC}:1.2.3.4" in lines
    mock_meta.assert_called_once()
