# Download CC-0 licensed data from DrugBank (https://go.drugbank.com/releases/latest)
import csv
import os.path
import shutil
from zipfile import ZipFile

import requests

from src.categories import COMPLEX_MOLECULAR_MIXTURE, FOOD
from src.datahandlers.unii import read_unii_ncit
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


def classify_allergenic_extract(row, unii_to_ncit, food_ncit_codes):
    """Return the Biolink type a DrugBank vocabulary row should be retyped to, or None (issue #828).

    DrugBank ships allergenic-extract products as structureless organism extracts (whole trout,
    strawberry, ragweed pollen, cat dander, ...) that default to biolink:ChemicalEntity. We only
    consider rows with **no** ``Standard InChI Key`` (an extract, not a defined molecule, so a
    genuine plant-derived small molecule stays a chemical), and split them:

    - biolink:Food when the row's UNII is classified under NCIt "Food"/"Seed" (``food_ncit_codes``)
      — trout, strawberry, beef, almond, wheat, ...
    - biolink:ComplexMolecularMixture when it is an allergenic extract that is not a food (its
      name/synonyms mention "allergen") — pollens, danders, molds, mites, dust. (biolink:Food is
      wrong for these; ComplexMolecularMixture is the closest existing class — see the docs for
      the PhysicalEntity alternative and the pending Biolink request.)

    Foods are checked first so a food that also happens to carry allergen text stays biolink:Food.
    """
    if (row.get("Standard InChI Key") or "").strip() != "":
        return None
    unii = (row.get("UNII") or "").strip()
    if unii and unii_to_ncit.get(unii) in food_ncit_codes:
        return FOOD
    text = f"{row.get('Common name', '')} {row.get('Synonyms', '')}".lower()
    if "allergen" in text:
        return COMPLEX_MOLECULAR_MIXTURE
    return None


def extract_drugbank_allergenic_extract_types(drugbank_vocab_csv, unii_records, food_ncit_codes_file, outfile):
    """Write ``DRUGBANK:xxx\\tbiolink:Type`` for DrugBank allergenic extracts to retype (issue #828).

    Reads the raw DrugBank vocabulary CSV (whose ``UNII`` column the label/synonym extractor
    discards), the FDA UNII records (for each UNII's NCIt class), and the enumerated NCIt Food/Seed
    subtree, then classifies each structureless extract as biolink:Food or
    biolink:ComplexMolecularMixture (see classify_allergenic_extract). The output drives the retype
    in ``chemicals.create_typed_sets``.
    """
    unii_to_ncit = read_unii_ncit(unii_records)
    with open(food_ncit_codes_file) as inf:
        food_ncit_codes = {line.strip() for line in inf if line.strip()}
    with open(drugbank_vocab_csv) as fin, open(outfile, "w") as outf:
        reader = csv.DictReader(fin)
        assert "DrugBank ID" in reader.fieldnames
        assert "UNII" in reader.fieldnames
        assert "Standard InChI Key" in reader.fieldnames
        for row in reader:
            biolink_type = classify_allergenic_extract(row, unii_to_ncit, food_ncit_codes)
            if biolink_type:
                outf.write(f"{DRUGBANK}:{row['DrugBank ID']}\t{biolink_type}\n")
