"""Unit tests for EMAPA ID typing and concord generation in ``src.createcompendia.anatomy``.

Both tests run offline (``unit``) by monkeypatching the UberGraph-facing calls.
"""

import pytest

import src.createcompendia.anatomy as anatomy
from src.prefixes import EMAPA
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


# --- Per-CURIE biolink typing ---


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


# --- Concord generation ---


@pytest.mark.unit
def test_build_emapa_obo_relationships_walks_part_of_with_ignore_list(monkeypatch):
    """build_emapa_obo_relationships() should walk part_of, not the default subClassOf.

    EMAPA is a partonomy, so a subClassOf walk finds only two terms. It must also apply
    ANATOMY_OBO_IGNORE_LIST, so the concord never picks up PMIDs, bare URLs or CL/GO
    xrefs. Both the real build and the EMAPA pipeline test fixture route through this
    function, so pinning its call keeps them from drifting apart.
    """
    captured = {}

    def _fake_build_sets(iri, concordfiles, set_type, **kwargs):
        captured["iri"] = iri
        captured["concordfiles"] = concordfiles
        captured["set_type"] = set_type
        captured.update(kwargs)

    monkeypatch.setattr(anatomy, "build_sets", _fake_build_sets)
    sentinel = object()
    anatomy.build_emapa_obo_relationships({EMAPA: sentinel})

    assert captured["iri"] == "EMAPA:0"
    assert captured["set_type"] == "xref"
    assert captured["hierarchy_predicate"] == HIERARCHY_PART_OF
    assert captured["ignore_list"] == anatomy.ANATOMY_OBO_IGNORE_LIST
    assert captured["concordfiles"] == {EMAPA: sentinel}


@pytest.mark.unit
def test_anatomy_obo_ignore_list_entries_are_upper_case():
    """build_sets() matches ignore_list against Text.get_prefix_or_none(), which upper-cases.

    A lower-case entry would silently never match and the prefix it was meant to block
    would be written to the concord, so build_sets() rejects one outright.
    """
    assert all(prefix == prefix.upper() for prefix in anatomy.ANATOMY_OBO_IGNORE_LIST)
