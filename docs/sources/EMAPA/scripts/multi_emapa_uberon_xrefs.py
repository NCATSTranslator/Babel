"""
List every UBERON term that cross-references more than one EMAPA term.

These are the cliques that decided whether `EMAPA` belongs in `anatomy_unique_prefixes`
(config.yaml). Restricting a prefix makes `glom()` refuse any merge whose union would hold two
identifiers sharing it, so each UBERON term below would have had its EMAPA mappings split apart,
and any EMAPA CURIE that lost the resulting contest without an ids-file row of its own would have
been dropped from the compendia entirely. Babel does not restrict EMAPA, so all of these mappings
survive into a single clique -- this file is the evidence an SME needs to confirm that is right.

The `emapa_has_label` column is the signal that separates the two populations: a mapping target
with no `rdfs:label` in EMAPA's own label file is a deprecated or dangling CURIE rather than a live
term, and a UBERON term whose extra mappings are all label-less is not really a 1:n mapping at all.

Usage:
    uv run python docs/sources/EMAPA/scripts/multi_emapa_uberon_xrefs.py \
        [--concord babel_outputs/intermediate/anatomy/concords/UBERON] \
        [--downloads babel_downloads] \
        [--output docs/sources/EMAPA/multi-emapa-xrefs.csv]

The concord comes from a local `anatomy` build (`uv run snakemake -c all anatomy`); the label files
come from the `get_obo_labels` rule, which a pipeline target does not itself depend on (see
docs/AddingNewSources.md).

Writes the CSV to --output and a short summary to stdout.
"""

import argparse
import csv
import os
import sys
from collections import defaultdict

from src.prefixes import EMAPA, UBERON


def read_labels(path):
    """Read a `babel_downloads/<PREFIX>/labels` file into a {CURIE: label} dict."""
    labels = {}
    if not os.path.exists(path):
        return labels
    with open(path) as infile:
        for line in infile:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 2:
                labels[fields[0]] = fields[1]
    return labels


def read_multi_emapa_xrefs(concord_path):
    """Return {UBERON CURIE: sorted [EMAPA CURIEs]} for subjects with more than one EMAPA xref."""
    by_subject = defaultdict(set)
    with open(concord_path) as infile:
        for line in infile:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                continue
            subject, _predicate, obj = fields[0], fields[1], fields[2]
            if subject.startswith(f"{UBERON}:") and obj.startswith(f"{EMAPA}:"):
                by_subject[subject].add(obj)
    return {subject: sorted(objs) for subject, objs in by_subject.items() if len(objs) > 1}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--concord", default="babel_outputs/intermediate/anatomy/concords/UBERON")
    parser.add_argument("--downloads", default="babel_downloads")
    parser.add_argument("--output", default="docs/sources/EMAPA/multi-emapa-xrefs.csv")
    args = parser.parse_args(argv)

    multi = read_multi_emapa_xrefs(args.concord)
    uberon_labels = read_labels(os.path.join(args.downloads, UBERON, "labels"))
    emapa_labels = read_labels(os.path.join(args.downloads, EMAPA, "labels"))
    if not emapa_labels:
        print(f"WARNING: no EMAPA labels found under {args.downloads}; emapa_label will be blank", file=sys.stderr)

    # One row per (UBERON, EMAPA) pair rather than a comma-joined list, so the file survives being
    # opened in a spreadsheet or split on commas.
    rows = []
    for uberon_curie in sorted(multi):
        emapa_curies = multi[uberon_curie]
        labelled = [curie for curie in emapa_curies if curie in emapa_labels]
        for emapa_curie in emapa_curies:
            rows.append(
                {
                    "uberon_curie": uberon_curie,
                    "uberon_label": uberon_labels.get(uberon_curie, ""),
                    "emapa_curie": emapa_curie,
                    "emapa_label": emapa_labels.get(emapa_curie, ""),
                    "emapa_has_label": emapa_curie in emapa_labels,
                    "emapa_terms_for_uberon_term": len(emapa_curies),
                    "labelled_emapa_terms_for_uberon_term": len(labelled),
                }
            )

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", newline="") as outfile:
        # lineterminator="\n": csv defaults to CRLF, which every other committed artifact here
        # would then diff against noisily.
        writer = csv.DictWriter(
            outfile, fieldnames=list(rows[0].keys()) if rows else ["uberon_curie"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    genuine = [u for u, curies in multi.items() if sum(c in emapa_labels for c in curies) > 1]
    print(f"UBERON terms cross-referencing more than one EMAPA term: {len(multi)}")
    print(f"  ...of which more than one mapping target is a labelled (live) EMAPA term: {len(genuine)}")
    print(f"EMAPA CURIEs involved: {sum(len(c) for c in multi.values())}")
    print(
        f"  ...without a label in {args.downloads}/{EMAPA}/labels: "
        f"{sum(1 for curies in multi.values() for c in curies if c not in emapa_labels)}"
    )
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
