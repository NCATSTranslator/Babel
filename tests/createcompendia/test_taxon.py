"""Tests for building the OrganismTaxon concords (src/createcompendia/taxon.py)."""

import pytest

from src.createcompendia.taxon import build_taxon_umls_relationships
from tests.conftest import assert_concordance_file_valid

# MRCONSO.RRF rows copied verbatim from the UMLS 2026AA release.
MRCONSO_ROWS = [
    # C1110641 Armoracia rusticana: UMLS calls NCBI Taxonomy "NCBI", and its CODE is the bare taxon ID.
    "C1110641|ENG|P|L0514063|PF|S0592368|N|A0647575||3704||NCBI|SCN|3704|Armoracia rusticana|0|N||",
    # C0003062 Animals: only the MeSH main heading (MH) is used; the entry term (ET) is skipped.
    "C0003062|ENG|P|L0003043|PF|S0014166|N|A2782515||M0001219|D000818|MSH|MH|D000818|Animals|0|N||",
    "C0003062|ENG|P|L0003043|VO|S0014083|Y|A26622215||M0001219|D000818|MSH|ET|D000818|Animal|0|N||",
    "C0003062|ENG|S|L0161925|PF|S0226340|N|A2687514||33208||NCBI|SY|33208|Animalia|0|N||",
    # C1704307 Fly (organism): a SNOMED CT atom, which isn't a source we map taxa from.
    "C1704307|ENG|S|L0016237|PF|S0004196|Y|A2876298|17694013|10147004||SNOMEDCT_US|PT|10147004|Fly|9|N||",
]


# UMLS CONCORD


@pytest.mark.unit
def test_build_taxon_umls_relationships(tmp_path):
    """UMLS taxon CUIs should be mapped to both MeSH and NCBITaxon, and other sources should be ignored."""
    mrconso = tmp_path / "MRCONSO.RRF"
    mrconso.write_text("".join(row + "\n" for row in MRCONSO_ROWS))
    idfile = tmp_path / "ids"
    idfile.write_text("".join(f"UMLS:{cui}\tbiolink:OrganismTaxon\n" for cui in ["C1110641", "C0003062", "C1704307"]))
    outfile = tmp_path / "concord"

    build_taxon_umls_relationships(str(mrconso), str(idfile), str(outfile), str(tmp_path / "metadata.yaml"))

    assert {tuple(row) for row in assert_concordance_file_valid(str(outfile))} == {
        ("UMLS:C1110641", "eq", "NCBITaxon:3704"),
        ("UMLS:C0003062", "eq", "MESH:D000818"),
        ("UMLS:C0003062", "eq", "NCBITaxon:33208"),
    }


@pytest.mark.unit
def test_build_taxon_umls_relationships_skips_cuis_not_in_id_list(tmp_path):
    """A CUI with an NCBI atom should not be mapped if it isn't one of the taxon UMLS IDs."""
    mrconso = tmp_path / "MRCONSO.RRF"
    mrconso.write_text("".join(row + "\n" for row in MRCONSO_ROWS))
    idfile = tmp_path / "ids"
    idfile.write_text("UMLS:C0003062\tbiolink:OrganismTaxon\n")
    outfile = tmp_path / "concord"

    build_taxon_umls_relationships(str(mrconso), str(idfile), str(outfile), str(tmp_path / "metadata.yaml"))

    assert "UMLS:C1110641" not in outfile.read_text()
