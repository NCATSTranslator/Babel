"""Unit tests for src/datahandlers/rhea.py (Rhea)."""
from pathlib import Path
from unittest.mock import patch

import pyoxigraph
import pytest

from src.datahandlers.rhea import Rhea
from src.prefixes import EC, RHEA
from tests.datahandlers.conftest import RDFS_NS, lit, make_graph_from_store, nn, quad

_RH_NS = "http://rdf.rhea-db.org/"
_ENZ_NS = "http://purl.uniprot.org/enzyme/"


def _make_rhea_store() -> pyoxigraph.Store:
    """In-memory Store with two Rhea reactions.

    Reaction R1: has label + accession.
    Reaction R2: has accession + ec link (for concordance test).
    """
    store = pyoxigraph.Store()
    r1 = nn(f"{_RH_NS}12345")
    r2 = nn(f"{_RH_NS}67890")

    store.add(quad(r1, nn(f"{RDFS_NS}label"), lit("ATP hydrolysis")))
    store.add(quad(r1, nn(f"{_RH_NS}accession"), lit("RHEA:12345")))
    store.add(quad(r2, nn(f"{_RH_NS}accession"), lit("RHEA:67890")))
    store.add(quad(r2, nn(f"{_RH_NS}ec"), nn(f"{_ENZ_NS}1.2.3.4")))
    return store


@pytest.fixture(scope="module")
def rhea():
    return make_graph_from_store(Rhea, _make_rhea_store(), filename="test_rhea.rdf")


@pytest.mark.unit
def test_pull_rhea_labels_writes_label(rhea, tmp_path):
    out = str(tmp_path / "labels.tsv")
    rhea.pull_rhea_labels(out)
    assert f"{RHEA}:12345\tATP hydrolysis" in Path(out).read_text().splitlines()


@pytest.mark.unit
@patch("src.datahandlers.rhea.write_concord_metadata")
def test_pull_rhea_ec_concs_writes_concordance(mock_meta, rhea, tmp_path):
    out = str(tmp_path / "concs.tsv")
    meta = str(tmp_path / "meta.yaml")
    rhea.pull_rhea_ec_concs(out, meta)
    assert f"{RHEA}:67890\toio:equivalent\t{EC}:1.2.3.4" in Path(out).read_text().splitlines()
    mock_meta.assert_called_once()
