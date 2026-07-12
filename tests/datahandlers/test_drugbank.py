"""Unit tests for the DrugBank food-and-extract retype (issue #828).

Covers datahandlers.drugbank.write_drugbank_food_extract_types (which DRUGBANK ids become
biolink:Food vs biolink:ComplexMolecularMixture) and the UNII helpers it and write_unii_ids rely on
(read_unii_ncit, read_organism_uniis, read_plant_uniis).
"""

import pytest

from src.categories import COMPLEX_MOLECULAR_MIXTURE, FOOD
from src.datahandlers.drugbank import classify_food_or_extract, write_drugbank_food_extract_types
from src.datahandlers.unii import (
    UNII_ORGANISM_COLUMNS,
    UNII_PLANT_COLUMNS,
    read_organism_uniis,
    read_plant_uniis,
    read_unii_ncit,
)

# Header for the CC-0 DrugBank vocabulary CSV, in the fixed column order Babel reads.
DRUGBANK_VOCAB_HEADER = "DrugBank ID,Accession Numbers,Common name,CAS,UNII,Synonyms,Standard InChI Key"

# UNII records are Windows-1252 TSV; only the columns Babel reads need to be present/positioned.
UNII_RECORDS_HEADER = ["UNII", "PT", "NCIT", "NCBI", "PLANTS", "GRIN", "MPNS"]

# The name/synonym substrings that mark a processed extract → ComplexMolecularMixture (config
# drugbank_extract_markers). "allergen" is deliberately not one of them (issue #828).
EXTRACT_MARKERS = ["extract"]


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
def test_read_plant_uniis_flags_only_botanical_records(tmp_path):
    """read_plant_uniis includes a UNII with any of PLANTS/GRIN/MPNS but excludes NCBI-only records."""
    records = tmp_path / "Latest_UNII_Records.txt"
    _write_unii_records(
        records,
        [
            {"UNII": "PLANTS0001", "PLANTS": "PRDU"},  # plant → included
            {"UNII": "GRINMPNS02", "GRIN": "1", "MPNS": "x"},  # plant → included
            {"UNII": "NCBIONLY03", "NCBI": "8032"},  # animal, NCBI-only → excluded
            {"UNII": "NOFLAGS004"},  # defined chemical → excluded
        ],
    )
    assert read_plant_uniis(str(records)) == {"PLANTS0001", "GRINMPNS02"}


@pytest.mark.unit
def test_unii_organism_columns_present_in_header():
    """The organism columns we key on must exist in the header layout the reader expects."""
    assert set(UNII_ORGANISM_COLUMNS) <= set(UNII_RECORDS_HEADER)


@pytest.mark.unit
def test_unii_plant_columns_are_botanical_subset():
    """Plant columns are the botanical subset of the organism columns, excluding NCBI."""
    assert set(UNII_PLANT_COLUMNS) < set(UNII_ORGANISM_COLUMNS)
    assert "NCBI" not in UNII_PLANT_COLUMNS


# ----
# write_drugbank_food_extract_types
# ----


