"""
Audit how many cross-references make_chebi_relations() takes out of ChEBI's database_accession.tsv.

The SDF half of that function was fixed in #951; this measures the other half. It replays the
production row-matching logic over the real file and reports how many rows it accepts, alongside how
many KEGG COMPOUND / PubChem Compound rows the file actually holds, so the gap between the two is a
number rather than an assertion.

The matching logic is duplicated here rather than imported because it is inlined in
make_chebi_relations() and not separately callable. If that loop is ever extracted, import it here
instead -- see docs/sources/CLAUDE.md on keeping an audit from drifting from the pipeline.

Usage:
    uv run python docs/sources/CHEBI/scripts/audit_database_accession.py <database_accession.tsv[.gz]>

Get the file from
https://ftp.ebi.ac.uk/pub/databases/chebi/flat_files/database_accession.tsv.gz, and its source_id
lookup from source.tsv.gz in the same directory.

Writes a Markdown report to stdout.
"""

import gzip
import sys
from collections import Counter

# source_id values in ChEBI's source.tsv for the two databases this ingest wants.
KEGG_COMPOUND_SOURCE_ID = "45"
PUBCHEM_COMPOUND_SOURCE_ID = "68"


def open_maybe_gzipped(filename):
    """Open a .tsv or .tsv.gz for text reading."""
    return gzip.open(filename, "rt") if filename.endswith(".gz") else open(filename)


def audit(filename):
    """
    Replay make_chebi_relations()' dbx parse over the file and count what it accepts vs. what's there.

    :return: (rows parsed, rows the production match accepts, Counter of source_id -> row count)
    """
    rows = 0
    accepted = 0
    by_source = Counter()

    with open_maybe_gzipped(filename) as inf:
        next(inf, None)  # header
        for line in inf:
            # Verbatim from make_chebi_relations(): split, require >=4 columns, match column 3.
            x = line.strip().split("\t")
            if len(x) < 4:
                continue
            rows += 1
            if x[3] in ("KEGG COMPOUND accession", "Pubchem accession"):
                accepted += 1
            if len(x) >= 6:
                by_source[x[5]] += 1

    return rows, accepted, by_source


def main():
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <database_accession.tsv[.gz]>")
    filename = sys.argv[1]

    rows, accepted, by_source = audit(filename)

    print(f"# ChEBI database_accession.tsv xref audit\n\nSource file: `{filename}`\n")
    print(f"- Data rows parsed: **{rows}**")
    print(f"- Rows accepted by make_chebi_relations(): **{accepted}**\n")
    print("| Source | source_id | Rows in file |")
    print("| --- | --- | --- |")
    print(f"| KEGG COMPOUND | {KEGG_COMPOUND_SOURCE_ID} | {by_source[KEGG_COMPOUND_SOURCE_ID]} |")
    print(f"| PubChem Compound | {PUBCHEM_COMPOUND_SOURCE_ID} | {by_source[PUBCHEM_COMPOUND_SOURCE_ID]} |")

    if accepted == 0:
        print(
            "\n**No rows matched.** Column 3 is `type` (MANUAL_X_REF / CITATION / CAS / "
            "REGISTRY_NUMBER); the source name lives in the numeric `source_id` column instead. "
            "See docs/sources/CHEBI/README.md."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
