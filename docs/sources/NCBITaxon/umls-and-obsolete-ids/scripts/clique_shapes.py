"""Summarize the shape of two OrganismTaxon builds' cliques, and how NCBITaxon and UMLS labels agree.

Checks the claims docs/sources/NCBITaxon/README.md makes about a build pair: how many cliques hold only a
UMLS identifier, that no clique holds two identifiers with the same prefix (NCBITaxon, MESH and UMLS are
all unique prefixes in glom()), the largest clique, and, in the AFTER build, how often a clique's NCBITaxon
and UMLS labels agree. Writes clique-shapes.md.

Usage (from the repository root):

    PYTHONPATH=. uv run python docs/sources/NCBITaxon/umls-and-obsolete-ids/scripts/clique_shapes.py \\
        BEFORE/OrganismTaxon.txt "before label" AFTER/OrganismTaxon.txt "after label" \\
        babel_downloads/NCBITaxon/synonyms docs/sources/NCBITaxon/umls-and-obsolete-ids
"""

import json
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

from src.prefixes import NCBITAXON, UMLS


def read_shapes(compendium):
    """Return (shape counts, [(NCBITaxon CURIE, its label, UMLS label)] for cliques holding both)."""
    shapes = {"cliques": 0, "umls_only": 0, "duplicate_prefix": 0, "largest": 0}
    pairs = []
    with open(compendium) as inf:
        for line in inf:
            identifiers = json.loads(line)["identifiers"]
            prefixes = [x["i"].split(":")[0] for x in identifiers]
            shapes["cliques"] += 1
            shapes["largest"] = max(shapes["largest"], len(identifiers))
            shapes["duplicate_prefix"] += len(prefixes) != len(set(prefixes))
            shapes["umls_only"] += prefixes == [UMLS]
            ncbi = [x for x in identifiers if x["i"].startswith(f"{NCBITAXON}:")]
            umls = [x for x in identifiers if x["i"].startswith(f"{UMLS}:")]
            if ncbi and umls:
                pairs.append((ncbi[0]["i"], ncbi[0].get("l", ""), umls[0].get("l", "")))
    return shapes, pairs


def main(before_fn, before_label, after_fn, after_label, ncbitaxon_synonyms, outdir):
    before, _ = read_shapes(before_fn)
    after, pairs = read_shapes(after_fn)

    # A clique's NCBITaxon label can carry a common name ("Armoracia rusticana (horseradish)"), so compare
    # the UMLS label against NCBI's own names too.
    differing = [(taxon, umls_label) for taxon, ncbi_label, umls_label in pairs if ncbi_label != umls_label]
    wanted = {taxon for taxon, _ in differing}
    synonyms = defaultdict(set)
    with open(ncbitaxon_synonyms) as inf:
        for line in inf:
            row = line.rstrip("\n").split("\t")
            if row[0] in wanted:
                synonyms[row[0]].add(row[-1])
    among_synonyms = sum(1 for taxon, umls_label in differing if umls_label in synonyms[taxon])

    lines = [
        "# OrganismTaxon clique shapes",
        "",
        f"- Before: {before_label}",
        f"- After: {after_label}",
        "",
        "| | before | after |",
        "|---|---|---|",
        f"| cliques | {before['cliques']:,} | {after['cliques']:,} |",
        f"| cliques holding only a UMLS identifier | {before['umls_only']:,} | {after['umls_only']:,} |",
        f"| cliques with two identifiers of one prefix | {before['duplicate_prefix']:,} "
        f"| {after['duplicate_prefix']:,} |",
        f"| largest clique | {before['largest']} | {after['largest']} |",
        "",
        # Wrapped to the 100 columns rumdl (MD013) allows.
        textwrap.fill(
            f"In the after build, {len(pairs):,} cliques hold both an NCBITaxon and a UMLS identifier. "
            f"{len(pairs) - len(differing):,} have the same label on both. Of the other {len(differing):,}, "
            f"{among_synonyms:,} have the UMLS label among NCBITaxon's own synonyms.",
            width=100,
            break_on_hyphens=False,
        ),
    ]
    (Path(outdir) / "clique-shapes.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:7])
