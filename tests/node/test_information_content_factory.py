"""Unit tests for InformationContentFactory and the icRDF.tsv loader behind it.

`_load_information_content` normally reaches the network twice (the Biolink prefix map and the
UberGraph reverse prefix map), so these tests stub `get_biolink_prefix_map` with a tiny converter
built from the same `curies` API the real one uses. Under that stub, only CHEBI IRIs compress.
"""

import curies
import pytest

import src.node as node
from src.babel_utils import write_compendium
from src.node import InformationContentFactory, _load_information_content

# Real `<IRI>\t<normalizedInformationContent>` rows, exactly as UberGraph returned them on 2026-11-17
# for the query src/ubergraph.py:write_normalized_information_content() runs, restricted to these IRIs.
# Re-derive with `VALUES ?iri { ... } ?iri <http://reasoner.renci.org/vocab/normalizedInformationContent> ?nic`.
CHEBI_15377_ROW = ("http://purl.obolibrary.org/obo/CHEBI_15377", "47.751447038644294")
CHEBI_17234_ROW = ("http://purl.obolibrary.org/obo/CHEBI_17234", "52.491214926949837")
# A real row whose IRI neither the Biolink prefix map nor config.yaml: ubergraph_iri_stem_to_prefix_map
# compresses (checked against both on 2026-11-17) -- one of the ~250,000 the loader skips.
UNMAPPED_COB_ROW = ("http://purl.obolibrary.org/obo/COB_0000022", "1.4819108121952984")

ICRDF_ROWS = [CHEBI_15377_ROW, CHEBI_17234_ROW]


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
    assert ic == {"CHEBI:15377": 47.751447038644294, "CHEBI:17234": 52.491214926949837}


@pytest.mark.unit
def test_get_ic_returns_the_minimum_across_a_cliques_identifiers(tmp_path, stub_prefix_maps):
    """A clique's information content is the lowest of any member that has one."""
    factory = InformationContentFactory(str(write_icrdf(tmp_path / "icRDF.tsv")))
    node_record = {"identifiers": [{"identifier": "CHEBI:17234"}, {"identifier": "CHEBI:15377"}]}
    assert factory.get_ic(node_record) == 47.751447038644294


@pytest.mark.unit
def test_get_ic_returns_none_when_no_identifier_has_a_value(tmp_path, stub_prefix_maps):
    """A clique with no information content anywhere should yield None, not 0 or an error."""
    factory = InformationContentFactory(str(write_icrdf(tmp_path / "icRDF.tsv")))
    assert factory.get_ic({"identifiers": [{"identifier": "CHEBI:99999"}]}) is None


@pytest.mark.unit
def test_iris_with_no_curie_are_skipped_not_stored_under_none(tmp_path, stub_prefix_maps):
    """An IRI neither prefix map can compress must not land in the dict at all.

    It used to be stored as ``ic[None]``, every such row overwriting the last, behind an assertion
    that compared ``None`` against ``(prefix, count)`` tuples and so could never fail.
    """
    ic = _load_information_content(str(write_icrdf(tmp_path / "icRDF.tsv", rows=[UNMAPPED_COB_ROW, CHEBI_15377_ROW])))
    assert ic == {"CHEBI:15377": 47.751447038644294}


# SHARING ONE FACTORY


@pytest.mark.unit
def test_the_ic_mapping_is_read_only(tmp_path, stub_prefix_maps):
    """One factory is shared by every write_compendium call in a rule, so no caller may change its values."""
    factory = InformationContentFactory(str(write_icrdf(tmp_path / "icRDF.tsv")))
    with pytest.raises(TypeError):
        factory.ic["CHEBI:15377"] = 0.0


@pytest.mark.unit
def test_each_factory_reads_the_file_itself(tmp_path, stub_prefix_maps):
    """There is no process-wide cache: a re-downloaded file at the same path is read afresh.

    Sharing one load across calls is the caller's job (write_compendium's ``ic_factory``), so the
    dict is freed when the caller lets go of it rather than living as long as the process.
    """
    path = write_icrdf(tmp_path / "icRDF.tsv")
    first = InformationContentFactory(str(path))
    write_icrdf(path, rows=[(CHEBI_15377_ROW[0], "1.0")])
    second = InformationContentFactory(str(path))

    assert first.ic == {"CHEBI:15377": 47.751447038644294, "CHEBI:17234": 52.491214926949837}
    assert second.ic == {"CHEBI:15377": 1.0}


@pytest.mark.unit
def test_write_compendium_rejects_a_factory_loaded_from_another_file(tmp_path, stub_prefix_maps):
    """`icrdf_filename` stays the declared input, so a factory from a different file is a caller bug.

    Checked before write_compendium loads anything else, so this needs no network.
    """
    factory = InformationContentFactory(str(write_icrdf(tmp_path / "one.tsv")))

    with pytest.raises(ValueError, match="ic_factory loaded from"):
        write_compendium([], [], "Test.txt", None, icrdf_filename=str(tmp_path / "two.tsv"), ic_factory=factory)
