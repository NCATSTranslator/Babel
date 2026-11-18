"""Unit tests for src/datahandlers/rhea.py (Rhea)."""

from pathlib import Path
from unittest.mock import patch

import pyoxigraph
import pytest

from src.datahandlers.rhea import Rhea, make_concord, make_labels
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


# ENTRY POINTS -- the caller-supplied rhea.rdf path must actually be the file we load.


@pytest.mark.unit
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda infile, tmp: make_labels(infile, str(tmp / "labels.tsv")), id="make_labels"),
        pytest.param(
            lambda infile, tmp: make_concord(infile, str(tmp / "concs.tsv"), str(tmp / "meta.yaml")),
            id="make_concord",
        ),
    ],
)
def test_entry_points_load_the_infile_they_are_given(call, tmp_path):
    """Both entry points should open the path passed to them, not one re-derived from the download
    directory. Rhea used to call make_local_name("rhea.rdf", subpath="RHEA") itself, so the
    Snakemake rules' declared input was ignored and the filename lived in two places -- the same gap
    ECgraph had. Pointing them at a missing path proves which one is opened: the error must name our
    path.
    """
    missing = tmp_path / "not-the-download-dir" / "rhea.rdf"

    with pytest.raises(FileNotFoundError) as excinfo:
        call(str(missing), tmp_path)

    assert str(missing) in str(excinfo.value)
