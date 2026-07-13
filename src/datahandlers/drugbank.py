# Download CC-0 licensed data from DrugBank (https://go.drugbank.com/releases/latest)
import csv
import os.path
import shutil
from zipfile import ZipFile

import requests

from src.categories import COMPLEX_MOLECULAR_MIXTURE, FOOD
from src.datahandlers.ncit import read_ncit_code_set
from src.datahandlers.unii import read_unii_flags
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


def classify_food_or_extract(row, unii_to_ncit, food_ncit_codes, nonfood_ncit_codes, plant_uniis, extract_markers):
    """Return ``(biolink_type, signal)`` a DrugBank vocabulary row should be retyped to, or
    ``(None, None)`` (issue #828).

    DrugBank ships food-and-extract products as structureless organism materials (whole trout,
    strawberry, ragweed pollen, willow bark, cat dander, ...) that default to biolink:ChemicalEntity.
    The aim is to type as many of the *foods* among them as biolink:Food as the available signals
    safely allow. We only consider rows with **no** ``Standard InChI Key`` (an extract/material, not
    a defined molecule, so a small molecule extracted from a plant stays a chemical), and then:

    - The row is treated as **food material** when its UNII is classified under NCIt "Food"/"Seed"
      (``food_ncit_codes`` — NCIt types a food by what it is, not what it came from, so this covers
      scallop, venison and beef liver as well as strawberries) *or* its UNII carries a
      botanical-database flag (``plant_uniis`` — PLANTS/GRIN/MPNS, which reaches the plant materials
      NCIt has no food class for). Everything else is left as biolink:ChemicalEntity and deferred:
      most importantly the NCBI-only organism entries, where the same flag covers real foods
      (lobster, mushroom) and biologics (immune globulins, antivenins, CAR-T), so retyping on it
      would call a biologic a food (issue #930).
    - Among that material, a row whose name/synonyms contain an ``extract_markers`` substring
      (``"extract"``) is a processed extract → **biolink:ComplexMolecularMixture** (an interim type;
      the eventual home is biolink:ProcessedMaterial once issue #929 adds that output). Bark/root/
      leaf/pollen *extracts* land here.
    - A botanical flag says "plant material", not "food", so on its own it must not overrule an NCIt
      class that says the entry is a drug: a row whose NCIt class is under ``nonfood_ncit_codes``
      (imaging agents, antineoplastics) is left as biolink:ChemicalEntity — DrugBank:DB00965
      "Ethiodized oil", a poppy-seed-oil contrast agent, is the motivating case. Explicit NCIt
      Food/Seed evidence still wins, so a food that is also a diagnostic agent (inulin) is unaffected.
    - Any other food material → **biolink:Food** (whole fruits, roots, seeds, herbs, meats). The
      finer Food-vs-biolink:OrganismTaxon distinction is deferred to issue #926.

    ``signal`` records which branch fired (``ncit-food``, ``botanical-flag``, or ``extract``) so the
    audit CSVs and the ids file share one classification.
    """
    if (row.get("Standard InChI Key") or "").strip() != "":
        return None, None
    unii = (row.get("UNII") or "").strip()
    is_ncit_food = bool(unii) and unii_to_ncit.get(unii) in food_ncit_codes
    is_plant = unii in plant_uniis
    if not (is_ncit_food or is_plant):
        return None, None
    # Both sides are lower-cased: the markers come from config, and an entry written "Extract" would
    # otherwise silently never match.
    text = f"{row.get('Common name', '')} {row.get('Synonyms', '')}".lower()
    if any(marker.lower() in text for marker in extract_markers):
        return COMPLEX_MOLECULAR_MIXTURE, "extract"
    if not is_ncit_food and unii_to_ncit.get(unii) in nonfood_ncit_codes:
        return None, None
    return FOOD, ("ncit-food" if is_ncit_food else "botanical-flag")


def write_drugbank_food_extract_types(
    drugbank_vocab_csv, unii_records, food_ncit_codes_file, nonfood_ncit_codes_file, extract_markers, outfile
):
    """Write ``DRUGBANK:xxx\\tbiolink:Type`` for DrugBank food/extracts to retype (issue #828).

    Reads the raw DrugBank vocabulary CSV (whose ``UNII`` column the label/synonym extractor
    discards), the FDA UNII records (for each UNII's NCIt class and its plant-database flags), and the
    enumerated NCIt Food/Seed and never-food subtrees, then classifies each structureless food material
    as biolink:Food or (for extracts) biolink:ComplexMolecularMixture (see classify_food_or_extract).
    ``extract_markers`` is the config list of name/synonym substrings that mark an extract. The output
    drives the retype in ``chemicals.create_typed_sets``.
    """
    unii_to_ncit, plant_uniis, _organism_uniis = read_unii_flags(unii_records)
    food_ncit_codes = read_ncit_code_set(food_ncit_codes_file)
    nonfood_ncit_codes = read_ncit_code_set(nonfood_ncit_codes_file)
    with open(drugbank_vocab_csv) as fin, open(outfile, "w") as outf:
        reader = csv.DictReader(fin)
        missing = {"DrugBank ID", "UNII", "Standard InChI Key"} - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"{drugbank_vocab_csv} is missing the columns the retype needs: {sorted(missing)}")
        for row in reader:
            biolink_type, _signal = classify_food_or_extract(
                row, unii_to_ncit, food_ncit_codes, nonfood_ncit_codes, plant_uniis, extract_markers
            )
            if biolink_type:
                outf.write(f"{DRUGBANK}:{row['DrugBank ID']}\t{biolink_type}\n")
