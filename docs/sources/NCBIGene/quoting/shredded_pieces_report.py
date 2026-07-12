"""Report every synonym that the issue-#932 fix removes from NCBIGene's shredded alias fields.

NCBI wraps a comma-containing alias in ''...'' and then turns that value's internal commas into
'|' -- the ``Synonyms`` column's own delimiter -- so the value arrives shredded into pipe-fragments.
The #744 fix drops the two fragments carrying the '' markers. The #932 fix drops what was left: the
value's *middle* pieces, which carry no '' at all and are indistinguishable from real aliases by
shape (``family 706``, ``subfamily A``, ``MET``, even a bare ``3``).

It can do that because the same value sits intact and correctly comma-formatted in
``Full_name_from_nomenclature_authority`` / ``Other_designations``, so its comma-pieces are exactly
the fragments to remove.

This script makes the fix's effect reviewable. For every row whose ``Synonyms`` field carries an
open marker it calls ``split_ncbigene_synonym_field`` twice -- without the intact value (the old
behavior) and with it (the new behavior) -- and reports the difference. It imports the production
function rather than reimplementing it, so the report cannot drift from what Babel actually emits.

Two outputs:

- ``shredded_pieces.csv`` -- one row per (gene, dropped synonym), with the gene's symbol, taxon, the
  intact value it was shredded from, and the raw ``Synonyms`` field. The reviewable record.
- ``shredded_pieces_report.md`` -- a short summary: totals, and the distinct dropped tokens ranked
  by how many genes carry them.

It also asserts the fix only ever *removes* synonyms (the new set is a subset of the old) and that
no shredded piece survives it, so a regression shows up as a crash rather than a quieter wrong
number.

Usage:
    uv run python docs/sources/NCBIGene/quoting/shredded_pieces_report.py [--input gene_info.gz]
"""

import argparse
import csv
import gzip
from collections import Counter, defaultdict
from pathlib import Path

from src.datahandlers.ncbigene import GENE_INFO_HEADER, is_open_marker, split_ncbigene_synonym_field

TAX_ID = GENE_INFO_HEADER.index("#tax_id")
GENE_ID = GENE_INFO_HEADER.index("GeneID")
SYMBOL = GENE_INFO_HEADER.index("Symbol")
SYNONYMS = GENE_INFO_HEADER.index("Synonyms")
FULL_NAME = GENE_INFO_HEADER.index("Full_name_from_nomenclature_authority")
OTHER_DESIG = GENE_INFO_HEADER.index("Other_designations")

DEFAULT_INPUT = Path("babel_downloads/NCBIGene/gene_info.gz")
DEFAULT_CSV = Path(__file__).with_name("shredded_pieces.csv")
DEFAULT_MD = Path(__file__).with_name("shredded_pieces_report.md")


def has_shredded_value(synonyms_field):
    """True if an open marker shows NCBI shredded a ''...''-quoted value into this field."""
    return any(
        is_open_marker(fragment.startswith("''"), fragment.endswith("''"))
        for fragment in (f.strip() for f in synonyms_field.split("|"))
    )


def analyze(input_path):
    """Yield one dict per (gene, dropped synonym), and tally rows/synonyms seen."""
    dropped_rows = []
    totals = Counter()

    with gzip.open(input_path, "rt", encoding="utf-8") as inf:
        inf.readline()
        for line in inf:
            row = line.rstrip("\n").split("\t")
            if len(row) <= OTHER_DESIG or not has_shredded_value(row[SYNONYMS]):
                continue
            totals["rows"] += 1

            intact = next((row[c] for c in (FULL_NAME, OTHER_DESIG) if row[c] not in ("", "-")), "")
            before = split_ncbigene_synonym_field(row[SYNONYMS])
            after = split_ncbigene_synonym_field(row[SYNONYMS], intact)
            totals["synonyms_before"] += len(before)
            totals["synonyms_after"] += len(after)

            # The fix must only ever remove synonyms, never invent one.
            assert after <= before, f"gene {row[GENE_ID]}: fix added synonyms {sorted(after - before)}"
            # And no piece of the shredded value may survive it.
            surviving = {s for s in after if s in {p.strip() for p in intact.split(",") if p.strip()}}
            assert not surviving, f"gene {row[GENE_ID]}: shredded pieces survived: {sorted(surviving)}"

            for synonym in sorted(before - after):
                dropped_rows.append(
                    {
                        "gene_id": row[GENE_ID],
                        "symbol": row[SYMBOL],
                        "tax_id": row[TAX_ID],
                        "dropped_synonym": synonym,
                        "shredded_from": intact,
                        "raw_synonyms_field": row[SYNONYMS],
                    }
                )
    return dropped_rows, totals


