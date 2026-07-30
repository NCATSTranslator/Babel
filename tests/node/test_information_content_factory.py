"""Unit tests for InformationContentFactory and the icRDF.tsv loader behind it.

The loader is cached per path because `write_compendium` constructs an InformationContentFactory on
every call, and the chemical build calls `write_compendium` once per entry in
`config.yaml: chemical_outputs`. icRDF.tsv is 212 MB and ~3.9 million lines, each needing a
`curies.Converter.compress()` call, so an uncached load did that work eight times in one rule for a
byte-identical result.

`_load_information_content` normally reaches the network twice (the Biolink prefix map and the
UberGraph reverse prefix map), so these tests stub `get_biolink_prefix_map` with a tiny converter
built from the same `curies` API the real one uses.
"""

import curies
import pytest

import src.node as node
from src.node import InformationContentFactory, _load_information_content

# Two rows copied verbatim from babel_downloads/icRDF.tsv, which is `<URL>\t<information content>`.
ICRDF_ROWS = [
    ("http://purl.obolibrary.org/obo/CHEBI_15377", "78.6"),
    ("http://purl.obolibrary.org/obo/CHEBI_17234", "83.2"),
]


@pytest.fixture(autouse=True)
def clear_loader_cache():
    """Each test gets a cold cache, so one test's load can't satisfy another's."""
    _load_information_content.cache_clear()
    yield
    _load_information_content.cache_clear()


@pytest.fixture
def stub_prefix_maps(monkeypatch):
    """Replace the two network-backed prefix maps with a local converter covering the test rows."""
    converter = curies.Converter.from_prefix_map({"CHEBI": "http://purl.obolibrary.org/obo/CHEBI_"})
    monkeypatch.setattr(node, "get_biolink_prefix_map", lambda: converter)
    monkeypatch.setattr(node, "get_config", lambda: {"ubergraph_iri_stem_to_prefix_map": {}})
    return converter


def write_icrdf(path, rows=ICRDF_ROWS):
    path.write_text("".join(f"{url}\t{ic}\n" for url, ic in rows))
    return path


# LOADING


@pytest.mark.unit
def test_urls_are_compressed_to_curies(tmp_path, stub_prefix_maps):
    """icRDF.tsv holds URLs, but the rest of the pipeline speaks CURIEs, so the loader compresses."""
    ic = _load_information_content(str(write_icrdf(tmp_path / "icRDF.tsv")))
    assert ic == {"CHEBI:15377": 78.6, "CHEBI:17234": 83.2}


@pytest.mark.unit
def test_get_ic_returns_the_minimum_across_a_cliques_identifiers(tmp_path, stub_prefix_maps):
    """A clique's information content is the lowest of any member that has one."""
    factory = InformationContentFactory(str(write_icrdf(tmp_path / "icRDF.tsv")))
    node_record = {"identifiers": [{"identifier": "CHEBI:17234"}, {"identifier": "CHEBI:15377"}]}
    assert factory.get_ic(node_record) == 78.6


@pytest.mark.unit
def test_get_ic_returns_none_when_no_identifier_has_a_value(tmp_path, stub_prefix_maps):
    """A clique with no information content anywhere should yield None, not 0 or an error."""
    factory = InformationContentFactory(str(write_icrdf(tmp_path / "icRDF.tsv")))
    assert factory.get_ic({"identifiers": [{"identifier": "CHEBI:99999"}]}) is None


# CACHING


@pytest.mark.unit
def test_the_file_is_read_once_per_path(tmp_path, stub_prefix_maps, monkeypatch):
    """A second factory over the same path must reuse the parsed dict rather than re-reading.

    Asserted by counting real `open` calls on the icRDF path, not just by object identity, because
    identity alone would also pass if the loader returned a shared empty default.
    """
    path = write_icrdf(tmp_path / "icRDF.tsv")
    reads = []
    real_open = open

    def counting_open(file, *args, **kwargs):
        if str(file) == str(path):
            reads.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)

    first = InformationContentFactory(str(path))
    second = InformationContentFactory(str(path))

    assert reads == [str(path)]
    assert first.ic is second.ic


@pytest.mark.unit
def test_a_different_path_gets_its_own_load(tmp_path, stub_prefix_maps):
    """The cache is keyed on the path, so a tool pointed at another icRDF file is not served stale data."""
    one = write_icrdf(tmp_path / "one.tsv")
    two = write_icrdf(tmp_path / "two.tsv", rows=[("http://purl.obolibrary.org/obo/CHEBI_15377", "1.0")])

    assert _load_information_content(str(one)) == {"CHEBI:15377": 78.6, "CHEBI:17234": 83.2}
    assert _load_information_content(str(two)) == {"CHEBI:15377": 1.0}
