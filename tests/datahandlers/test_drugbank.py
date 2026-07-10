"""Unit tests for the DrugBank allergenic-extract retype (issue #828).

Covers datahandlers.drugbank.extract_drugbank_allergenic_extract_types (which DRUGBANK ids become
biolink:Food vs biolink:ComplexMolecularMixture) and the UNII helpers it and write_unii_ids rely on
(read_unii_ncit, read_organism_uniis).
"""

import pytest

from src.categories import COMPLEX_MOLECULAR_MIXTURE, FOOD
from src.datahandlers.drugbank import classify_allergenic_extract, extract_drugbank_allergenic_extract_types
from src.datahandlers.unii import UNII_ORGANISM_COLUMNS, read_organism_uniis, read_unii_ncit

# Header for the CC-0 DrugBank vocabulary CSV, in the fixed column order Babel reads.
DRUGBANK_VOCAB_HEADER = "DrugBank ID,Accession Numbers,Common name,CAS,UNII,Synonyms,Standard InChI Key"

# UNII records are Windows-1252 TSV; only the columns Babel reads need to be present/positioned.
UNII_RECORDS_HEADER = ["UNII", "PT", "NCIT", "NCBI", "PLANTS", "GRIN", "MPNS"]


def _write_vocab(path, rows):
    """Write a DrugBank vocabulary CSV. Each row is the 7 fields in header order."""
    with open(path, "w") as out:
        out.write(DRUGBANK_VOCAB_HEADER + "\n")
        for row in rows:
            out.write(",".join(f'"{f}"' for f in row) + "\n")


def _write_unii_records(path, rows):
    """Write a UNII records TSV. Each row is a dict of column->value; missing columns are blank."""
    with open(path, "w", encoding="windows-1252") as out:
        out.write("\t".join(UNII_RECORDS_HEADER) + "\n")
        for row in rows:
            out.write("\t".join(row.get(col, "") for col in UNII_RECORDS_HEADER) + "\n")


# ----
# UNII record readers
# ----


@pytest.mark.unit
def test_read_unii_ncit_returns_ncit_curies(tmp_path):
    """read_unii_ncit maps each UNII with an NCIt code to its NCIt CURIE, skipping blank codes."""
    records = tmp_path / "Latest_UNII_Records.txt"
    _write_unii_records(
        records,
        [
            {"UNII": "7TI7U5PF2U", "NCIT": "C71910"},  # trout
            {"UNII": "NOCODE0000", "NCIT": ""},  # no NCIt code → skipped
        ],
    )
    assert read_unii_ncit(str(records)) == {"7TI7U5PF2U": "NCIT:C71910"}


@pytest.mark.unit
def test_read_organism_uniis_flags_organism_records(tmp_path):
    """A UNII with any of NCBI/PLANTS/GRIN/MPNS populated is an organism (write_unii_ids skips these)."""
    records = tmp_path / "Latest_UNII_Records.txt"
    _write_unii_records(
        records,
        [
            {"UNII": "7TI7U5PF2U", "NCBI": "8032"},  # animal → organism
            {"UNII": "3Z252A2K9G", "PLANTS": "PRDU"},  # plant → organism
            {"UNII": "2052SC0X7O"},  # defined chemical → not organism
        ],
    )
    assert read_organism_uniis(str(records)) == {"7TI7U5PF2U", "3Z252A2K9G"}


@pytest.mark.unit
def test_unii_organism_columns_present_in_header():
    """The organism columns we key on must exist in the header layout the reader expects."""
    assert set(UNII_ORGANISM_COLUMNS) <= set(UNII_RECORDS_HEADER)


# ----
# extract_drugbank_allergenic_extract_types
# ----


@pytest.mark.unit
def test_extract_drugbank_allergenic_extract_types(tmp_path):
    """Foods (UNII under NCIt Food/Seed) → Food; non-food allergens → ComplexMolecularMixture; a real
    chemical (with an InChI Key) and an unrelated structureless entry get neither."""
    vocab = tmp_path / "drugbank vocabulary.csv"
    _write_vocab(
        vocab,
        [
            # id, accession, common name, CAS, UNII, synonyms, InChIKey
            ("DB10626", "", "Trout", "", "7TI7U5PF2U", "", ""),  # NCIt food → Food
            ("DB10500", "", "Almond", "", "3Z252A2K9G", "", ""),  # NCIt seed → Food
            ("DB10351", "", "Cynodon dactylon pollen", "", "175F461W10", "Allergenic extract- bermuda grass", ""),
            ("DB00316", "", "Acetaminophen", "103-90-2", "2052SC0X7O", "", "RZVAJINKPMORJF-UHFFFAOYSA-N"),
            ("DB99999", "", "Mystery reagent", "", "ZZZZZZZZZZ", "", ""),  # structureless, not food, no allergen text
        ],
    )
    records = tmp_path / "Latest_UNII_Records.txt"
    _write_unii_records(
        records,
        [
            {"UNII": "7TI7U5PF2U", "NCIT": "C71910"},  # trout → a food code
            {"UNII": "3Z252A2K9G", "NCIT": "C74458"},  # almond → a seed code
            {"UNII": "175F461W10", "NCIT": "C85157"},  # pollen → NOT a food code
            {"UNII": "2052SC0X7O", "NCIT": "C198"},  # acetaminophen
        ],
    )
    food_codes = tmp_path / "ncit_food_codes"
    food_codes.write_text("NCIT:C71910\nNCIT:C74458\n")  # trout + almond classified as food
    outfile = tmp_path / "DRUGBANK_allergenic_extracts"

    extract_drugbank_allergenic_extract_types(str(vocab), str(records), str(food_codes), str(outfile))

    lines = set(outfile.read_text().splitlines())
    assert lines == {
        f"DRUGBANK:DB10626\t{FOOD}",
        f"DRUGBANK:DB10500\t{FOOD}",
        f"DRUGBANK:DB10351\t{COMPLEX_MOLECULAR_MIXTURE}",
    }


@pytest.mark.unit
def test_classify_food_takes_precedence_over_allergen_text():
    """A food that also carries allergen text stays biolink:Food (food is checked first)."""
    row = {
        "Common name": "Peanut",
        "Synonyms": "Peanut allergenic extract",
        "UNII": "PEANUTUNII",
        "Standard InChI Key": "",
    }
    result = classify_allergenic_extract(row, {"PEANUTUNII": "NCIT:C71993"}, {"NCIT:C71993"})
    assert result == FOOD


@pytest.mark.unit
def test_classify_requires_missing_structure():
    """A plant-derived molecule that still has an InChI Key is a chemical, not an extract."""
    row = {"UNII": "3Z252A2K9G", "Common name": "Some plant alkaloid", "Standard InChI Key": "ABC-DEF-G"}
    assert classify_allergenic_extract(row, {"3Z252A2K9G": "NCIT:C74458"}, {"NCIT:C74458"}) is None
