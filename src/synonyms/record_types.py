"""
The Biolink types a synonym record lists. This is the one place that decides them: write_compendium() calls
synonym_record_types() for every record it writes, and conflate_synonyms() only takes the union of records that already
went through it. Name Resolver filters searches on this list (`biolink_type=...`), and the SapBERT export takes its
first entry as the record's type.

The compendia and NodeNorm don't use this list: NodeNorm computes a clique's ancestors itself, from the clique's own
type. What every output should do with the top-level classes is #1178.
"""

from src.categories import ONTOLOGY_CLASS

BIOLINK_PREFIX = "biolink:"

# Biolink classes that a synonym record leaves out of its `types` when they are only an *ancestor* of the clique's
# type. OntologyClass is a mixin that most Biolink classes inherit (Protein is an exception), so it says nothing about
# what an entity is: a femur is a NamedThing, but only philosophically an OntologyClass. A Name Resolver search
# filtered on OntologyClass therefore matches only cliques typed OntologyClass themselves, of which 2026jul22 had none;
# docs/synonyms/ontology-class/README.md counts the records this changes.
#
# NamedThing and Entity stay until #1178 decides them, along with other top-level mixins such as PhysicalEssence. To
# leave out another class, add it here rather than filtering in a consumer, so that every synonym file agrees.
ANCESTORS_LEFT_OUT_OF_SYNONYM_TYPES = frozenset({ONTOLOGY_CLASS})


def synonym_record_types(clique_type, ancestors):
    """
    Return the `types` of a clique's synonym record: the clique's type and its ancestors, without the `biolink:` prefix
    and without the ancestors in ANCESTORS_LEFT_OUT_OF_SYNONYM_TYPES.

    The clique's own type always comes first and is never left out, even if it is in that set: it is the one type that
    says what the clique is, and consumers such as the SapBERT export read `types[0]` as the record's type. So the list
    is never empty.

    :param clique_type: The clique's Biolink type, as a `biolink:`-prefixed CURIE (e.g. `biolink:AnatomicalEntity`).
    :param ancestors: The clique type's ancestors, as `NodeFactory.get_ancestors()` returns them: `biolink:`-prefixed,
        in the Biolink Model Toolkit's order, which starts with the type itself.
    :return: The types to write, e.g. `["AnatomicalEntity", "PhysicalEssence", "OrganismalEntity", ...]`.
    """
    kept = [clique_type] + [
        ancestor
        for ancestor in ancestors
        if ancestor != clique_type and ancestor not in ANCESTORS_LEFT_OUT_OF_SYNONYM_TYPES
    ]
    return [typ.removeprefix(BIOLINK_PREFIX) for typ in kept]
