"""List the UBERON SNOMED xrefs whose UMLS join needs a person's review, after anatomy_badxrefs.txt.

An UBERON SNOMED xref joins the UBERON term to whichever UMLS concept holds that SNOMED code. The production
check, anatomy.find_uberon_snomed_xrefs_to_review(), flags the two shapes in which that merges more than the
UBERON term means: a UMLS concept that lumps several SNOMED codes, and an UBERON term whose SNOMED xrefs reach
several UMLS concepts. This script writes every xref it flags that input_data/anatomy_badxrefs.txt does not
drop, with names, so the list can be reviewed; tests/pipeline/test_uberon_umls_joins.py fails on a flagged
xref missing from it. Regenerate it only after judging the new rows (and dropping the wrong ones).

Usage (from the repository root, after `uv run snakemake anatomy`):

    uv run python docs/sources/UBERON/umls-joins/scripts/snomed_xref_review.py

Writes docs/sources/UBERON/umls-joins/snomed-xref-review.csv and prints a summary. The summary also measures
the xrefs to SNOMED "structure" concepts listed in sctid-structure-entire.csv (from sctid_structure_entire.py):
how many of the UMLS concepts they reach are also reached by another of the same UBERON term's xrefs, and how
many also carry an FMA, MeSH or NCIt code -- i.e. are UMLS's main concept for the thing, not a SNOMED-only one.
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from src.babel_utils import read_badxrefs
from src.createcompendia.anatomy import ANATOMY_BAD_XREFS, find_uberon_snomed_xrefs_to_review
from src.prefixes import FMA, MESH, NCIT, SNOMEDCT, UMLS

REPO = Path(__file__).resolve().parents[5]


def read_cuis_by_snomed(umls_concord, bad_pairs):
    """Return {SNOMEDCT CURIE: {UMLS CURIE}} from the anatomy UMLS concord, without the dropped pairs."""
    cuis = defaultdict(set)
    with open(umls_concord) as inf:
        for line in inf:
            cui, _, target = line.rstrip("\n").split("\t")
            if target.startswith(f"{SNOMEDCT}:") and frozenset((cui, target)) not in bad_pairs:
                cuis[target].add(cui)
    return cuis


def summarize_structure_xrefs(structure_csv, uberon_concord, umls_concord, bad_pairs):
    """Print how the UMLS concepts that UBERON's xrefs to SNOMED structure concepts reach are otherwise joined."""
    codes_of = defaultdict(set)
    with open(umls_concord) as inf:
        for line in inf:
            cui, _, target = line.rstrip("\n").split("\t")
            if frozenset((cui, target)) not in bad_pairs:
                codes_of[cui].add(target)
    cuis_of = defaultdict(set)
    for cui, codes in codes_of.items():
        for code in codes:
            cuis_of[code].add(cui)
    xrefs = defaultdict(set)
    with open(uberon_concord) as inf:
        for line in inf:
            uberon, _, target = line.rstrip("\n").split("\t")
            if frozenset((uberon, target)) not in bad_pairs:
                xrefs[uberon].add(target)
    joins, also_joined, main_concept = 0, 0, 0
    with open(structure_csv) as inf:
        for row in csv.DictReader(inf):
            uberon, snomed = row["uberon_id"], f"{SNOMEDCT}:{row['structure_sctid']}"
            if frozenset((uberon, snomed)) in bad_pairs:
                continue
            for cui in cuis_of[snomed]:
                joins += 1
                others = xrefs[uberon] - {snomed}
                also_joined += cui in others or bool(others & codes_of[cui])
                main_concept += any(c.split(":", 1)[0] in (FMA, MESH, NCIT) for c in codes_of[cui])
    print(f"xrefs to SNOMED structure concepts join {joins} (UBERON term, UMLS concept) pairs:")
    print(f"  {also_joined} also joined by another xref of the same UBERON term")
    print(f"  {main_concept} to a UMLS concept that also carries an FMA, MeSH or NCIt code")


def read_names(mrconso, snomed_codes, cuis):
    """Return ({SNOMED code: fully specified name}, {CUI: preferred English name}) from MRCONSO."""
    fsn, cui_name = {}, {}
    with open(mrconso) as inf:
        for line in inf:
            x = line.split("|")
            if x[11] == "SNOMEDCT_US" and x[12] == "FN" and x[13] in snomed_codes and x[16] == "N":
                fsn[x[13]] = x[14]
            if x[0] in cuis and x[1] == "ENG" and x[2] == "P" and x[4] == "PF" and x[6] == "Y":
                cui_name[x[0]] = x[14]
    return fsn, cui_name


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--uberon-concord", default=REPO / "babel_outputs/intermediate/anatomy/concords/UBERON")
    parser.add_argument("--umls-concord", default=REPO / "babel_outputs/intermediate/anatomy/concords/UMLS")
    parser.add_argument("--labels", default=REPO / "babel_downloads/UBERON/labels")
    parser.add_argument("--mrconso", default=REPO / "babel_downloads/UMLS/MRCONSO.RRF")
    parser.add_argument("--out", default=REPO / "docs/sources/UBERON/umls-joins/snomed-xref-review.csv")
    parser.add_argument("--structure-csv", default=REPO / "docs/sources/UBERON/umls-joins/sctid-structure-entire.csv")
    args = parser.parse_args()

    bad_pairs = {frozenset(pair) for pair in read_badxrefs(ANATOMY_BAD_XREFS)}
    flagged = find_uberon_snomed_xrefs_to_review(args.uberon_concord, args.umls_concord, bad_pairs)
    cuis_by_snomed = read_cuis_by_snomed(args.umls_concord, bad_pairs)
    with open(args.labels) as inf:
        labels = dict(line.rstrip("\n").split("\t", 1) for line in inf if "\t" in line)
    snomed_codes = {snomed.split(":", 1)[1] for _, snomed in flagged}
    cuis = {cui.split(":", 1)[1] for _, snomed in flagged for cui in cuis_by_snomed[snomed]}
    fsn, cui_name = read_names(args.mrconso, snomed_codes, cuis)

    with open(args.out, "w", newline="") as outf:
        w = csv.writer(outf)
        w.writerow(["uberon_id", "uberon_label", "snomed_id", "snomed_fsn", "umls_ids", "umls_names", "reasons"])
        for uberon, snomed in sorted(flagged):
            cui_curies = sorted(cuis_by_snomed[snomed])
            w.writerow(
                [
                    uberon,
                    labels.get(uberon, ""),
                    snomed,
                    fsn.get(snomed.split(":", 1)[1], ""),
                    ";".join(cui_curies),
                    ";".join(cui_name.get(c.removeprefix(f"{UMLS}:"), "") for c in cui_curies),
                    ";".join(sorted(flagged[(uberon, snomed)])),
                ]
            )

    reasons = Counter(r for rs in flagged.values() for r in rs)
    print(f"{len(flagged)} UBERON SNOMED xrefs on {len({u for u, _ in flagged})} UBERON terms flagged, after")
    print(f"the {len(bad_pairs)} pairs in {ANATOMY_BAD_XREFS}; written to {args.out}")
    for reason, n in reasons.most_common():
        print(f"  {reason}: {n}")
    summarize_structure_xrefs(args.structure_csv, args.uberon_concord, args.umls_concord, bad_pairs)


if __name__ == "__main__":
    main()
