"""Unit tests for src.createcompendia.chemicals.

Currently focused on write_unichem_concords()'s handling of UniChem compound IDs
that already embed their source prefix (e.g. the CHEBI source stores
"CHEBI:12345" rather than a bare "12345"), which previously produced invalid
"CHEBI:CHEBI:12345" CURIEs across the chemical compendia.
"""

import gzip

import pytest

from src.categories import CHEMICAL_ENTITY, COMPLEX_MOLECULAR_MIXTURE, FOOD, SMALL_MOLECULE
from src.createcompendia.chemicals import create_typed_sets, write_ncit_food_types, write_unichem_concords
from src.datahandlers.umls import MRCONSO_CODE_COLUMN, MRCONSO_CUI_COLUMN, MRCONSO_SAB_COLUMN
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
# FOOD-AND-EXTRACT RETYPE (issue #828)
# ----


@pytest.mark.unit
def test_create_typed_sets_food_evidence_beats_chemical_entity():
    """Food evidence on a clique whose members only vote ChemicalEntity should win: ChemicalEntity is
    exactly the uninformative type the retype exists to improve on. Every member (incl. RXCUI) is kept."""
    trout = frozenset({"DRUGBANK:DB10626", "UMLS:C2725895", "RXCUI:882482"})
    types = {"UMLS:C2725895": CHEMICAL_ENTITY}

    typed = create_typed_sets({trout}, types, food_types={"DRUGBANK:DB10626": FOOD})

    assert trout in typed[FOOD]
    assert all(trout not in sets for t, sets in typed.items() if t != FOOD)


@pytest.mark.unit
def test_create_typed_sets_food_evidence_loses_to_small_molecule():
    """Food evidence must NOT demote a defined molecule: NCIt classifies water as a food, but its clique
    votes SmallMolecule, which is more specific and wins (issue #935)."""
    water = frozenset({"UNII:059QF0KO0R", "CHEBI:15377", "PUBCHEM.COMPOUND:962"})
    types = {"CHEBI:15377": SMALL_MOLECULE, "PUBCHEM.COMPOUND:962": SMALL_MOLECULE}

    typed = create_typed_sets({water}, types, food_types={"UNII:059QF0KO0R": FOOD})

    assert water in typed[SMALL_MOLECULE]
    assert water not in typed[FOOD]


@pytest.mark.unit
def test_create_typed_sets_extract_evidence_becomes_complex_molecular_mixture():
    """A DrugBank extract carries ComplexMolecularMixture evidence and lands there, not in Food."""
    pollen = frozenset({"DRUGBANK:DB10351", "UMLS:C2684343"})

    typed = create_typed_sets({pollen}, {}, food_types={"DRUGBANK:DB10351": COMPLEX_MOLECULAR_MIXTURE})

    assert pollen in typed[COMPLEX_MOLECULAR_MIXTURE]
    assert pollen not in typed[FOOD]


@pytest.mark.unit
def test_create_typed_sets_extract_evidence_beats_food_evidence():
    """When a clique carries both kinds of evidence — DrugBank says extract, NCIt says the same concept is
    a food — the extract wins, because ComplexMolecularMixture outranks Food."""
    green_tea = frozenset({"DRUGBANK:DB13246", "UMLS:C0376263"})

    typed = create_typed_sets(
        {green_tea},
        {},
        food_types={"DRUGBANK:DB13246": COMPLEX_MOLECULAR_MIXTURE, "UMLS:C0376263": FOOD},
    )

    assert green_tea in typed[COMPLEX_MOLECULAR_MIXTURE]
    assert green_tea not in typed[FOOD]


@pytest.mark.unit
def test_create_typed_sets_leaves_clique_without_food_evidence_untouched():
    """A clique carrying no food/extract evidence keeps its normal type (no food_types leakage)."""
    normal = frozenset({"CHEBI:15377", "PUBCHEM.COMPOUND:962"})
    types = {"CHEBI:15377": SMALL_MOLECULE, "PUBCHEM.COMPOUND:962": SMALL_MOLECULE}

    typed = create_typed_sets({normal}, types, food_types={"DRUGBANK:DB10626": FOOD})

    assert normal in typed[SMALL_MOLECULE]
    assert normal not in typed[FOOD]


# ----
# write_ncit_food_types (issue #935)
# ----


def _write_mrconso(path, rows):
    """Write an MRCONSO.RRF fragment. Each row is (CUI, SAB, CODE); other columns are padded."""
    with open(path, "w") as out:
        for cui, sab, code in rows:
            fields = [""] * 18
            fields[MRCONSO_CUI_COLUMN] = cui
            fields[MRCONSO_SAB_COLUMN] = sab
            fields[MRCONSO_CODE_COLUMN] = code
            out.write("|".join(fields) + "\n")


def _write_unii_records_for_food(path, rows):
    """Write a UNII records TSV. Each row is a dict of column -> value; missing columns are blank."""
    header = ["UNII", "Display Name", "NCIT", "INCHIKEY"]
    with open(path, "w", encoding="windows-1252") as out:
        out.write("\t".join(header) + "\n")
        for row in rows:
            out.write("\t".join(row.get(col, "") for col in header) + "\n")


@pytest.mark.unit
def test_write_ncit_food_types_projects_ncit_foods_onto_umls_and_unii(tmp_path):
    """NCIt's food classification should reach the identifiers that are actually in chemical cliques: the
    CUI of every SAB=NCI food code, and every structureless UNII whose NCIt class is a food. A UNII with an
    InChI Key is skipped (a defined molecule is typed from its structure), and a never-food code (an
    imaging agent) contributes nothing even if it somehow appears under a food root."""
    mrconso = tmp_path / "MRCONSO.RRF"
    _write_mrconso(
        mrconso,
        [
            ("C0039299", "NCI", "C71920"),  # swordfish -> food code
            ("C0039299", "MSH", "D013530"),  # same CUI, non-NCI source: must not matter
            ("C0596170", "NCI", "C487"),  # ethiodized oil -> never-food code
            ("C0012345", "NCI", "C99999"),  # not a food code at all
        ],
    )
    records = tmp_path / "Latest_UNII_Records.txt"
    _write_unii_records_for_food(
        records,
        [
            {"UNII": "SWORDFISH1", "Display Name": "SWORDFISH", "NCIT": "C71920"},  # structureless food
            {"UNII": "059QF0KO0R", "Display Name": "WATER", "NCIT": "C71920", "INCHIKEY": "XLYOFNOQ-UHFF"},
            {"UNII": "NOTAFOOD01", "Display Name": "SOMETHING", "NCIT": "C99999"},  # not a food code
        ],
    )
    food_codes = tmp_path / "ncit_food_codes"
    food_codes.write_text("NCIT:C71920\nNCIT:C487\n")  # C487 is (implausibly) under a food root too...
    nonfood_codes = tmp_path / "ncit_nonfood_codes"
    nonfood_codes.write_text("NCIT:C487\n")  # ...but the never-food veto removes it
    outfile = tmp_path / "ncit_food_types"

    write_ncit_food_types(str(mrconso), str(records), str(food_codes), str(nonfood_codes), str(outfile))

    assert set(outfile.read_text().splitlines()) == {
        f"UMLS:C0039299\t{FOOD}",
        f"UNII:SWORDFISH1\t{FOOD}",
    }
