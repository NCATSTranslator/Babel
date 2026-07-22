"""Unit tests for src/datahandlers/ec.py (ECgraph)."""

import pyoxigraph
import pytest

from src.categories import MOLECULAR_ACTIVITY
from src.datahandlers.ec import ECgraph, make_ids, make_labels
from src.prefixes import EC
from tests.datahandlers.conftest import RDF_NS, RDFS_NS, SKOS_NS, lit, make_graph_from_store, nn, quad

_EC_NS = "http://purl.uniprot.org/enzyme/"
_UC_NS = "http://purl.uniprot.org/core/"


def _make_ec_store() -> pyoxigraph.Store:
    """In-memory Store with two EC entries covering prefLabel, altLabel, and rdfs:label."""
    store = pyoxigraph.Store()
    store.add(quad(nn(f"{_EC_NS}1.2.3.4"), nn(f"{RDF_NS}type"), nn(f"{_UC_NS}Enzyme")))
    store.add(quad(nn(f"{_EC_NS}1.2.3.4"), nn(f"{SKOS_NS}prefLabel"), lit("Alcohol dehydrogenase")))
    store.add(quad(nn(f"{_EC_NS}1.2.3.4"), nn(f"{SKOS_NS}altLabel"), lit("ADH")))
    store.add(quad(nn(f"{_EC_NS}5.6.7.8"), nn(f"{RDF_NS}type"), nn(f"{_UC_NS}Enzyme")))
    store.add(quad(nn(f"{_EC_NS}5.6.7.8"), nn(f"{RDFS_NS}label"), lit("Some enzyme")))
    return store


@pytest.fixture(scope="module")
def ecgraph():
    return make_graph_from_store(ECgraph, _make_ec_store())


@pytest.fixture(scope="module")
def ec_output(ecgraph, tmp_path_factory):
    """Run label/synonym extraction once and return the file contents."""
    tmp = tmp_path_factory.mktemp("ec")
    lf = str(tmp / "labels.tsv")
    sf = str(tmp / "syns.tsv")
    ecgraph.pull_EC_labels_and_synonyms(lf, sf)
    return {"labels": (tmp / "labels.tsv").read_text(), "syns": (tmp / "syns.tsv").read_text()}


@pytest.mark.unit
def test_pull_EC_ids_writes_enzyme_ids(ecgraph, tmp_path):
    out = str(tmp_path / "ids.tsv")
    ecgraph.pull_EC_ids(out)
    lines = (tmp_path / "ids.tsv").read_text().splitlines()
    assert f"{EC}:1.2.3.4\t{MOLECULAR_ACTIVITY}" in lines
    assert f"{EC}:5.6.7.8\t{MOLECULAR_ACTIVITY}" in lines


@pytest.mark.unit
def test_pull_EC_labels_preflabel_in_both_files(ec_output):
    assert f"{EC}:1.2.3.4\tAlcohol dehydrogenase" in ec_output["labels"]
    assert f"{EC}:1.2.3.4\tskos:prefLabel\tAlcohol dehydrogenase" in ec_output["syns"]


@pytest.mark.unit
def test_pull_EC_labels_altlabel_in_syn_only(ec_output):
    assert "ADH" not in ec_output["labels"]
    assert f"{EC}:1.2.3.4\tskos:altLabel\tADH" in ec_output["syns"]


@pytest.mark.unit
def test_pull_EC_labels_rdfs_label_in_both_files(ec_output):
    assert f"{EC}:5.6.7.8\tSome enzyme" in ec_output["labels"]
    assert f"{EC}:5.6.7.8\trdfs:label\tSome enzyme" in ec_output["syns"]


# ENTRY POINTS -- the caller-supplied enzyme.rdf path must actually be the file we load.


@pytest.mark.unit
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda infile, tmp: make_ids(infile, str(tmp / "ids.tsv")), id="make_ids"),
        pytest.param(
            lambda infile, tmp: make_labels(infile, str(tmp / "labels.tsv"), str(tmp / "syns.tsv")),
            id="make_labels",
        ),
    ],
)
def test_entry_points_load_the_infile_they_are_given(call, tmp_path):
    """Both entry points should open the path passed to them, not one re-derived from the download
    directory. ECgraph used to call make_local_name("enzyme.rdf", subpath="EC") itself, so the
    Snakemake rules' declared input was ignored and the filename lived in two places -- a rule could
    depend on one file and read another. Pointing them at a missing path proves which one is opened:
    the error must name our path.
    """
    missing = tmp_path / "not-the-download-dir" / "enzyme.rdf"

    with pytest.raises(FileNotFoundError) as excinfo:
        call(str(missing), tmp_path)

    assert str(missing) in str(excinfo.value)
