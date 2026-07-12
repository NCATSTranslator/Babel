#!/usr/bin/env python
"""Regenerate the two DrugBank allergenic-extract audit CSVs in this directory (issue #828).

This is the committed generator for the sibling files:

  - ``allergenic-extracts.csv`` (File A) — every structureless DrugBank plant/food material this PR
    retypes, with the type it ships now (``biolink:Food`` or, for extracts, the interim
    ``biolink:ComplexMolecularMixture``) and, on the extract rows, the ``future_biolink_type``
    (``biolink:ProcessedMaterial``) they should become once issue #929 adds that output.
  - ``ncbi-only-drugbank-entries.csv`` (File B) — the NCBI-only structureless entries we deliberately
    do *not* retype yet (animals, bacteria, fungi, biologics, danders), the review set for the
    NCBI-only follow-up issue.

The classification is imported from production code (``classify_allergenic_extract``) so this script
and the ``chemical_drugbank_allergenic_extracts`` pipeline rule can never drift.

Inputs (pinned DrugBank vocabulary; current FDA UNII records):

  - ``babel_downloads/DRUGBANK/drugbank vocabulary.csv``
  - ``babel_downloads/UNII/Latest_UNII_Records.txt``  (via ``pull_unii()`` if absent)
  - ``ncit_food_codes`` — the enumerated NCIt Food/Seed subtree. Produced by the
    ``chemical_ncit_food_codes`` Snakemake rule, or directly (UberGraph query):

        uv run python -c "import src.createcompendia.chemicals as c, src.util as u; \\
          c.write_ncit_descendant_codes(u.get_config()['drugbank_food_ncit_roots'], 'ncit_food_codes')"

Run (from the repo root):

    uv run python docs/sources/DRUGBANK/allergenic-extracts/scripts/generate_csvs.py \\
        --ncit-food-codes babel_outputs/intermediate/chemicals/ids/ncit_food_codes
"""

import argparse
import csv
from pathlib import Path

from src.categories import COMPLEX_MOLECULAR_MIXTURE
from src.datahandlers.drugbank import classify_allergenic_extract
from src.datahandlers.unii import read_organism_uniis, read_plant_uniis, read_unii_ncit
from src.prefixes import DRUGBANK
from src.util import get_config

# ProcessedMaterial is the eventual home for the "extract" rows once issue #929 adds that output.
FUTURE_EXTRACT_TYPE = "biolink:ProcessedMaterial"

HERE = Path(__file__).resolve().parent.parent  # docs/sources/DRUGBANK/allergenic-extracts/
FILE_A = HERE / "allergenic-extracts.csv"
FILE_B = HERE / "ncbi-only-drugbank-entries.csv"


def generate(vocab_csv, unii_records, ncit_food_codes_file, extract_markers, file_a, file_b):
    """Write File A (retype changes) and File B (deferred NCBI-only), returning per-file row counts."""
    unii_to_ncit = read_unii_ncit(unii_records)
    plant_uniis = read_plant_uniis(unii_records)
    organism_uniis = read_organism_uniis(unii_records)
    with open(ncit_food_codes_file) as inf:
        food_ncit_codes = {line.strip() for line in inf if line.strip()}

    a_rows, b_rows = [], []
    with open(vocab_csv) as fin:
        for row in csv.DictReader(fin):
            curie = f"{DRUGBANK}:{row['DrugBank ID']}"
            unii = (row.get("UNII") or "").strip()
            ncit = unii_to_ncit.get(unii, "")
            biolink_type, signal = classify_allergenic_extract(
                row, unii_to_ncit, food_ncit_codes, plant_uniis, extract_markers
            )
            if biolink_type:
                a_rows.append(
                    {
                        "drugbank_curie": curie,
                        "label": row.get("Common name", ""),
                        "unii": f"UNII:{unii}" if unii else "",
                        "ncit": ncit,
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
                b_rows.append(
                    {
                        "drugbank_curie": curie,
                        "label": row.get("Common name", ""),
                        "unii": f"UNII:{unii}" if unii else "",
                        "unii_ncit": ncit,
                    }
                )

    a_rows.sort(key=lambda r: r["drugbank_curie"])
    b_rows.sort(key=lambda r: r["drugbank_curie"])
    _write_csv(
        file_a, ["drugbank_curie", "label", "unii", "ncit", "biolink_type", "future_biolink_type", "signal"], a_rows
    )
    _write_csv(file_b, ["drugbank_curie", "label", "unii", "unii_ncit"], b_rows)
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
    args = parser.parse_args()

    a_rows, b_rows = generate(
        args.vocab_csv, args.unii_records, args.ncit_food_codes, config["drugbank_extract_markers"], FILE_A, FILE_B
    )
    food = sum(1 for r in a_rows if r["biolink_type"] == "biolink:Food")
    cmm = sum(1 for r in a_rows if r["biolink_type"] == COMPLEX_MOLECULAR_MIXTURE)
    print(f"File A {FILE_A.name}: {len(a_rows)} rows ({food} Food + {cmm} ComplexMolecularMixture→ProcessedMaterial)")
    print(f"File B {FILE_B.name}: {len(b_rows)} NCBI-only deferred rows")


if __name__ == "__main__":
    main()
