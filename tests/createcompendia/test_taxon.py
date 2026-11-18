"""Unit tests for src/createcompendia/taxon.py: how the taxon and chemical pipelines split the MeSH records that
carry an NCBI Taxon registry number (#1240), and the check in build_relationships() that keeps them split."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.categories import CHEMICAL_ENTITY, ORGANISM_TAXON
from src.createcompendia import chemicals, taxon

# Registry rows in rule get_mesh_registry's format. C000626778 "maize chlorotic mottle virus" is an SCR_Chemical
# record with RegistryNumber txid12138 in supp2026.gz; C000612320 "UR2 sarcoma virus" is an SCR_Organism record
# with txid354090 (also tests/data/mesh/supp2026_sample.xml); D000068877 "Imatinib Mesylate" has UNII 8A1O1M485B.
VIRUS_SCR_CHEMICAL = "MESH:C000626778"
VIRUS_SCR_ORGANISM = "MESH:C000612320"
IMATINIB = "MESH:D000068877"
REGISTRY = f"{VIRUS_SCR_ORGANISM}\ttxid354090\n{VIRUS_SCR_CHEMICAL}\ttxid12138\n{IMATINIB}\t8A1O1M485B\n"


def _fake_mesh():
    """A Mesh stand-in whose only records are the three above: imatinib under D02, the maize virus as an
    SCR_Chemical record and UR2 sarcoma virus as an SCR_Organism record, none mapped to an excluded tree."""
    fake = MagicMock()
    fake.get_terms_in_tree.side_effect = lambda tree: [IMATINIB] if tree == "D02" else []
    fake.get_terms_with_type.side_effect = lambda vocab: {
        "SCR_Chemical": [VIRUS_SCR_CHEMICAL],
        "SCR_Organism": [VIRUS_SCR_ORGANISM],
    }.get(vocab, [])
    fake.get_scr_terms_mapped_to_trees.return_value = set()
    return fake


def _ids(path):
    return dict(line.rstrip("\n").split("\t") for line in open(path))


# MESH IDS


@pytest.mark.unit
@patch("src.datahandlers.mesh.Mesh")
def test_virus_scr_with_ncbitaxon_goes_to_taxon_not_chemicals(mock_cls, tmp_path):
    """An SCR_Chemical record with an NCBI Taxon registry number should be in the taxon ids/MESH and not the
    chemical one, while an ordinary chemical stays in chemicals and SCR_Organism records stay in taxon."""
    mock_cls.return_value = _fake_mesh()
    registry = tmp_path / "registry.tsv"
    registry.write_text(REGISTRY)

    chemicals.write_mesh_ids(tmp_path / "chemicals", registry)
    taxon.write_mesh_ids(tmp_path / "taxon", registry)

    assert _ids(tmp_path / "chemicals") == {IMATINIB: CHEMICAL_ENTITY}
    assert _ids(tmp_path / "taxon") == {VIRUS_SCR_ORGANISM: ORGANISM_TAXON, VIRUS_SCR_CHEMICAL: ORGANISM_TAXON}


# NCBI_MESH CONCORD


def _build_relationships(tmp_path, other_pipelines_mesh_ids):
    registry = tmp_path / "registry.tsv"
    registry.write_text(REGISTRY)
    rdf_source = tmp_path / "rdf_source.json"
    rdf_source.write_text(json.dumps({"mesh_year": "2026", "url": "https://example/mesh2026.nt.gz", "sha1": "a" * 40}))
    xml_sources = tmp_path / "xml_sources.json"
    xml_sources.write_text(
        json.dumps([{"mesh_year": "2026", "url": "https://example/supp2026.gz", "sha1": "b" * 40, "modified": None}])
    )
    outfile = tmp_path / "NCBI_MESH"
    taxon.build_relationships(
        outfile,
        tmp_path / "unused_taxon_ids",
        tmp_path / "metadata-NCBI_MESH.yaml",
        mesh_registry=registry,
        mesh_rdf_source=rdf_source,
        mesh_xml_sources=xml_sources,
        other_pipelines_mesh_ids=other_pipelines_mesh_ids,
    )
    return outfile.read_text().splitlines()


@pytest.mark.unit
def test_build_relationships_writes_every_txid(tmp_path):
    """With no other pipeline claiming a txid record, every one should get its MeSH-NCBITaxon xref."""
    chemical_ids = tmp_path / "chemicals_ids"
    chemical_ids.write_text(f"{IMATINIB}\t{CHEMICAL_ENTITY}\n")
    assert _build_relationships(tmp_path, {"chemicals": chemical_ids}) == [
        f"{VIRUS_SCR_ORGANISM}\txref\tNCBITaxon:354090",
        f"{VIRUS_SCR_CHEMICAL}\txref\tNCBITaxon:12138",
    ]


@pytest.mark.unit
def test_build_relationships_raises_when_another_pipeline_claims_a_txid_record(tmp_path):
    """A txid record in another pipeline's ids/MESH would end up in two compendia, so building the concord
    should fail, naming the pipeline and the record."""
    chemical_ids = tmp_path / "chemicals_ids"
    chemical_ids.write_text(f"{IMATINIB}\t{CHEMICAL_ENTITY}\n{VIRUS_SCR_CHEMICAL}\t{CHEMICAL_ENTITY}\n")
    with pytest.raises(ValueError, match=f"chemicals \\(1\\): {VIRUS_SCR_CHEMICAL}"):
        _build_relationships(tmp_path, {"chemicals": chemical_ids})
