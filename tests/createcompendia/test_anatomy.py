"""Tests for src/createcompendia/anatomy.py."""

import pytest

from src.createcompendia.anatomy import (
    ANATOMY_OBO_IGNORE_LIST,
    ANATOMY_OBO_SOURCES,
    UBERON_OBO_IGNORE_LIST,
    build_wikidata_cell_relationships,
    get_anatomy_xref_prefix_map,
)
from src.prefixes import CL, EMAPA, FMA, GO, SNOMEDCT, UBERON, UMLS, WIKIDATA

# XREF PREFIX RENAMES AND IGNORE LISTS


@pytest.mark.unit
def test_uberon_sctid_xrefs_are_renamed_to_snomedct():
    """UBERON's SCTID xrefs should be renamed to SNOMEDCT, the spelling the UMLS concord uses.

    Without the rename no UBERON SNOMED xref can join a UMLS concept (docs/sources/UBERON/README.md).
    """
    assert get_anatomy_xref_prefix_map(UBERON) == {"SCTID": SNOMEDCT}


@pytest.mark.unit
def test_every_anatomy_obo_xref_source_has_a_rename_entry():
    """Every source whose xrefs build_anatomy_obo_relationships() writes should have an
    anatomy_xref_prefixes entry, so a missing one fails here rather than at build time."""
    for source in (UBERON, GO, EMAPA):
        assert source in ANATOMY_OBO_SOURCES
        assert isinstance(get_anatomy_xref_prefix_map(source), dict)


@pytest.mark.unit
def test_fma_xrefs_are_allowed_for_uberon_only():
    """UBERON's FMA xrefs should be kept while GO and EMAPA still ignore FMA, and the UBERON list
    should otherwise match the shared one."""
    assert FMA in ANATOMY_OBO_IGNORE_LIST
    assert FMA not in UBERON_OBO_IGNORE_LIST
    assert set(UBERON_OBO_IGNORE_LIST) == set(ANATOMY_OBO_IGNORE_LIST) - {FMA}


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
