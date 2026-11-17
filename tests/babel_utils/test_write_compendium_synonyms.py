"""Tests that write_compendium() writes each synonym record's types through synonym_record_types().

The clique is UMLS:C0733999 "Scapular line" with FMA:14613, the same clique tests/synonyms/test_synonymconflation.py
copies from an anatomy build; the factories are the in-memory fakes from conftest.py.
"""

import json
from types import SimpleNamespace

import pytest

import src.babel_utils as babel_utils
from src.categories import ANATOMICAL_ENTITY
from tests.synonyms.test_record_types import ANATOMICAL_ENTITY_ANCESTORS

HAS_EXACT_SYNONYM = "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym"


# SYNONYM RECORD TYPES


@pytest.mark.unit
def test_synonym_record_types_leave_out_ontology_class(fake_write_compendium_env, monkeypatch):
    """Should write the anatomy clique's synonym record with its type first and every ancestor except OntologyClass,
    while the compendium line keeps the clique's type unchanged."""
    # The class write_compendium() will use: conftest.py is imported under more than one module name, so patching an
    # imported FakeNodeFactory could patch a different copy.
    monkeypatch.setattr(babel_utils.NodeFactory, "ancestors", {ANATOMICAL_ENTITY: ANATOMICAL_ENTITY_ANCESTORS})
    synonyms = SimpleNamespace(
        get_synonyms=lambda *args, **kwargs: [
            (HAS_EXACT_SYNONYM, "Scapular line"),
            (HAS_EXACT_SYNONYM, "Linea scapularis"),
        ],
        close=lambda: None,
    )
    monkeypatch.setattr(babel_utils, "SynonymFactory", lambda *args: synonyms)

    babel_utils.write_compendium(
        [],
        [{"UMLS:C0733999", "FMA:14613"}],
        "AnatomicalEntity.txt",
        ANATOMICAL_ENTITY,
        labels={"UMLS:C0733999": "Scapular line"},
        icrdf_filename="icRDF.tsv",
    )

    (record,) = [
        json.loads(line)
        for line in (fake_write_compendium_env / "synonyms" / "AnatomicalEntity.txt").read_text().splitlines()
    ]
    assert record["types"] == [
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
    (clique,) = [
        json.loads(line)
        for line in (fake_write_compendium_env / "compendia" / "AnatomicalEntity.txt").read_text().splitlines()
    ]
    assert clique["type"] == ANATOMICAL_ENTITY
