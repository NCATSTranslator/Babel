#!/usr/bin/env python
"""Regenerate the two DrugBank food-and-extract audit CSVs in this directory (issue #828).

This is the committed generator for the sibling files:

  - ``food-and-extracts.csv`` (File A) — every structureless DrugBank food/material this PR retypes,
    with the type it ships now (``biolink:Food`` or, for extracts, the interim
    ``biolink:ComplexMolecularMixture``) and, on the extract rows, the ``future_biolink_type``
    (``biolink:ProcessedMaterial``) they should become once issue #929 adds that output.
  - ``ncbi-only-drugbank-entries.csv`` (File B) — the NCBI-only structureless entries we deliberately
    do *not* retype yet (animals, bacteria, fungi, biologics, danders), the review set for issue #930.
    It carries everything we know about each entry — the UNII's NCBI taxon (with label), its NCIt
    class (with label), its preferred name, and whether the DrugBank name/synonyms say "extract" —
    because that is what #930 needs to separate the genuine foods (scallop, lobster) from the
    extracts and the biologics (immune globulins, whose taxon is *Homo sapiens*).

The classification is imported from production code (``classify_food_or_extract``) so this script
and the ``chemical_drugbank_food_extracts`` pipeline rule can never drift.

Inputs (pinned DrugBank vocabulary; current FDA UNII records):

  - ``babel_downloads/DRUGBANK/drugbank vocabulary.csv``
  - ``babel_downloads/UNII/Latest_UNII_Records.txt``  (via ``pull_unii()`` if absent)
  - ``babel_downloads/NCIT/labels`` and ``babel_downloads/NCBITaxon/labels`` — for the label columns;
    Snakemake rules ``ncit_labels`` / ``ncbitaxon_labels_and_synonyms``, e.g.

        uv run snakemake -c2 babel_downloads/NCBITaxon/labels

  - ``ncit_food_codes`` — the enumerated NCIt Food/Seed subtree. Produced by the
    ``chemical_ncit_food_codes`` Snakemake rule, or directly (UberGraph query):

        uv run python -c "import src.createcompendia.chemicals as c, src.util as u; \\
          c.write_ncit_descendant_codes(u.get_config()['drugbank_food_ncit_roots'], 'ncit_food_codes')"

Run (from the repo root):

    uv run python docs/sources/DRUGBANK/food-and-extracts/scripts/generate_csvs.py \\
        --ncit-food-codes babel_outputs/intermediate/chemicals/ids/ncit_food_codes
"""

import argparse
import csv
from pathlib import Path

from src.categories import COMPLEX_MOLECULAR_MIXTURE
from src.datahandlers.drugbank import classify_food_or_extract
from src.datahandlers.unii import (
    UNII_RECORDS_ENCODING,
    read_organism_uniis,
    read_plant_uniis,
    read_unii_ncit,
)
from src.prefixes import DRUGBANK, NCBITAXON
from src.util import get_config

# ProcessedMaterial is the eventual home for the "extract" rows once issue #929 adds that output.
FUTURE_EXTRACT_TYPE = "biolink:ProcessedMaterial"

HERE = Path(__file__).resolve().parent.parent  # docs/sources/DRUGBANK/food-and-extracts/
FILE_A = HERE / "food-and-extracts.csv"
FILE_B = HERE / "ncbi-only-drugbank-entries.csv"


def read_labels(labels_file):
    """Return {CURIE -> label} from a Babel ``CURIE\\tlabel`` labels file (``babel_downloads/<PREFIX>/labels``)."""
    with open(labels_file) as inf:
        return dict(line.rstrip("\n").split("\t", 1) for line in inf if "\t" in line)


def read_unii_records(unii_records):
    """Return {UNII code -> raw Latest_UNII_Records.txt row} so File B can report the UNII's own fields."""
    with open(unii_records, encoding=UNII_RECORDS_ENCODING) as inf:
        return {row["UNII"]: row for row in csv.DictReader(inf, delimiter="\t")}


