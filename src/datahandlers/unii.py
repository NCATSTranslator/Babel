import csv
from os import listdir, path, rename
from zipfile import ZipFile

import requests

from src.prefixes import NCIT, UNII
from src.util import get_config

# Columns in Latest_UNII_Records.txt that, when populated, mark a UNII as a whole organism or
# crude organism-derived substance (a plant, animal, fungus, etc.) rather than a defined
# chemical. These are the substances the chemical ingest deliberately skips ("a plant or an eye
# of newt") and the same signal the DrugBank food-and-extract retype (issue #828) uses to
# recognise that a structureless DrugBank entry is really a food/organism extract.
UNII_ORGANISM_COLUMNS = ["NCBI", "PLANTS", "GRIN", "MPNS"]

# The botanical-database subset of UNII_ORGANISM_COLUMNS. A UNII cross-referenced to any of the USDA
# PLANTS database, the GRIN germplasm database, or the Medicinal Plant Names Services (MPNS) reliably
# denotes plant material (a whole plant or a plant part/extract). NCBI is deliberately excluded: the
# NCBI taxonomy also covers animals, bacteria, fungi and the biologic-drug source organisms, so an
# NCBI flag alone is not a reliable "this is a plant/food" signal. Used by the DrugBank
# food-and-extract retype to recognise plant-derived Food/extract entries (issue #828).
UNII_PLANT_COLUMNS = ["PLANTS", "GRIN", "MPNS"]

# Latest_UNII_Records.txt is a Windows-1252 TSV.
UNII_RECORDS_ENCODING = "windows-1252"


def read_unii_records(records_file):
    """Yield each row of Latest_UNII_Records.txt as a {column name -> value} dict.

    QUOTE_NONE because the file is a plain tab-separated dump: a bare double quote in a substance
    name is data, not a quoted field.
    """
    with open(records_file, encoding=UNII_RECORDS_ENCODING) as inf:
        yield from csv.DictReader(inf, delimiter="\t", quoting=csv.QUOTE_NONE)


def read_unii_flags(records_file):
    """Return ``(unii_to_ncit, plant_uniis, organism_uniis)`` from one pass over Latest_UNII_Records.txt.

    - ``unii_to_ncit``: {UNII code -> NCIt CURIE, e.g. "NCIT:C71910"} for the records that carry an
      NCIt code. This is what lets the DrugBank food-and-extract retype (issue #828) decide that a
      structureless DrugBank entry is a food — its UNII's NCIt class is under NCIt "Food"/"Seed".
    - ``plant_uniis``: UNIIs flagged as plant material (any of UNII_PLANT_COLUMNS populated), which
      the same retype types biolink:Food, or biolink:ComplexMolecularMixture when the entry is an
      "extract".
    - ``organism_uniis``: UNIIs flagged as a whole organism / crude organism-derived substance (any of
      UNII_ORGANISM_COLUMNS populated), which chemicals.write_unii_ids excludes from the chemical
      compendium, and which the audit CSVs use to find the NCBI-only entries deferred to issue #930.

    All three come back together because every caller wants at least two of them and the file is one
    scan.
    """
    unii_to_ncit, plant_uniis, organism_uniis = {}, set(), set()
    for row in read_unii_records(records_file):
        unii = row["UNII"]
        ncit = (row.get("NCIT") or "").strip()
        if ncit:
            unii_to_ncit[unii] = f"{NCIT}:{ncit}"
        if any(row.get(col) for col in UNII_PLANT_COLUMNS):
            plant_uniis.add(unii)
        if any(row.get(col) for col in UNII_ORGANISM_COLUMNS):
            organism_uniis.add(unii)
    return unii_to_ncit, plant_uniis, organism_uniis


def pull_unii():
    for pullfile, originalprefix, finalname in [
        ("UNIIs.zip", "UNII_Names", "Latest_UNII_Names.txt"),
        ("UNII_Data.zip", "UNII_Records", "Latest_UNII_Records.txt"),
    ]:
        # Downloads also available from https://precision.fda.gov/uniisearch/archive
        url = f"https://precision.fda.gov/uniisearch/archive/latest/{pullfile}"
        response = requests.get(url, stream=True)
        if not response.ok:
            raise RuntimeError(f"Could not download {url}: {response}")
        local_filename = path.join(get_config()["download_directory"], "UNII", pullfile)
        with open(local_filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        ddir = path.dirname(local_filename)
        with ZipFile(local_filename, "r") as zipObj:
            zipObj.extractall(ddir)
        # this zip file unzips into a readme and a file named something like "UNII_Names_<date>.txt" and we need to rename it for make
        files = listdir(ddir)
        for filename in files:
            if filename.startswith(originalprefix):
                original = path.join(ddir, filename)
                final = path.join(ddir, finalname)
                rename(original, final)


def make_labels_and_synonyms(inputfile, labelfile, synfile):
    idcol = 2
    labelcol = 3
    syncol = 0
    wrotelabels = set()
    wrotesyns = set()
    with open(inputfile, encoding="latin-1") as inf, open(labelfile, "w") as lf, open(synfile, "w") as sf:
        _header = inf.readline()
        for line in inf:
            parts = line.strip().split("\t")
            ident = f"{UNII}:{parts[idcol]}"
            label = parts[labelcol]
            synonym = parts[syncol]
            lstring = f"{ident}\t{label}\n"
            sstring = f"{ident}\t{synonym}\n"
            if lstring not in wrotelabels:
                lf.write(lstring)
                wrotelabels.add(lstring)
            if sstring not in wrotesyns:
                sf.write(sstring)
