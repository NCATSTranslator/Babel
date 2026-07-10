"""Unit tests for src.createcompendia.chemicals.

Currently focused on write_unichem_concords()'s handling of UniChem compound IDs
that already embed their source prefix (e.g. the CHEBI source stores
"CHEBI:12345" rather than a bare "12345"), which previously produced invalid
"CHEBI:CHEBI:12345" CURIEs across the chemical compendia.
"""

import gzip

import pytest

from src.categories import COMPLEX_MOLECULAR_MIXTURE, FOOD, SMALL_MOLECULE
from src.createcompendia.chemicals import create_typed_sets, write_unichem_concords
from src.datahandlers.unichem import UNICHEM_REFERENCE_TSV_HEADER, UNICHEM_STRUCT_TSV_HEADER
from src.datahandlers.unichem import data_sources as unichem_data_sources
from src.prefixes import CHEBI

# Derive CHEBI's UniChem source ID from the authoritative dict rather than hardcoding it.
CHEBI_SRC_ID = next(k for k, v in unichem_data_sources.items() if v == CHEBI)


def _bare_rows_for_other_sources():
    """One bare-ID row per non-CHEBI source.

    write_unichem_concords() raises if any configured source produces no entries,
    so a focused test still has to feed every source at least one row.
    """
    return [("1", src_id, "100") for src_id in unichem_data_sources if src_id != CHEBI_SRC_ID]


def _write_struct(path):
    """Write a minimal gzipped UniChem structure file with one UCI→InChIKey row."""
    with gzip.open(path, "wt") as out:
        out.write(UNICHEM_STRUCT_TSV_HEADER)
        out.write("1\tInChI=1S/H2O/h1H2\tXLYOFNOQVPJJNP-UHFFFAOYSA-N\n")


def _write_ref(path, rows):
    """Write a UniChem reference file; rows are (uci, src_id, compound_id) tuples (assignment is always '1')."""
    with open(path, "w") as out:
        out.write(UNICHEM_REFERENCE_TSV_HEADER)
        for uci, src_id, compound_id in rows:
            out.write(f"{uci}\t{src_id}\t{compound_id}\t1\n")


@pytest.mark.unit
def test_write_unichem_concords_strips_embedded_chebi_prefix(tmp_path):
    """A CHEBI compound ID stored as 'CHEBI:12345' must yield CHEBI:12345, not CHEBI:CHEBI:12345."""
    struct = tmp_path / "structure.tsv.gz"
    ref = tmp_path / "reference.tsv"
    _write_struct(struct)
    _write_ref(ref, [("1", CHEBI_SRC_ID, "CHEBI:12345"), *_bare_rows_for_other_sources()])

    write_unichem_concords(str(struct), str(ref), str(tmp_path))

    content = (tmp_path / f"UNICHEM_{CHEBI}").read_text()
    assert "CHEBI:12345\t" in content
    assert "CHEBI:CHEBI" not in content


@pytest.mark.unit
def test_write_unichem_concords_raises_on_unexpected_embedded_prefix(tmp_path):
    """A CHEBI row carrying a foreign embedded prefix is a format change worth a loud failure."""
    struct = tmp_path / "structure.tsv.gz"
    ref = tmp_path / "reference.tsv"
    _write_struct(struct)
    _write_ref(ref, [("1", CHEBI_SRC_ID, "FOO:9")])

    with pytest.raises(ValueError, match="unexpected embedded prefix"):
        write_unichem_concords(str(struct), str(ref), str(tmp_path))


@pytest.mark.unit
def test_write_unichem_concords_raises_when_source_produces_no_entries(tmp_path):
    """Any configured source that contributes zero rows should raise RuntimeError."""
    struct = tmp_path / "structure.tsv.gz"
    ref = tmp_path / "reference.tsv"
    _write_struct(struct)
    # Feed rows for every source except CHEBI — CHEBI should trigger the empty-source guard.
    rows = [("1", src_id, "100") for src_id in unichem_data_sources if src_id != CHEBI_SRC_ID]
    _write_ref(ref, rows)

    with pytest.raises(RuntimeError, match="no entries for the following sources"):
        write_unichem_concords(str(struct), str(ref), str(tmp_path))


# ----
# ALLERGENIC-EXTRACT RETYPE (issue #828)
# ----


@pytest.mark.unit
def test_create_typed_sets_forces_food_clique():
    """A clique containing a DRUGBANK CURIE forced to Food should be typed biolink:Food regardless of
    its other members' types, and keep every member (incl. RXCUI)."""
    trout = frozenset({"DRUGBANK:DB10626", "UMLS:C2725895", "RXCUI:882482"})
    # A member is typed ChemicalEntity, which would otherwise win the vote — the forced type must override.
    types = {"UMLS:C2725895": "biolink:ChemicalEntity"}

    typed = create_typed_sets({trout}, types, forced_types={"DRUGBANK:DB10626": FOOD})

    assert trout in typed[FOOD]
    assert all(trout not in sets for t, sets in typed.items() if t != FOOD)


@pytest.mark.unit
def test_create_typed_sets_forces_non_food_allergen_to_mixture():
    """A DRUGBANK allergen extract forced to ComplexMolecularMixture lands there, not in Food."""
    pollen = frozenset({"DRUGBANK:DB10351", "UMLS:C2684343"})

    typed = create_typed_sets({pollen}, {}, forced_types={"DRUGBANK:DB10351": COMPLEX_MOLECULAR_MIXTURE})

    assert pollen in typed[COMPLEX_MOLECULAR_MIXTURE]
    assert pollen not in typed[FOOD]


@pytest.mark.unit
def test_create_typed_sets_leaves_non_forced_clique_untouched():
    """A clique with no forced-type CURIE should keep its normal type (no forced_types leakage)."""
    normal = frozenset({"CHEBI:15377", "PUBCHEM.COMPOUND:962"})
    types = {"CHEBI:15377": SMALL_MOLECULE, "PUBCHEM.COMPOUND:962": SMALL_MOLECULE}

    typed = create_typed_sets({normal}, types, forced_types={"DRUGBANK:DB10626": FOOD})

    assert normal in typed[SMALL_MOLECULE]
    assert normal not in typed[FOOD]
