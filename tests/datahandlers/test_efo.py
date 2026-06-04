"""Unit tests for src/datahandlers/efo.py (EFOgraph)."""

import io

import pyoxigraph
import pytest

from src.categories import DISEASE
from src.datahandlers.efo import EFOgraph
from src.prefixes import EFO
from tests.datahandlers.conftest import RDFS_NS, SKOS_NS, lit, make_graph_from_store, nn, quad

_EFO_NS = "http://www.ebi.ac.uk/efo/EFO_"
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

    store.add(quad(root, nn(f"{SKOS_NS}prefLabel"), lit("Liver disease")))
    store.add(quad(root, nn(f"{SKOS_NS}altLabel"), lit("hepatic disease")))
    store.add(quad(root, nn(f"{RDFS_NS}label"), lit("Liver disease", language="en")))

    store.add(quad(not_efo, nn(f"{SKOS_NS}prefLabel"), lit("Something else")))

    store.add(quad(child, nn(f"{RDFS_NS}subClassOf"), root))
    store.add(quad(child, nn(f"{SKOS_NS}prefLabel"), lit("Child term")))

    store.add(quad(root, nn(f"{SKOS_NS}exactMatch"), nn(f"{_MONDO_NS}0001234")))
    store.add(quad(root, nn(f"{SKOS_NS}exactMatch"), nn(_ORPHANET_IRI)))
    # mondo#exactMatch is normalised to skos:exactMatch in output
    store.add(quad(root, nn(f"{_MONDOH_NS}exactMatch"), nn(f"{_MONDO_NS}9999999")))

    store.add(quad(root, nn(f"{_OBO_NS}hasDbXref"), lit("MESH:D001234")))
    store.add(quad(root, nn(f"{_OBO_NS}hasDbXref"), lit("not-a-curie")))

    return store


@pytest.fixture(scope="module")
def efograph():
    return make_graph_from_store(EFOgraph, _make_efo_store())


@pytest.fixture(scope="module")
def efo_output(efograph, tmp_path_factory):
    """Run label/synonym extraction once and return the file contents."""
    tmp = tmp_path_factory.mktemp("efo")
    lf = str(tmp / "labels.tsv")
    sf = str(tmp / "syns.tsv")
    efograph.pull_EFO_labels_and_synonyms(lf, sf)
    return {"labels": (tmp / "labels.tsv").read_text(), "syns": (tmp / "syns.tsv").read_text()}


# ---------------------------------------------------------------------------
# pull_EFO_labels_and_synonyms
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_EFO_labels_writes_preflabel(efo_output):
    assert f"{EFO}:0000001\tLiver disease" in efo_output["labels"]
    assert f"{EFO}:0000001\tskos:prefLabel\tLiver disease" in efo_output["syns"]


@pytest.mark.unit
def test_pull_EFO_labels_altlabel_in_syn_only(efo_output):
    assert "hepatic disease" not in efo_output["labels"]
    assert f"{EFO}:0000001\tskos:altLabel\thepatic disease" in efo_output["syns"]


@pytest.mark.unit
def test_pull_EFO_labels_strips_language_tag(efo_output):
    assert "@en" not in efo_output["labels"]
    assert f"{EFO}:0000001\tLiver disease" in efo_output["labels"]


@pytest.mark.unit
def test_pull_EFO_labels_skips_non_efo_prefix(efo_output):
    assert "Something else" not in efo_output["labels"]


# ---------------------------------------------------------------------------
# pull_EFO_ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_EFO_ids_writes_descendants(efograph, tmp_path):
    out = str(tmp_path / "ids.tsv")
    efograph.pull_EFO_ids([("EFO:0000001", DISEASE)], out)
    curies = [line.split("\t")[0] for line in (tmp_path / "ids.tsv").read_text().splitlines()]
    assert f"{EFO}:0000001" in curies
    assert f"{EFO}:0001234" in curies


# ---------------------------------------------------------------------------
# get_exacts
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_exacts_skos_exactmatch(efograph):
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    assert "EFO:0000001\tskos:exactMatch\tMONDO:0001234" in out.getvalue()


@pytest.mark.unit
def test_get_exacts_mondo_exactmatch(efograph):
    # mondo#exactMatch is normalised to skos:exactMatch by EFOgraph.get_exacts
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    assert "EFO:0000001\tskos:exactMatch\tMONDO:9999999" in out.getvalue()


@pytest.mark.unit
def test_get_exacts_filters_orphanet(efograph):
    out = io.StringIO()
    efograph.get_exacts("EFO:0000001", out)
    for line in out.getvalue().splitlines():
        assert "orphanet" not in line.lower(), f"Unexpected Orphanet line: {line}"


# ---------------------------------------------------------------------------
# get_xrefs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_xrefs_writes_valid_curie(efograph):
    out = io.StringIO()
    efograph.get_xrefs("EFO:0000001", out)
    assert "EFO:0000001\toboInOwl:hasDbXref\tMESH:D001234" in out.getvalue()


@pytest.mark.unit
def test_get_xrefs_skips_non_curie(efograph):
    out = io.StringIO()
    efograph.get_xrefs("EFO:0000001", out)
    assert "not-a-curie" not in out.getvalue()
