"""Unit tests for the DrugBank food-and-extract retype (issue #828).

Covers datahandlers.drugbank.write_drugbank_food_extract_types (which DRUGBANK ids become
biolink:Food vs biolink:ComplexMolecularMixture) and the UNII flag reader it and write_unii_ids rely
on (read_unii_flags).
"""

import pytest

from src.categories import COMPLEX_MOLECULAR_MIXTURE, FOOD
from src.datahandlers.drugbank import classify_food_or_extract, write_drugbank_food_extract_types
from src.datahandlers.unii import read_unii_flags

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
# UNII record reader
# ----


@pytest.mark.unit
def test_read_unii_flags(tmp_path):
    """read_unii_flags should map each UNII with an NCIt code to its CURIE; flag PLANTS/GRIN/MPNS
    records as plants; and flag those *plus* NCBI-only records as organisms (which write_unii_ids
    excludes from the chemical compendium, but which are not reliably plants/foods)."""
    records = tmp_path / "Latest_UNII_Records.txt"
    _write_unii_records(
        records,
        [
            {"UNII": "7TI7U5PF2U", "NCIT": "C71910", "NCBI": "8032"},  # trout: NCIt code, organism only
            {"UNII": "PLANTS0001", "PLANTS": "PRDU"},  # plant → plant + organism
            {"UNII": "GRINMPNS02", "GRIN": "1", "MPNS": "x"},  # plant → plant + organism
            {"UNII": "2052SC0X7O", "NCIT": ""},  # defined chemical: no NCIt code, no flags
        ],
    )

    unii_to_ncit, plant_uniis, organism_uniis = read_unii_flags(str(records))

    assert unii_to_ncit == {"7TI7U5PF2U": "NCIT:C71910"}
    assert plant_uniis == {"PLANTS0001", "GRINMPNS02"}
    assert organism_uniis == {"7TI7U5PF2U", "PLANTS0001", "GRINMPNS02"}


# ----
# write_drugbank_food_extract_types
# ----


@pytest.mark.unit
def test_write_drugbank_food_extract_types(tmp_path):
    """Food material → Food; an *extract* → ComplexMolecularMixture; a real chemical (InChI Key), an
    NCBI-only organism, an unflagged structureless entry, and a plant-flagged entry NCIt classifies as
    a drug (ethiodized oil) all get neither."""
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
            ("DB00965", "", "Ethiodized oil", "", "KZW0R0686Q", "", ""),  # plant, but NCIt says imaging agent
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
            {"UNII": "KZW0R0686Q", "NCIT": "C487", "PLANTS": "PASO2"},  # ethiodized oil → plant, but a drug
        ],
    )
    food_codes = tmp_path / "ncit_food_codes"
    food_codes.write_text("NCIT:C71910\nNCIT:C74458\n")  # trout + almond classified as food
    nonfood_codes = tmp_path / "ncit_nonfood_codes"
    nonfood_codes.write_text("NCIT:C487\n")  # ethiodized oil's NCIt class is never food
    outfile = tmp_path / "DRUGBANK_food_extracts"

    write_drugbank_food_extract_types(
        str(vocab), str(records), str(food_codes), str(nonfood_codes), EXTRACT_MARKERS, str(outfile)
    )

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
    assert classify_food_or_extract(row, {}, set(), set(), {"RADISH"}, EXTRACT_MARKERS) == (FOOD, "botanical-flag")


@pytest.mark.unit
def test_classify_plant_extract_is_complex_molecular_mixture():
    """A plant-flagged material whose name says 'extract' is biolink:ComplexMolecularMixture."""
    row = {"Common name": "Birch bark extract", "Synonyms": "", "UNII": "BARK", "Standard InChI Key": ""}
    result = classify_food_or_extract(row, {}, set(), set(), {"BARK"}, EXTRACT_MARKERS)
    assert result == (COMPLEX_MOLECULAR_MIXTURE, "extract")


@pytest.mark.unit
def test_classify_extract_marker_beats_ncit_food():
    """'extract' routes even an NCIt-food row to ComplexMolecularMixture (extract check wins)."""
    row = {"Common name": "Soybean extract", "Synonyms": "", "UNII": "SOY", "Standard InChI Key": ""}
    result = classify_food_or_extract(row, {"SOY": "NCIT:C72010"}, {"NCIT:C72010"}, set(), set(), EXTRACT_MARKERS)
    assert result == (COMPLEX_MOLECULAR_MIXTURE, "extract")


@pytest.mark.unit
def test_classify_allergen_text_no_longer_triggers_cmm():
    """'allergen' is no longer a marker: a plant material carrying allergen (but not extract) text is
    still biolink:Food, not ComplexMolecularMixture."""
    row = {"Common name": "Ragweed pollen", "Synonyms": "allergenic", "UNII": "RAG", "Standard InChI Key": ""}
    assert classify_food_or_extract(row, {}, set(), set(), {"RAG"}, EXTRACT_MARKERS) == (FOOD, "botanical-flag")


@pytest.mark.unit
def test_classify_ncbi_only_is_not_retyped():
    """An NCBI-only organism (not plant-flagged, not NCIt-food) is left alone — deferred work."""
    row = {"Common name": "Periplaneta americana", "Synonyms": "allergen", "UNII": "ROACH", "Standard InChI Key": ""}
    assert classify_food_or_extract(row, {}, set(), set(), set(), EXTRACT_MARKERS) == (None, None)


@pytest.mark.unit
def test_classify_botanical_flag_does_not_overrule_a_nonfood_ncit_class():
    """A botanical flag says 'plant material', not 'food', so it must not type a plant-derived *drug* as
    Food: DRUGBANK:DB00965 'Ethiodized oil' is a poppy-seed-oil contrast agent (NCIt 'Imaging Agent'),
    and should be left alone rather than retyped."""
    row = {"Common name": "Ethiodized oil", "Synonyms": "", "UNII": "KZW0R0686Q", "Standard InChI Key": ""}
    unii_to_ncit = {"KZW0R0686Q": "NCIT:C487"}
    result = classify_food_or_extract(row, unii_to_ncit, set(), {"NCIT:C487"}, {"KZW0R0686Q"}, EXTRACT_MARKERS)
    assert result == (None, None)


@pytest.mark.unit
def test_classify_ncit_food_beats_a_nonfood_ncit_class():
    """An explicit NCIt Food/Seed classification outranks the never-food veto, so a food that is also a
    diagnostic agent (inulin, used to measure GFR) stays biolink:Food."""
    row = {"Common name": "Inulin", "Synonyms": "", "UNII": "JOS53KRJ01", "Standard InChI Key": ""}
    unii_to_ncit = {"JOS53KRJ01": "NCIT:C61506"}
    result = classify_food_or_extract(
        row, unii_to_ncit, {"NCIT:C61506"}, {"NCIT:C61506"}, {"JOS53KRJ01"}, EXTRACT_MARKERS
    )
    assert result == (FOOD, "ncit-food")


@pytest.mark.unit
def test_classify_requires_missing_structure():
    """A plant-derived molecule that still has an InChI Key is a chemical, not an extract."""
    row = {"UNII": "3Z252A2K9G", "Common name": "Some plant alkaloid", "Standard InChI Key": "ABC-DEF-G"}
    assert classify_food_or_extract(row, {}, set(), set(), {"3Z252A2K9G"}, EXTRACT_MARKERS) == (None, None)
