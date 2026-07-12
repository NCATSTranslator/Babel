from os import listdir, path, rename
from zipfile import ZipFile

import requests

from src.prefixes import NCIT, UNII
from src.util import get_config

# Columns in Latest_UNII_Records.txt that, when populated, mark a UNII as a whole organism or
# crude organism-derived substance (a plant, animal, fungus, etc.) rather than a defined
# chemical. These are the substances the chemical ingest deliberately skips ("a plant or an eye
# of newt") and the same signal the DrugBank allergenic-extract retype (issue #828) uses to
# recognise that a structureless DrugBank entry is really a food/organism extract.
UNII_ORGANISM_COLUMNS = ["NCBI", "PLANTS", "GRIN", "MPNS"]

# The botanical-database subset of UNII_ORGANISM_COLUMNS. A UNII cross-referenced to any of the USDA
# PLANTS database, the GRIN germplasm database, or the Medicinal Plant Names Services (MPNS) reliably
# denotes plant material (a whole plant or a plant part/extract). NCBI is deliberately excluded: the
# NCBI taxonomy also covers animals, bacteria, fungi and the biologic-drug source organisms, so an
# NCBI flag alone is not a reliable "this is a plant/food" signal. Used by the DrugBank
# allergenic-extract retype to recognise plant-derived Food/extract entries (issue #828).
UNII_PLANT_COLUMNS = ["PLANTS", "GRIN", "MPNS"]

# Latest_UNII_Records.txt is Windows-1252 encoded and column 0 is the UNII code.
UNII_RECORDS_ENCODING = "windows-1252"
UNII_RECORDS_CODE_COLUMN = 0

# Column in Latest_UNII_Records.txt holding the substance's NCIt code (bare, e.g. "C71910"). Used
# by the DrugBank allergenic-extract retype to recognise foods via NCIt classification (issue #828).
UNII_RECORDS_NCIT_COLUMN = "NCIT"


def read_unii_ncit(records_file):
    """Return {UNII code -> NCIt CURIE (e.g. "NCIT:C71910")} for records that carry an NCIt code.

    The NCIt code lets the DrugBank allergenic-extract retype decide whether a structureless
    DrugBank entry is a food (its UNII's NCIt class is under NCIt "Food"/"Seed").
    """
    unii_to_ncit = {}
    with open(records_file, encoding=UNII_RECORDS_ENCODING) as inf:
        header = inf.readline().rstrip("\n").split("\t")
        ncit_colno = header.index(UNII_RECORDS_NCIT_COLUMN)
        for line in inf:
            row = line.rstrip("\n").split("\t")
            ncit = row[ncit_colno].strip()
            if ncit:
                unii_to_ncit[row[UNII_RECORDS_CODE_COLUMN]] = f"{NCIT}:{ncit}"
    return unii_to_ncit


def _read_uniis_with_any_column(records_file, columns):
    """Return the set of UNII codes with any of ``columns`` populated in Latest_UNII_Records.txt."""
    uniis = set()
    with open(records_file, encoding=UNII_RECORDS_ENCODING) as inf:
        header = inf.readline().rstrip("\n").split("\t")
        colnos = [header.index(col) for col in columns]
        for line in inf:
            # rstrip("\n") not strip(): the organism columns are near the end and are usually
            # empty, and strip() would drop those trailing empty fields and misalign the row.
            row = line.rstrip("\n").split("\t")
            if any(len(row[colno]) > 0 for colno in colnos):
                uniis.add(row[UNII_RECORDS_CODE_COLUMN])
    return uniis


def read_organism_uniis(records_file):
    """Return the set of UNII codes flagged as a whole organism / crude organism-derived
    substance in Latest_UNII_Records.txt (any of UNII_ORGANISM_COLUMNS populated).

    Shared by chemicals.write_unii_ids (which excludes these from the chemical compendium) and
    the DrugBank allergenic-extract retype so the "this UNII is an organism" definition lives in
    one place.
    """
    return _read_uniis_with_any_column(records_file, UNII_ORGANISM_COLUMNS)


def read_plant_uniis(records_file):
    """Return the set of UNII codes flagged as plant material in Latest_UNII_Records.txt (any of
    UNII_PLANT_COLUMNS — PLANTS/GRIN/MPNS — populated).

    Used by the DrugBank allergenic-extract retype (issue #828) to recognise plant-derived entries
    (whole plants, plant parts, and plant extracts), which are typed biolink:Food or, when described
    as an "extract", biolink:ComplexMolecularMixture. Unlike read_organism_uniis this excludes
    NCBI-only records, which mix plants with animals/bacteria/fungi/biologics and are not retyped.
    """
    return _read_uniis_with_any_column(records_file, UNII_PLANT_COLUMNS)


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
