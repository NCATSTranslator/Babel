"""Tests for src/createcompendia/anatomy.py."""

import pytest

from src.categories import ANATOMICAL_ENTITY, CELL, CELLULAR_COMPONENT, GROSS_ANATOMICAL_STRUCTURE
from src.createcompendia.anatomy import (
    ANATOMY_OBO_IGNORE_LIST,
    ANATOMY_OBO_SOURCES,
    UBERON_OBO_IGNORE_LIST,
    build_wikidata_cell_relationships,
    find_uberon_snomed_xrefs_to_review,
    get_anatomy_xref_prefix_map,
)
from src.prefixes import CL, EMAPA, FMA, GO, SNOMEDCT, UBERON, UMLS, WIKIDATA
from src.util import get_biolink_model_toolkit, get_config, get_extra_prefixes

# XREF PREFIX RENAMES AND IGNORE LISTS


@pytest.mark.unit
def test_uberon_sctid_xrefs_are_renamed_to_snomedct():
    """UBERON's SCTID xrefs should be renamed to SNOMEDCT, the spelling the UMLS concord uses.

    Without the rename no UBERON SNOMED xref can join a UMLS concept (docs/sources/UBERON/umls-joins/README.md).
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


# EXTRA PREFIXES

ANATOMY_EXTRA_PREFIXES = "anatomy_extra_prefixes_by_biolink_class"


@pytest.mark.unit
def test_fma_is_shipped_as_an_extra_prefix_for_gross_anatomical_structure_only():
    """FMA should be an extra prefix for GrossAnatomicalStructure and for no other anatomy class.

    Biolink registers FMA for AnatomicalEntity but not GrossAnatomicalStructure, so without the extra
    prefix an FMA CURIE in a clique that joins an UBERON gross anatomy term is dropped (#1134). The
    allowlist overrides Biolink, so pin it: update this test alongside the config, not instead of it."""
    assert get_config()[ANATOMY_EXTRA_PREFIXES] == {GROSS_ANATOMICAL_STRUCTURE: [FMA]}
    assert get_extra_prefixes(ANATOMY_EXTRA_PREFIXES, GROSS_ANATOMICAL_STRUCTURE) == [FMA]
    for biotype in (ANATOMICAL_ENTITY, CELL, CELLULAR_COMPONENT):
        assert get_extra_prefixes(ANATOMY_EXTRA_PREFIXES, biotype) == []


@pytest.mark.network
def test_fma_extra_prefix_is_still_needed():
    """The FMA extra prefix should be removed once Biolink registers FMA for GrossAnatomicalStructure.

    A stale entry keeps FMA from competing for the preferred identifier in its registered position, and
    nothing else would notice. When this fails, remove the entry from config.yaml:
    anatomy_extra_prefixes_by_biolink_class and close https://github.com/NCATSTranslator/Babel/issues/1134
    (biolink/biolink-model#1827).

    Only GrossAnatomicalStructure is checked: whether Biolink registers FMA for any other class is not
    what this entry depends on, so a change there must not tell the maintainer to remove it."""
    toolkit = get_biolink_model_toolkit(get_config()["biolink_version"])
    assert FMA not in toolkit.get_element(GROSS_ANATOMICAL_STRUCTURE).id_prefixes


# UBERON SNOMED XREFS TO REVIEW

# Rows copied verbatim from the anatomy UBERON and UMLS concords (UMLS 2026AA, UberGraph of 2026-11-18).
_UBERON_CONCORD = """\
UBERON:0000082\txref\tSNOMEDCT:181414000
UBERON:0003672\txref\tSNOMEDCT:245543004
UBERON:0011877\txref\tSNOMEDCT:368572007
UBERON:0011877\txref\tSNOMEDCT:368594004
"""
_UMLS_CONCORD = """\
UMLS:C1278978\teq\tSNOMEDCT:181414000
UMLS:C0011443\teq\tSNOMEDCT:245543004
UMLS:C0040426\teq\tSNOMEDCT:38199008
UMLS:C0040426\teq\tSNOMEDCT:245543004
UMLS:C1289035\teq\tSNOMEDCT:368572007
UMLS:C1289057\teq\tSNOMEDCT:368594004
"""


@pytest.fixture
def snomed_concords(tmp_path):
    """The UBERON and UMLS concord excerpts above, written to files."""
    uberon, umls = tmp_path / UBERON, tmp_path / UMLS
    uberon.write_text(_UBERON_CONCORD)
    umls.write_text(_UMLS_CONCORD)
    return uberon, umls


@pytest.mark.unit
def test_snomed_xrefs_into_lumped_or_several_umls_concepts_are_flagged(snomed_concords):
    """An xref whose UMLS concept holds other SNOMED codes, or whose UBERON term reaches several UMLS concepts,
    should be flagged; an xref to a concept holding only that code should not be.

    UMLS files "Structure of dentition" (SNOMEDCT:245543004) under both "Dentition" and "Tooth"
    (UMLS:C0040426, which also holds SNOMEDCT:38199008 "Tooth structure"), and UBERON:0011877 "margin of
    tongue" xrefs both the left and the right margin."""
    flagged = find_uberon_snomed_xrefs_to_review(*snomed_concords, bad_pairs=set())
    assert flagged == {
        ("UBERON:0003672", "SNOMEDCT:245543004"): {
            "UMLS concept holds other SNOMED codes",
            "UBERON term reaches several UMLS concepts",
        },
        ("UBERON:0011877", "SNOMEDCT:368572007"): {"UBERON term reaches several UMLS concepts"},
        ("UBERON:0011877", "SNOMEDCT:368594004"): {"UBERON term reaches several UMLS concepts"},
    }


@pytest.mark.unit
def test_bad_pairs_are_removed_before_flagging(snomed_concords):
    """A pair listed in anatomy_badxrefs.txt should neither be flagged nor make another xref look lumped.

    Dropping the lumped UMLS-side pair leaves "Structure of dentition" in one concept, and dropping one side
    of margin of tongue leaves it reaching one concept, so nothing is flagged."""
    bad_pairs = {
        frozenset(("UMLS:C0040426", "SNOMEDCT:245543004")),
        frozenset(("UBERON:0011877", "SNOMEDCT:368572007")),
    }
    assert find_uberon_snomed_xrefs_to_review(*snomed_concords, bad_pairs=bad_pairs) == {}


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
