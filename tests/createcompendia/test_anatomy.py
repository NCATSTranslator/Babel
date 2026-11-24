"""Tests for src/createcompendia/anatomy.py."""

import pytest

from src.categories import ANATOMICAL_ENTITY, GROSS_ANATOMICAL_STRUCTURE
from src.createcompendia.anatomy import (
    build_wikidata_cell_relationships,
    classify_anatomy_clique,
    joins_animal_anatomy_to_plant_structure,
    match_plant_part_names,
    normalize_plant_part_name,
    read_plant_structure_ids,
)
from src.prefixes import CL, UMLS, WIKIDATA

# WIKIDATA CELL RELATIONSHIPS


@pytest.mark.network
def test_build_wikidata_cell_relationships(tmp_path):
    """The Wikidata CL/UMLS SPARQL endpoint should still answer and yield usable concord rows."""
    build_wikidata_cell_relationships(str(tmp_path), str(tmp_path / "wikidata.yaml"))

    lines = (tmp_path / WIKIDATA).read_text().splitlines()
    assert len(lines) > 100, "Expected thousands of unique UMLS/CL pairs, got a near-empty concord"
    for line in lines:
        umls_curie, relation, cl_curie = line.split("\t")
        assert umls_curie.startswith(f"{UMLS}:")
        assert relation == "eq"
        assert cl_curie.startswith(f"{CL}:")


# PLANT PART NAME MATCHING


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Plant Leaves", "leaf"),  # MESH:D018515
        ("leaf", "leaf"),  # PO:0025034
        ("Root Nodules, Plant", "root nodule"),  # MESH:D053204
        ("Plant, Whole", "whole"),  # NCIT:C79659
        ("whole plant", "whole"),  # PO:0000003
        ("Plant Stomata", "stoma"),  # MESH:D054046
        ("Plant Epidermis", "epidermi"),  # MESH:D019441; over-trimmed, but the same on both sides
        ("plant epidermis", "epidermi"),  # PO:0005679
        ("Bud", "bud"),  # NCIT:C79622; three letters, so not singularized
    ],
)
def test_normalize_plant_part_name(name, expected):
    """normalize_plant_part_name() should send a MeSH or NCIt name and the PO name for the same structure
    to the same key."""
    assert normalize_plant_part_name(name) == expected


@pytest.mark.unit
def test_match_plant_part_names_pairs_equal_names_by_label_or_synonym():
    """A vocabulary term should pair with the PO term whose label or exact synonym has the same name."""
    po_names = {
        "PO:0025034": {"leaf"},
        "PO:0005848": {"secondary xylem", "wood", "portion of secondary xylem tissue"},
        "PO:0009005": {"root"},
    }
    vocabulary_names = {"MESH:D018515": "Plant Leaves", "MESH:D014934": "Wood", "MESH:D038821": "Mycorrhizae"}

    assert match_plant_part_names(po_names, vocabulary_names) == {
        "MESH:D018515": "PO:0025034",
        "MESH:D014934": "PO:0005848",
    }


@pytest.mark.unit
def test_match_plant_part_names_drops_ambiguous_matches_both_ways():
    """A name that fits two PO terms, and a PO term two vocabulary terms claim, should both go unmatched
    rather than have a winner picked. The CURIEs and names here are made up to force each case."""
    po_names = {"PO:1": {"blade"}, "PO:2": {"blade"}, "PO:3": {"stem"}}
    vocabulary_names = {"NCIT:A": "Blade", "NCIT:B": "Stem", "NCIT:C": "Stems"}

    assert match_plant_part_names(po_names, vocabulary_names) == {}


@pytest.mark.unit
def test_classify_anatomy_clique_trusts_po_over_a_majority():
    """A clique holding a PO term should take PO's type even when MeSH and UMLS outvote it. Otherwise the
    xylem clique would be typed biolink:AnatomicalEntity, which Biolink does not register PO for, and
    write_compendium() would drop the PO term."""
    clique = frozenset({"PO:0005352", "MESH:D052584", "UMLS:C1720877"})
    types = {
        "PO:0005352": GROSS_ANATOMICAL_STRUCTURE,
        "MESH:D052584": ANATOMICAL_ENTITY,
        "UMLS:C1720877": ANATOMICAL_ENTITY,
    }

    assert classify_anatomy_clique(clique, types) == GROSS_ANATOMICAL_STRUCTURE


# ANIMAL ANATOMY VS PLANT STRUCTURES


@pytest.mark.unit
@pytest.mark.parametrize(
    ("subject", "obj", "expected"),
    [
        ("UBERON:0010008", "MESH:D018548", True),  # "placental cotyledon" -> MeSH "Cotyledon" (seed leaf)
        ("UBERON:0010008", "UMLS:C0242769", True),  # the same, through the CUI that follows MESH:D018548
        ("MESH:D058506", "UBERON:0000312", True),  # either way round
        ("PO:0020030", "MESH:D018548", False),  # PO is the plant ontology
        ("GO:0090406", "MESH:D053205", False),  # "pollen tube": GO applies to plants
        ("UBERON:0010008", "NCIT:C34135", False),  # an animal term to a non-plant target
    ],
)
def test_joins_animal_anatomy_to_plant_structure(subject, obj, expected):
    """A concord pair between a UBERON or EMAPA term and a MeSH plant structure (or its CUI) should be
    flagged for skipping, whichever way round it is written, and nothing else should be."""
    plant_structure_ids = frozenset({"MESH:D018548", "UMLS:C0242769", "MESH:D058506", "MESH:D053205"})

    assert joins_animal_anatomy_to_plant_structure(subject, obj, plant_structure_ids) is expected


@pytest.mark.unit
def test_read_plant_structure_ids_adds_the_cuis_that_follow_a_descriptor(tmp_path):
    """read_plant_structure_ids() should return the listed descriptors plus every CUI mesh_ownership
    gives to one of them, and nothing for a CUI following some other descriptor. The ownership rows are
    copied from a local build's intermediate/umls/mesh_ownership.tsv."""
    plant_structures = tmp_path / "mesh_plant_structures.tsv"
    plant_structures.write_text("MESH:D018548\tCotyledon\n")
    ownership = tmp_path / "mesh_ownership.tsv"
    ownership.write_text(
        "UMLS:C0242769\tanatomy\tMESH:D018548\tbiolink:AnatomicalEntity\n"
        "MESH:C000612320\ttaxon\tMESH:C000612320\tbiolink:OrganismTaxon\n"
    )

    assert read_plant_structure_ids(str(plant_structures), str(ownership)) == {"MESH:D018548", "UMLS:C0242769"}
    assert read_plant_structure_ids(None, str(ownership)) == frozenset()