@pytest.mark.unit
def test_write_drugbank_food_extract_types(tmp_path):
    """Plant/food material → Food; a plant *extract* → ComplexMolecularMixture; a real chemical (InChI
    Key), an NCBI-only organism, and an unflagged structureless entry get neither."""
    vocab = tmp_path / "drugbank vocabulary.csv"
    _write_vocab(
        vocab,
        [
            # id, accession, common name, CAS, UNII, synonyms, InChIKey
            ("DB10626", "", "Trout", "", "7TI7U5PF2U", "", ""),  # NCIt food (NCBI animal) → Food
            ("DB10500", "", "Almond", "", "3Z252A2K9G", "", ""),  # NCIt seed (plant) → Food
            ("DB16536", "", "Birch bark extract", "", "3R504894L9", "", ""),  # plant + "extract" → CMM
            ("DB10650", "", "Raphanus sativus", "", "RADISH0000", "", ""),  # plant, no extract → Food
            ("DB00316", "", "Acetaminophen", "103-90-2", "2052SC0X7O", "", "RZVAJINKPMORJF-UHFFFAOYSA-N"),
            ("DB10417", "", "Periplaneta americana", "", "2RQ1L9N089", "cockroach allergen", ""),  # NCBI-only
            ("DB99999", "", "Mystery reagent", "", "ZZZZZZZZZZ", "", ""),  # structureless, no flag, not food
        ],
    )
    records = tmp_path / "Latest_UNII_Records.txt"
    _write_unii_records(
        records,
        [
            {"UNII": "7TI7U5PF2U", "NCIT": "C71910", "NCBI": "8032"},  # trout → food code, animal
            {"UNII": "3Z252A2K9G", "NCIT": "C74458", "PLANTS": "PRDU"},  # almond → seed code, plant
            {"UNII": "3R504894L9", "PLANTS": "BEPE"},  # birch → plant, no food code
            {"UNII": "RADISH0000", "PLANTS": "RASA2"},  # radish → plant, no food code
            {"UNII": "2052SC0X7O", "NCIT": "C198"},  # acetaminophen
            {"UNII": "2RQ1L9N089", "NCBI": "6970"},  # cockroach → NCBI-only, not a food
        ],
    )
    food_codes = tmp_path / "ncit_food_codes"
    food_codes.write_text("NCIT:C71910\nNCIT:C74458\n")  # trout + almond classified as food
    outfile = tmp_path / "DRUGBANK_food_extracts"

    write_drugbank_food_extract_types(str(vocab), str(records), str(food_codes), EXTRACT_MARKERS, str(outfile))

    lines = set(outfile.read_text().splitlines())
    assert lines == {
        f"DRUGBANK:DB10626\t{FOOD}",
        f"DRUGBANK:DB10500\t{FOOD}",
        f"DRUGBANK:DB16536\t{COMPLEX_MOLECULAR_MIXTURE}",
        f"DRUGBANK:DB10650\t{FOOD}",
    }


# ----
# classify_food_or_extract
# ----


@pytest.mark.unit
def test_classify_plant_material_without_extract_is_food():
    """A plant-flagged structureless material with no 'extract' marker is biolink:Food."""
    row = {"Common name": "Raphanus sativus", "Synonyms": "", "UNII": "RADISH", "Standard InChI Key": ""}
    assert classify_food_or_extract(row, {}, set(), {"RADISH"}, EXTRACT_MARKERS) == (FOOD, "botanical-flag")


@pytest.mark.unit
def test_classify_plant_extract_is_complex_molecular_mixture():
    """A plant-flagged material whose name says 'extract' is biolink:ComplexMolecularMixture."""
    row = {"Common name": "Birch bark extract", "Synonyms": "", "UNII": "BARK", "Standard InChI Key": ""}
    result = classify_food_or_extract(row, {}, set(), {"BARK"}, EXTRACT_MARKERS)
    assert result == (COMPLEX_MOLECULAR_MIXTURE, "extract")


@pytest.mark.unit
def test_classify_extract_marker_beats_ncit_food():
    """'extract' routes even an NCIt-food row to ComplexMolecularMixture (extract check wins)."""
    row = {"Common name": "Soybean extract", "Synonyms": "", "UNII": "SOY", "Standard InChI Key": ""}
    result = classify_food_or_extract(row, {"SOY": "NCIT:C72010"}, {"NCIT:C72010"}, set(), EXTRACT_MARKERS)
    assert result == (COMPLEX_MOLECULAR_MIXTURE, "extract")


@pytest.mark.unit
def test_classify_allergen_text_no_longer_triggers_cmm():
    """'allergen' is no longer a marker: a plant material carrying allergen (but not extract) text is
    still biolink:Food, not ComplexMolecularMixture."""
    row = {"Common name": "Ragweed pollen", "Synonyms": "allergenic", "UNII": "RAG", "Standard InChI Key": ""}
    assert classify_food_or_extract(row, {}, set(), {"RAG"}, EXTRACT_MARKERS) == (FOOD, "botanical-flag")


@pytest.mark.unit
def test_classify_ncbi_only_is_not_retyped():
    """An NCBI-only organism (not plant-flagged, not NCIt-food) is left alone — deferred work."""
    row = {"Common name": "Periplaneta americana", "Synonyms": "allergen", "UNII": "ROACH", "Standard InChI Key": ""}
    assert classify_food_or_extract(row, {}, set(), set(), EXTRACT_MARKERS) == (None, None)


@pytest.mark.unit
def test_classify_requires_missing_structure():
    """A plant-derived molecule that still has an InChI Key is a chemical, not an extract."""
    row = {"UNII": "3Z252A2K9G", "Common name": "Some plant alkaloid", "Standard InChI Key": "ABC-DEF-G"}
    assert classify_food_or_extract(row, {}, set(), {"3Z252A2K9G"}, EXTRACT_MARKERS) == (None, None)