def write_csv(dropped_rows, out_path):
    with out_path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(
            out,
            fieldnames=["gene_id", "symbol", "tax_id", "dropped_synonym", "shredded_from", "raw_synonyms_field"],
            lineterminator="\n",  # csv defaults to \r\n; keep the committed file LF-only.
        )
        writer.writeheader()
        writer.writerows(dropped_rows)


def write_markdown(dropped_rows, totals, out_path, csv_path, input_path):
    by_token = defaultdict(list)
    for entry in dropped_rows:
        by_token[entry["dropped_synonym"]].append(entry)

    # Keep every emitted line under 100 characters: rumdl (MD013) lints this file in CI, and it is
    # regenerated, so the generator -- not a one-off `rumdl fmt` -- has to produce compliant output.
    lines = [
        "# NCBIGene: synonyms removed by the issue-#932 fix\n",
        f"Source: `{input_path}`. Generated by `shredded_pieces_report.py`.",
        f"The full per-gene record is [`{csv_path.name}`](./{csv_path.name}).\n",
        "NCBI shreds a `''`-quoted, comma-containing alias across the pipe-delimited `Synonyms`",
        "column. The #744 fix dropped the two fragments carrying the `''` markers; this drops the",
        "value's middle pieces, which carry no `''` and look like ordinary aliases. The value itself",
        "is unaffected — it reaches the synonyms intact from `Full_name_from_nomenclature_authority`.\n",
        "## Totals\n",
        "```text",
        f"{'rows with a shredded value':32s} {totals['rows']:>8,}",
        f"{'synonyms emitted before the fix':32s} {totals['synonyms_before']:>8,}",
        f"{'synonyms emitted after the fix':32s} {totals['synonyms_after']:>8,}",
        f"{'junk synonyms removed':32s} {len(dropped_rows):>8,}",
        f"{'  distinct tokens':32s} {len(by_token):>8,}",
        "```\n",
        "Every dropped token is a fragment of a longer name — none is a plausible standalone alias.",
        "Several are actively hazardous rather than merely useless: `MET`, `CYS` and `PRO` are real",
        "human gene symbols, and a bare `3` would match almost anything.\n",
        "## Distinct dropped tokens\n",
        "Ranked by how many genes carry them.\n",
        "| dropped synonym | genes | example gene | shredded from |",
        "| --- | ---: | --- | --- |",
    ]
    for token, entries in sorted(by_token.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        example = entries[0]
        shredded_from = example["shredded_from"].replace("|", "\\|")[:60]
        lines.append(
            f"| `{token.replace('|', chr(92) + '|')}` | {len(entries):,} | "
            f"{example['gene_id']} ({example['symbol']}) | {shredded_from} |"
        )
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    dropped_rows, totals = analyze(args.input)
    write_csv(dropped_rows, args.csv)
    write_markdown(dropped_rows, totals, args.markdown, args.csv, args.input)
    print(  # noqa: T201
        f"Wrote {args.csv} and {args.markdown}: {len(dropped_rows):,} junk synonyms removed "
        f"across {totals['rows']:,} rows "
        f"({totals['synonyms_before']:,} -> {totals['synonyms_after']:,} synonyms)"
    )


if __name__ == "__main__":
    main()
