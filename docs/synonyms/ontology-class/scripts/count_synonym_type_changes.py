"""Measure what synonym_record_types() changes in a finished build's synonym files, without rebuilding them.

A published record's `types` is its clique's ancestor list with `biolink:` stripped and nothing left out, starting with
the clique's own type. So running synonym_record_types() over it reproduces what the current code writes, and comparing
the two counts every record whose `types` change. Nothing else in a record depends on its types, and a conflated
record's types are the union of its members' (conflate_synonyms() no longer filters), so this covers the conflated
files too. See ../README.md.

Each file is streamed and only its `"types": [...]` field is read, so the run takes minutes per GB, not a JSON parse
of every record. Files are processed in parallel.

Usage:
  uv run python docs/synonyms/ontology-class/scripts/count_synonym_type_changes.py <build_url> \\
      AnatomicalEntity BiologicalProcess ... GeneProteinConflated DrugChemicalConflated umls \\
      --subdir synonyms --output docs/synonyms/ontology-class/2026jul22.tsv
"""

import argparse
import collections
import concurrent.futures
import csv
import gzip
import json
import os
import sys
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, REPO_ROOT)

from src.synonyms.record_types import BIOLINK_PREFIX, synonym_record_types  # noqa: E402

TYPES_KEY = b'"types": ['


def count_types_lists(url):
    """Return a Counter of the distinct `types` lists (as JSON text) in the gzipped synonym JSONL at `url`, and the
    number of lines that had none. A JSON string can't hold an unescaped `"`, so the key can't match inside a name."""
    counts = collections.Counter()
    without_types = 0
    with urllib.request.urlopen(url) as response, gzip.GzipFile(fileobj=response) as lines:
        for line in lines:
            start = line.find(TYPES_KEY)
            if start < 0:
                without_types += 1
                continue
            start += len(TYPES_KEY) - 1
            counts[line[start : line.index(b"]", start) + 1].decode()] += 1
    return counts, without_types


def new_types(old_types):
    """What synonym_record_types() writes for a record whose published types are `old_types`."""
    if not old_types:
        return old_types
    return synonym_record_types(BIOLINK_PREFIX + old_types[0], [BIOLINK_PREFIX + t for t in old_types])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("build_url", help="The build directory, e.g. https://stars.renci.org/var/babel/<build>")
    parser.add_argument("names", nargs="+", help="Synonym files to read, without .txt.gz")
    parser.add_argument("--subdir", default="synonyms", help="The directory under build_url that holds them")
    parser.add_argument("--output", required=True, help="TSV to write: one row per file and clique type")
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()

    urls = {name: f"{args.build_url.rstrip('/')}/{args.subdir}/{name}.txt.gz" for name in args.names}
    with concurrent.futures.ProcessPoolExecutor(args.jobs) as pool:
        results = dict(zip(urls, pool.map(count_types_lists, urls.values())))

    rows = []
    for name, (counts, without_types) in results.items():
        if without_types:
            raise RuntimeError(f"{name}: {without_types:,} records have no types field")
        by_type = collections.defaultdict(lambda: [0, 0, 0])
        for types_json, count in counts.items():
            old = json.loads(types_json)
            new = new_types(old)
            row = by_type[old[0] if old else ""]
            row[0] += count
            row[1] += count if new != old else 0
            row[2] += count if "OntologyClass" in new else 0
        for first_type, (records, changed, still_ontology_class) in sorted(by_type.items()):
            rows.append([name, first_type, records, changed, still_ontology_class])

    with open(args.output, "w", newline="") as out:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow(["file", "first_type", "records", "records_changed", "records_still_ontology_class"])
        writer.writerows(rows)

    totals = collections.defaultdict(lambda: [0, 0, 0])
    for name, _, records, changed, still in rows:
        totals[name][0] += records
        totals[name][1] += changed
        totals[name][2] += still
    print("| File | Records | Records whose types change | Still list OntologyClass |")
    print("|------|--------:|---------------------------:|-------------------------:|")
    for name in args.names:
        records, changed, still = totals[name]
        print(f"| {name} | {records:,} | {changed:,} | {still:,} |")
    records, changed, still = (sum(t[i] for t in totals.values()) for i in range(3))
    print(f"| **All** | {records:,} | {changed:,} | {still:,} |")


if __name__ == "__main__":
    main()
