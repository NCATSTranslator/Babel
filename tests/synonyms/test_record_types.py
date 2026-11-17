"""Unit tests for src/synonyms/record_types.py, which decides the Biolink types every synonym record lists.

The ancestor lists are copied verbatim from `NodeFactory.get_ancestors()` against Biolink Model 4.4.3 (the
`biolink_version` in config.yaml when these tests were written), so they have the toolkit's real order: the type
itself, then its ancestors, with OntologyClass in the middle rather than at the end.
"""

import pytest

from src.categories import ANATOMICAL_ENTITY, NAMED_THING, ONTOLOGY_CLASS
from src.synonyms.record_types import synonym_record_types

# NodeFactory.get_ancestors("biolink:AnatomicalEntity"), Biolink Model 4.4.3.
ANATOMICAL_ENTITY_ANCESTORS = [
    "biolink:AnatomicalEntity",
    "biolink:PhysicalEssence",
    "biolink:OntologyClass",
    "biolink:OrganismalEntity",
    "biolink:SubjectOfInvestigation",
    "biolink:BiologicalEntity",
    "biolink:ThingWithTaxon",
    "biolink:NamedThing",
    "biolink:Entity",
    "biolink:PhysicalEssenceOrOccurrent",
]

# NodeFactory.get_ancestors("biolink:OntologyClass"), Biolink Model 4.4.3.
ONTOLOGY_CLASS_ANCESTORS = ["biolink:OntologyClass"]

# NodeFactory.get_ancestors("biolink:NamedThing"), Biolink Model 4.4.3.
NAMED_THING_ANCESTORS = ["biolink:NamedThing", "biolink:Entity"]


# CHOOSING A SYNONYM RECORD'S TYPES


@pytest.mark.unit
def test_ontology_class_is_left_out_when_it_is_only_an_ancestor():
    """Should drop OntologyClass from an anatomy clique's types, keep every other ancestor in the toolkit's order, and
    strip the biolink: prefix."""
    assert synonym_record_types(ANATOMICAL_ENTITY, ANATOMICAL_ENTITY_ANCESTORS) == [
        "AnatomicalEntity",
        "PhysicalEssence",
        "OrganismalEntity",
        "SubjectOfInvestigation",
        "BiologicalEntity",
        "ThingWithTaxon",
        "NamedThing",
        "Entity",
        "PhysicalEssenceOrOccurrent",
    ]


@pytest.mark.unit
def test_a_clique_typed_ontology_class_keeps_it_as_its_only_type():
    """Should keep OntologyClass when it is the clique's own type, so the list is never empty and types[0] (which the
    SapBERT export reads) is still the clique's type."""
    assert synonym_record_types(ONTOLOGY_CLASS, ONTOLOGY_CLASS_ANCESTORS) == ["OntologyClass"]


@pytest.mark.unit
def test_named_thing_and_entity_are_kept():
    """Should keep NamedThing and Entity, which #1178 has yet to decide, including for a clique typed NamedThing."""
    assert synonym_record_types(NAMED_THING, NAMED_THING_ANCESTORS) == ["NamedThing", "Entity"]


@pytest.mark.unit
def test_the_clique_type_comes_first_even_if_the_ancestors_list_it_later():
    """Should put the clique's own type first and list it once, whatever order the ancestors come in, since consumers
    read types[0] as the record's type."""
    ancestors = ["biolink:PhysicalEssence", "biolink:AnatomicalEntity", "biolink:NamedThing"]
    assert synonym_record_types(ANATOMICAL_ENTITY, ancestors) == ["AnatomicalEntity", "PhysicalEssence", "NamedThing"]
