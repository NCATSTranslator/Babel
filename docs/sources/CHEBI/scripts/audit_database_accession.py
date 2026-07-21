"""
Audit how many cross-references make_chebi_relations() takes out of ChEBI's database_accession.tsv.

The file identifies each xref's database only by a numeric source_id, and a row's `type` decides
whether `accession_number` is that database's own identifier at all. Both columns therefore have to
be matched, and this script measures what that match actually yields: how many rows are accepted per
prefix, how many rows the wanted sources carry under some *other* type (which must not be read as
accessions), and whether every accepted accession has the shape its database uses.

It imports read_chebi_lookup_ids(), CHEBI_DBX_SOURCE_NAMES, CHEBI_DBX_ACCESSION_TYPE and
CHEBI_DBX_ACCEPTED_STATUSES from the pipeline rather than restating the matching rule, so the audit
cannot drift from what the build does -- see docs/sources/CLAUDE.md.

Usage:
    uv run python docs/sources/CHEBI/scripts/audit_database_accession.py \
        <database_accession.tsv[.gz]> <source.tsv[.gz]> <status.tsv[.gz]>

All three files come from https://ftp.ebi.ac.uk/pub/databases/chebi/flat_files/.

Writes a Markdown report to stdout.
"""

import gzip
import os
import re
import sys
from collections import Counter

from src.createcompendia.chemicals import (
    CHEBI_DBX_ACCEPTED_STATUSES,
    CHEBI_DBX_ACCESSION_TYPE,
    CHEBI_DBX_SOURCE_NAMES,
    read_chebi_lookup_ids,
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


def audit(dbx_filename, prefixes_by_source_id, accepted_status_ids, status_names_by_id):
    """
    Replay make_chebi_relations()' dbx match over the file and count what it accepts and rejects.

    :param dbx_filename: Path to database_accession.tsv[.gz].
    :param prefixes_by_source_id: {source_id -> prefix}.
    :param accepted_status_ids: status_ids the build accepts.
    :param status_names_by_id: {status_id -> name}, for labelling the rejection table.
    :return: (rows parsed, Counter of prefix -> accepted, Counter of (prefix, reason) -> rejected,
              Counter of prefix -> accessions failing their shape)
    """
    rows = 0
    accepted = Counter()
    rejected = Counter()
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
                rejected[(prefix, f"type={x[3]}")] += 1
                continue
            if x[4] not in accepted_status_ids:
                rejected[(prefix, f"status={status_names_by_id.get(x[4], x[4])}")] += 1
                continue
            accepted[prefix] += 1
            shape = ACCESSION_SHAPES.get(prefix)
            if shape and not shape.match(x[2]):
                misshapen[prefix] += 1

    return rows, accepted, rejected, misshapen


def main():
    if len(sys.argv) != 4:
        raise SystemExit(f"Usage: {sys.argv[0]} <database_accession.tsv[.gz]> <source.tsv[.gz]> <status.tsv[.gz]>")
    dbx_filename, source_filename, status_filename = sys.argv[1], sys.argv[2], sys.argv[3]

    source_names_by_id = read_chebi_lookup_ids(source_filename, set(CHEBI_DBX_SOURCE_NAMES))
    prefixes_by_source_id = {sid: CHEBI_DBX_SOURCE_NAMES[name] for sid, name in source_names_by_id.items()}
    accepted_status_ids = set(read_chebi_lookup_ids(status_filename, CHEBI_DBX_ACCEPTED_STATUSES))
    # Every status, not just the accepted ones, so the rejection table can name SUBMITTED rather
    # than printing a bare id.
    status_names_by_id = read_chebi_lookup_ids(status_filename)
    rows, accepted, rejected, misshapen = audit(
        dbx_filename, prefixes_by_source_id, accepted_status_ids, status_names_by_id
    )

    # Basenames, not the local paths they were run from: this report is committed, and a path under
    # someone's scratch directory is not reproducible for the next reader.
    print("# ChEBI database_accession.tsv xref audit\n")
    print(
        f"Source files: `{os.path.basename(dbx_filename)}`, `{os.path.basename(source_filename)}`, "
        f"`{os.path.basename(status_filename)}`, from\n"
        f"<https://ftp.ebi.ac.uk/pub/databases/chebi/flat_files/>.\n"
    )
    print(f"- Data rows parsed: **{rows}**")
    print(f"- Rows accepted by make_chebi_relations(): **{sum(accepted.values())}**\n")
    print(f"Only `{CHEBI_DBX_ACCESSION_TYPE}` rows carry the source's own accession. Rows of other")
    print("types under the same source_id hold a different identifier entirely -- a CAS registry")
    print("number, a citation -- and must not be read as accessions. Of those, only rows whose")
    print(f"curation status is one of {sorted(CHEBI_DBX_ACCEPTED_STATUSES)} are taken; SUBMITTED rows")
    print("are a depositor's unreviewed claim (issue #957).\n")

    print("| Source | source_id | Prefix | Accepted | Rejected | Misshapen accessions |")
    print("| --- | --- | --- | --- | --- | --- |")
    # Keyed by source name, not by prefix: two names could map to one prefix, and inverting on the
    # prefix would then silently report one source's id for the other.
    for name, prefix in sorted(CHEBI_DBX_SOURCE_NAMES.items()):
        source_id = next((sid for sid, n in source_names_by_id.items() if n == name), "?")
        dropped = sum(count for (pfx, _reason), count in rejected.items() if pfx == prefix)
        print(f"| {name} | {source_id} | `{prefix}` | {accepted[prefix]} | {dropped} | {misshapen[prefix]} |")

    print("\n## Rejected rows by reason\n")
    print("| Prefix | Rejected because | Rows |")
    print("| --- | --- | --- |")
    for (prefix, reason), count in sorted(rejected.items()):
        print(f"| `{prefix}` | `{reason}` | {count} |")

    if sum(misshapen.values()):
        print(f"\n**{sum(misshapen.values())} accepted accession(s) do not match their database's shape.**")
        return 1
    print("\nEvery accepted accession matches its database's expected shape.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
