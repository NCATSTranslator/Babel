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

# A source_id alone does not identify an accession: rows are also tagged with a `type`, and both
# sources below carry CAS-typed rows whose accession_number is a CAS registry number rather than a
# KEGG or PubChem ID (e.g. `17 7 498-15-7 CAS 1 45`). Only MANUAL_X_REF rows hold the source's own
# accession, so any fix must filter on both columns.
ACCESSION_TYPE = "MANUAL_X_REF"


def open_maybe_gzipped(filename):
    """Open a .tsv or .tsv.gz for text reading."""
    return gzip.open(filename, "rt") if filename.endswith(".gz") else open(filename)


def audit(filename):
    """
    Replay make_chebi_relations()' dbx parse over the file and count what it accepts vs. what's there.

    :return: (rows parsed, rows the production match accepts, Counter of (source_id, type) -> count)
    """
    rows = 0
    accepted = 0
    by_source_and_type = Counter()

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
                by_source_and_type[(x[5], x[3])] += 1

    return rows, accepted, by_source_and_type


def main():
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <database_accession.tsv[.gz]>")
    filename = sys.argv[1]

    rows, accepted, by_source_and_type = audit(filename)

    print(f"# ChEBI database_accession.tsv xref audit\n\nSource file: `{filename}`\n")
    print(f"- Data rows parsed: **{rows}**")
    print(f"- Rows accepted by make_chebi_relations(): **{accepted}**\n")
    print(f"Recoverable rows are those tagged `{ACCESSION_TYPE}`; the rest carry a different")
    print("identifier under the same source_id and must not be read as an accession.\n")
    print(f"| Source | source_id | `{ACCESSION_TYPE}` rows | Rows of other types |")
    print("| --- | --- | --- | --- |")
    for name, source_id in (
        ("KEGG COMPOUND", KEGG_COMPOUND_SOURCE_ID),
        ("PubChem Compound", PUBCHEM_COMPOUND_SOURCE_ID),
    ):
        usable = by_source_and_type[(source_id, ACCESSION_TYPE)]
        other = sum(count for (sid, _type), count in by_source_and_type.items() if sid == source_id) - usable
        print(f"| {name} | {source_id} | {usable} | {other} |")

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
