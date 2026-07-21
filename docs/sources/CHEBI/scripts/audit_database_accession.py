"""
Audit how many cross-references make_chebi_relations() takes out of ChEBI's database_accession.tsv.

The file identifies each xref's database only by a numeric source_id, and a row's `type` decides
whether `accession_number` is that database's own identifier at all. Both columns therefore have to
be matched, and this script measures what that match actually yields: how many rows are accepted per
prefix, how many rows the wanted sources carry under some *other* type (which must not be read as
accessions), and whether every accepted accession has the shape its database uses.

It imports read_chebi_dbx_source_ids(), CHEBI_DBX_SOURCE_NAMES and CHEBI_DBX_ACCESSION_TYPE from the
pipeline rather than restating the matching rule, so the audit cannot drift from what the build does
-- see docs/sources/CLAUDE.md.

Usage:
    uv run python docs/sources/CHEBI/scripts/audit_database_accession.py \
        <database_accession.tsv[.gz]> <source.tsv[.gz]>

Both files come from https://ftp.ebi.ac.uk/pub/databases/chebi/flat_files/.

Writes a Markdown report to stdout.
"""

import gzip
import re
import sys
from collections import Counter

from src.createcompendia.chemicals import (
    CHEBI_DBX_ACCESSION_TYPE,
    CHEBI_DBX_SOURCE_NAMES,
    read_chebi_dbx_source_ids,
)
from src.prefixes import KEGGCOMPOUND, PUBCHEMCOMPOUND

# The shape each database's own accessions take, so a mismatched column shows up as a shape error
# rather than as a plausible-looking CURIE. KEGG COMPOUND accessions are C-prefixed numbers; PubChem
# compound IDs are bare integers.
ACCESSION_SHAPES = {
    KEGGCOMPOUND: re.compile(r"^C\d+$"),
    PUBCHEMCOMPOUND: re.compile(r"^\d+$"),
}


def open_maybe_gzipped(filename):
    """Open a .tsv or .tsv.gz for text reading."""
    return gzip.open(filename, "rt") if filename.endswith(".gz") else open(filename)


def audit(dbx_filename, prefixes_by_source_id):
    """
    Replay make_chebi_relations()' dbx match over the file and count what it accepts and rejects.

    :param dbx_filename: Path to database_accession.tsv[.gz].
    :param prefixes_by_source_id: {source_id -> prefix}, from read_chebi_dbx_source_ids().
    :return: (rows parsed, Counter of prefix -> accepted, Counter of (prefix, type) -> rejected,
              Counter of prefix -> accessions failing their shape)
    """
    rows = 0
    accepted = Counter()
    rejected_by_type = Counter()
    misshapen = Counter()

    with open_maybe_gzipped(dbx_filename) as inf:
        next(inf, None)  # header
        for line in inf:
            # Verbatim from make_chebi_relations(): six columns, matching type and source_id.
            x = line.rstrip("\n").split("\t")
            if len(x) < 6:
                continue
            rows += 1
            prefix = prefixes_by_source_id.get(x[5])
            if prefix is None:
                continue
            if x[3] != CHEBI_DBX_ACCESSION_TYPE:
                rejected_by_type[(prefix, x[3])] += 1
                continue
            accepted[prefix] += 1
            shape = ACCESSION_SHAPES.get(prefix)
            if shape and not shape.match(x[2]):
                misshapen[prefix] += 1

    return rows, accepted, rejected_by_type, misshapen


def main():
    if len(sys.argv) != 3:
        raise SystemExit(f"Usage: {sys.argv[0]} <database_accession.tsv[.gz]> <source.tsv[.gz]>")
    dbx_filename, source_filename = sys.argv[1], sys.argv[2]

    prefixes_by_source_id = read_chebi_dbx_source_ids(source_filename)
    rows, accepted, rejected_by_type, misshapen = audit(dbx_filename, prefixes_by_source_id)

    print(f"# ChEBI database_accession.tsv xref audit\n\nSource file: `{dbx_filename}`\n")
    print(f"- Data rows parsed: **{rows}**")
    print(f"- Rows accepted by make_chebi_relations(): **{sum(accepted.values())}**\n")
    print(f"Only `{CHEBI_DBX_ACCESSION_TYPE}` rows carry the source's own accession. Rows of other")
    print("types under the same source_id hold a different identifier entirely -- a CAS registry")
    print("number, a citation -- and must not be read as accessions.\n")

    print("| Source | source_id | Prefix | Accepted | Rejected on `type` | Misshapen accessions |")
    print("| --- | --- | --- | --- | --- | --- |")
    source_ids_by_prefix = {prefix: sid for sid, prefix in prefixes_by_source_id.items()}
    for name, prefix in sorted(CHEBI_DBX_SOURCE_NAMES.items()):
        rejected = sum(count for (pfx, _type), count in rejected_by_type.items() if pfx == prefix)
        print(
            f"| {name} | {source_ids_by_prefix.get(prefix, '?')} | `{prefix}` | "
            f"{accepted[prefix]} | {rejected} | {misshapen[prefix]} |"
        )

    print("\n## Rejected rows by type\n")
    print("| Prefix | Type | Rows |")
    print("| --- | --- | --- |")
    for (prefix, row_type), count in sorted(rejected_by_type.items()):
        print(f"| `{prefix}` | `{row_type}` | {count} |")

    if sum(misshapen.values()):
        print(f"\n**{sum(misshapen.values())} accepted accession(s) do not match their database's shape.**")
        return 1
    print("\nEvery accepted accession matches its database's expected shape.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
