"""Unit test for EMAPA per-CURIE biolink typing in ``write_emapa_ids``.

EMAPA terms at or below EMAPA:35949 "organ" or EMAPA:35868 "tissue" are typed as
biolink:GrossAnatomicalStructure; everything else defaults to biolink:AnatomicalEntity.
We monkeypatch ``UberGraph`` with a small fixed partonomy so the test is offline (``unit``)
and assert the typing, EMAPA-prefix filtering, and deterministic sorted output.
"""

import pytest

import src.createcompendia.anatomy as anatomy
from src.ubergraph import HIERARCHY_PART_OF

# Fixed part_of descendant closures keyed by root IRI. Mirrors UberGraph.get_subclasses_of,
# which returns the full transitive closure from the redundant graph.
_PART_OF_DESCENDANTS = {
    "EMAPA:0": ["EMAPA:35949", "EMAPA:35868", "EMAPA:100", "EMAPA:200", "EMAPA:300", "UBERON:9999"],
    "EMAPA:35949": ["EMAPA:100"],  # organ subtree
    "EMAPA:35868": ["EMAPA:200"],  # tissue subtree
}


class _FakeUberGraph:
    def get_subclasses_of(self, iri, hierarchy_predicate=None):
        if hierarchy_predicate == HIERARCHY_PART_OF:
            return [{"descendent": c} for c in _PART_OF_DESCENDANTS.get(iri, [])]
        # No is_a (subClassOf) links in this fixture.
        return []


@pytest.mark.unit
def test_write_emapa_ids_types_organ_and_tissue_as_gross(tmp_path, monkeypatch):
    monkeypatch.setattr(anatomy, "UberGraph", lambda *a, **k: _FakeUberGraph())
    outfile = tmp_path / "EMAPA"
    anatomy.write_emapa_ids(str(outfile))

    rows = [line.split("\t") for line in outfile.read_text().splitlines()]
    types = {curie: biolink for curie, biolink in rows}

    # Non-EMAPA descendants are filtered out.
    assert "UBERON:9999" not in types

    # Organ/tissue roots and their descendants are gross.
    for curie in ("EMAPA:35949", "EMAPA:35868", "EMAPA:100", "EMAPA:200"):
        assert types[curie] == "biolink:GrossAnatomicalStructure", curie

    # The root and unrelated terms default to AnatomicalEntity.
    assert types["EMAPA:0"] == "biolink:AnatomicalEntity"
    assert types["EMAPA:300"] == "biolink:AnatomicalEntity"

    # Output is sorted by CURIE for deterministic, clean diffs.
    curies = [curie for curie, _ in rows]
    assert curies == sorted(curies)
