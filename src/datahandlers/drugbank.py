# Download CC-0 licensed data from DrugBank (https://go.drugbank.com/releases/latest)
import csv
import os.path
import shutil
from zipfile import ZipFile

import requests

from src.categories import COMPLEX_MOLECULAR_MIXTURE, FOOD
from src.datahandlers.unii import read_plant_uniis, read_unii_ncit
from src.predicates import HAS_EXACT_SYNONYM
from src.prefixes import DRUGBANK


def download_drugbank_vocabulary(drugbank_version, outfile):
    """Download a particular version of the DrugBank vocabulary."""

    # Download from URL using Requests.
    response = requests.get(
        f"https://go.drugbank.com/releases/{drugbank_version}/downloads/all-drugbank-vocabulary", stream=True
    )

    with open(outfile + ".zip", "wb") as fout:
        shutil.copyfileobj(response.raw, fout)

    # Decompress file.
    with ZipFile(outfile + ".zip", "r") as zipObj:
        zipObj.extractall(os.path.dirname(outfile))


def extract_drugbank_labels_and_synonyms(drugbank_vocab_csv, labels, synonyms):
    """
    Extract labels and synonyms for DRUGBANK IDs from the DrugBank vocabulary file (see download_drugbank_vocabulary()).

    :param drugbank_vocab_csv: The DrugBank vocabulary file downloaded with download_drugbank_vocabulary().
    :param labels: The file to write labels into.
    :param synonyms: The file to write synonyms into.
    """

    with open(drugbank_vocab_csv) as fin, open(labels, "w") as labelsf, open(synonyms, "w") as synonymsf:
        reader = csv.DictReader(fin)
        assert "DrugBank ID" in reader.fieldnames
        assert "Common name" in reader.fieldnames
        assert "Synonyms" in reader.fieldnames
        for line in reader:
            drugbank_id = f"{DRUGBANK}:{line['DrugBank ID']}"
            if "Common name" in line and line["Common name"].strip() != "":
                labelsf.write(f"{drugbank_id}\t{line['Common name']}\n")
            if "Synonyms" in line and line["Synonyms"].strip() != "":
                synonyms = line["Synonyms"].split(" | ")
                for syn in synonyms:
                    synonymsf.write(f"{drugbank_id}\t{HAS_EXACT_SYNONYM}\t{syn}\n")


def classify_food_or_extract(row, unii_to_ncit, food_ncit_codes, plant_uniis, extract_markers):
    """Return ``(biolink_type, signal)`` a DrugBank vocabulary row should be retyped to, or
    ``(None, None)`` (issue #828).

    DrugBank ships food-and-extract products as structureless organism materials (whole trout,
    strawberry, ragweed pollen, willow bark, cat dander, ...) that default to biolink:ChemicalEntity.
    We only consider rows with **no** ``Standard InChI Key`` (an extract/material, not a defined
    molecule, so a genuine plant-derived small molecule stays a chemical), and type the plant-derived
    ones:

    - The row is treated as **plant/food material** when its UNII is classified under NCIt "Food"/
      "Seed" (``food_ncit_codes``) *or* its UNII carries a botanical-database flag (``plant_uniis`` —
      PLANTS/GRIN/MPNS). Everything else (NCBI-only organisms — animals, bacteria, fungi, biologics —
      and unflagged rows) is left as biolink:ChemicalEntity and deferred for later work.
    - Among that material, a row whose name/synonyms contain an ``extract_markers`` substring
      (``"extract"``) is a processed extract → **biolink:ComplexMolecularMixture** (an interim type;
      the eventual home is biolink:ProcessedMaterial once issue #929 adds that output). Bark/root/
      leaf/pollen *extracts* land here.
    - Any other plant/food material → **biolink:Food** (whole fruits, roots, seeds, herbs). The
      finer Food-vs-biolink:OrganismTaxon distinction is deferred to issue #926.

    ``signal`` records which branch fired (``ncit-food``, ``plant-food``, or ``extract``) so the
    audit CSVs and the ids file share one classification.
    """
    if (row.get("Standard InChI Key") or "").strip() != "":
        return None, None
    unii = (row.get("UNII") or "").strip()
    is_ncit_food = bool(unii) and unii_to_ncit.get(unii) in food_ncit_codes
    is_plant = unii in plant_uniis
    if not (is_ncit_food or is_plant):
        return None, None
    text = f"{row.get('Common name', '')} {row.get('Synonyms', '')}".lower()
    if any(marker in text for marker in extract_markers):
        return COMPLEX_MOLECULAR_MIXTURE, "extract"
    return FOOD, ("ncit-food" if is_ncit_food else "plant-food")


def write_drugbank_food_extract_types(drugbank_vocab_csv, unii_records, food_ncit_codes_file, extract_markers, outfile):
    """Write ``DRUGBANK:xxx\\tbiolink:Type`` for DrugBank food/extracts to retype (issue #828).

    Reads the raw DrugBank vocabulary CSV (whose ``UNII`` column the label/synonym extractor
    discards), the FDA UNII records (for each UNII's NCIt class and its plant-database flags), and the
    enumerated NCIt Food/Seed subtree, then classifies each structureless plant/food material as
    biolink:Food or (for extracts) biolink:ComplexMolecularMixture (see classify_food_or_extract).
    ``extract_markers`` is the config list of name/synonym substrings that mark an extract. The output
    drives the retype in ``chemicals.create_typed_sets``.
    """
    unii_to_ncit = read_unii_ncit(unii_records)
    plant_uniis = read_plant_uniis(unii_records)
    with open(food_ncit_codes_file) as inf:
        food_ncit_codes = {line.strip() for line in inf if line.strip()}
    with open(drugbank_vocab_csv) as fin, open(outfile, "w") as outf:
        reader = csv.DictReader(fin)
        assert "DrugBank ID" in reader.fieldnames
        assert "UNII" in reader.fieldnames
        assert "Standard InChI Key" in reader.fieldnames
        for row in reader:
            biolink_type, _signal = classify_food_or_extract(
                row, unii_to_ncit, food_ncit_codes, plant_uniis, extract_markers
            )
            if biolink_type:
                outf.write(f"{DRUGBANK}:{row['DrugBank ID']}\t{biolink_type}\n")