def generate(
    vocab_csv, unii_records, ncit_food_codes_file, extract_markers, ncit_labels, ncbitaxon_labels, file_a, file_b
):
    """Write File A (retype changes) and File B (deferred NCBI-only), returning per-file row counts."""
    unii_to_ncit = read_unii_ncit(unii_records)
    plant_uniis = read_plant_uniis(unii_records)
    organism_uniis = read_organism_uniis(unii_records)
    unii_rows = read_unii_records(unii_records)
    ncit_label = read_labels(ncit_labels)
    taxon_label = read_labels(ncbitaxon_labels)
    with open(ncit_food_codes_file) as inf:
        food_ncit_codes = {line.strip() for line in inf if line.strip()}

    a_rows, b_rows = [], []
    with open(vocab_csv) as fin:
        for row in csv.DictReader(fin):
            curie = f"{DRUGBANK}:{row['DrugBank ID']}"
            unii = (row.get("UNII") or "").strip()
            ncit = unii_to_ncit.get(unii, "")
            biolink_type, signal = classify_food_or_extract(
                row, unii_to_ncit, food_ncit_codes, plant_uniis, extract_markers
            )
            if biolink_type:
                a_rows.append(
                    {
                        "drugbank_curie": curie,
                        "label": row.get("Common name", ""),
                        "unii": f"UNII:{unii}" if unii else "",
                        "ncit": ncit,
                        "ncit_label": ncit_label.get(ncit, ""),
                        "biolink_type": biolink_type,
                        "future_biolink_type": FUTURE_EXTRACT_TYPE if biolink_type == COMPLEX_MOLECULAR_MIXTURE else "",
                        "signal": signal,
                    }
                )
            elif (
                (row.get("Standard InChI Key") or "").strip() == ""
                and unii in organism_uniis
                and unii not in plant_uniis
            ):
                # Structureless, organism-flagged, but NCBI-only (no botanical flag): the deferred set.
                # Everything we know about the entry goes in, because deciding whether one of these is a
                # food, an extract, or a biologic (issue #930) needs the source organism above all: the
                # UNII's NCBI taxon says "Pecten" (scallop, a food) vs "Homo sapiens" (an immune globulin).
                taxon = unii_rows.get(unii, {}).get("NCBI", "").strip()
                taxon_curie = f"{NCBITAXON}:{taxon}" if taxon else ""
                name_and_synonyms = f"{row.get('Common name', '')} {row.get('Synonyms', '')}".lower()
                b_rows.append(
                    {
                        "drugbank_curie": curie,
                        "label": row.get("Common name", ""),
                        "unii": f"UNII:{unii}" if unii else "",
                        "unii_preferred_name": unii_rows.get(unii, {}).get("Display Name", ""),
                        "ncbitaxon": taxon_curie,
                        "ncbitaxon_label": taxon_label.get(taxon_curie, ""),
                        "unii_ncit": ncit,
                        "unii_ncit_label": ncit_label.get(ncit, ""),
                        "has_extract_marker": str(any(marker in name_and_synonyms for marker in extract_markers)),
                    }
                )

    a_rows.sort(key=lambda r: r["drugbank_curie"])
    b_rows.sort(key=lambda r: r["drugbank_curie"])
    _write_csv(
        file_a,
        ["drugbank_curie", "label", "unii", "ncit", "ncit_label", "biolink_type", "future_biolink_type", "signal"],
        a_rows,
    )
    _write_csv(
        file_b,
        [
            "drugbank_curie",
            "label",
            "unii",
            "unii_preferred_name",
            "ncbitaxon",
            "ncbitaxon_label",
            "unii_ncit",
            "unii_ncit_label",
            "has_extract_marker",
        ],
        b_rows,
    )
    return a_rows, b_rows


def _write_csv(path, fieldnames, rows):
    """Write ``rows`` to ``path`` as UTF-8 CSV with LF line endings."""
    with open(path, "w", newline="\n") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    config = get_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    dd = config["download_directory"]
    parser.add_argument("--vocab-csv", default=f"{dd}/DRUGBANK/drugbank vocabulary.csv")
    parser.add_argument("--unii-records", default=f"{dd}/UNII/Latest_UNII_Records.txt")
    parser.add_argument(
        "--ncit-food-codes", default=f"{config['intermediate_directory']}/chemicals/ids/ncit_food_codes"
    )
    parser.add_argument("--ncit-labels", default=f"{dd}/NCIT/labels")
    parser.add_argument("--ncbitaxon-labels", default=f"{dd}/NCBITaxon/labels")
    args = parser.parse_args()

    a_rows, b_rows = generate(
        args.vocab_csv,
        args.unii_records,
        args.ncit_food_codes,
        config["drugbank_extract_markers"],
        args.ncit_labels,
        args.ncbitaxon_labels,
        FILE_A,
        FILE_B,
    )
    food = sum(1 for r in a_rows if r["biolink_type"] == "biolink:Food")
    cmm = sum(1 for r in a_rows if r["biolink_type"] == COMPLEX_MOLECULAR_MIXTURE)
    print(f"File A {FILE_A.name}: {len(a_rows)} rows ({food} Food + {cmm} ComplexMolecularMixture→ProcessedMaterial)")
    print(f"File B {FILE_B.name}: {len(b_rows)} NCBI-only deferred rows")


if __name__ == "__main__":
    main()
