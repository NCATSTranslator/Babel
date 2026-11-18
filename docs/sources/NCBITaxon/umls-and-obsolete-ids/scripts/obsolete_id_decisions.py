"""Tabulate what update_obsolete_ncbitaxon_ids() decides for every taxon concord row with an obsolete NCBITaxon ID.

Runs the pipeline's own function over the raw taxon concords, so the counts are exactly what a build
records under `obsolete_ncbitaxon` in the concord metadata. Writes:

- obsolete-id-decisions.md: the counts per concord and decision, plus a sample of the rows dropped because
  the merge target is broader or because several records competed for it.
- obsolete-id-decisions.csv: every one of those dropped rows, with labels.

Usage (from the repository root; the inputs are the taxon_update_obsolete_ncbitaxon_ids rule's inputs):

    PYTHONPATH=. uv run python docs/sources/NCBITaxon/umls-and-obsolete-ids/scripts/obsolete_id_decisions.py \\
        INTERMEDIATE/taxon/raw_concords/UMLS INTERMEDIATE/taxon/raw_concords/NCBI_MESH \\
        babel_downloads/NCBITaxon/taxdump.tar babel_downloads/MESH/labels babel_downloads/UMLS/labels \\
        babel_downloads/UMLS/synonyms "description of the inputs" docs/sources/NCBITaxon/umls-and-obsolete-ids
"""

import csv
import sys
import tempfile
import textwrap
from collections import Counter
from pathlib import Path

from src.createcompendia.taxon import (
    DROPPED_DELETED,
    DROPPED_MERGED_ALREADY_LINKED,
    DROPPED_MERGED_AMBIGUOUS,
    DROPPED_MERGED_INTO_BROADER_TAXON,
    DROPPED_MERGED_SUPERSEDED_BY_DIRECT,
    REMAPPED_MERGED,
    update_obsolete_ncbitaxon_ids,
)
from src.datahandlers.ncbitaxon import read_taxon_names

DECISIONS = [
    REMAPPED_MERGED,
    DROPPED_MERGED_ALREADY_LINKED,
    DROPPED_MERGED_INTO_BROADER_TAXON,
    DROPPED_MERGED_SUPERSEDED_BY_DIRECT,
    DROPPED_MERGED_AMBIGUOUS,
    DROPPED_DELETED,
]
LISTED = [DROPPED_MERGED_INTO_BROADER_TAXON, DROPPED_MERGED_AMBIGUOUS]
SAMPLE_SIZE = 8


def read_labels(label_files, curies):
    labels = {}
    for filename in label_files:
        with open(filename) as inf:
            for line in inf:
                curie, label = line.rstrip("\n").split("\t", 1)
                if curie in curies:
                    labels.setdefault(curie, label)
    return labels


def main(umls_raw, ncbi_mesh_raw, taxdump, mesh_labels, umls_labels, umls_synonyms, inputs_description, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        _, decisions = update_obsolete_ncbitaxon_ids(
            {"UMLS": (umls_raw, f"{tmp}/UMLS"), "NCBI_MESH": (ncbi_mesh_raw, f"{tmp}/NCBI_MESH")},
            taxdump,
            [mesh_labels, umls_labels],
            [umls_synonyms],
        )

    listed = sorted(
        (d for d in decisions if d["decision"] in LISTED),
        key=lambda d: (d["decision"], d["current"], d["identifier"]),
    )
    labels = read_labels([mesh_labels, umls_labels], {d["identifier"] for d in listed})
    taxon_names = read_taxon_names(taxdump, {d["current"] for d in listed})

    def scientific_name(taxon):
        return next((n for n, classes in taxon_names.get(taxon, {}).items() if "scientific name" in classes), "")

    rows = [
        {
            "decision": d["decision"],
            "concord": d["concord"],
            "identifier": d["identifier"],
            "label": labels.get(d["identifier"], ""),
            "obsolete": d["obsolete"],
            "current": d["current"],
            "current_scientific_name": scientific_name(d["current"]),
        }
        for d in listed
    ]
    with open(outdir / "obsolete-id-decisions.csv", "w", newline="") as outf:
        writer = csv.DictWriter(outf, fieldnames=list(rows[0].keys()) if rows else ["decision"])
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter((d["concord"], d["decision"]) for d in decisions)
    concords = sorted({d["concord"] for d in decisions})
    lines = [
        "# What happens to obsolete NCBITaxon IDs in the taxon concords",
        "",
        # Wrapped to the 100 columns rumdl (MD013) allows.
        textwrap.fill(f"Inputs: {inputs_description}.", width=100),
        "",
        "Counts of rows per decision; see `update_obsolete_ncbitaxon_ids()` and",
        "`resolve_obsolete_ncbitaxon_ids()` in `src/createcompendia/taxon.py` for what each one means.",
        "",
        "| decision | " + " | ".join(concords) + " |",
        "|---|" + "---|" * len(concords),
    ]
    lines += [
        f"| {decision} | " + " | ".join(f"{counts[(c, decision)]:,}" for c in concords) + " |" for decision in DECISIONS
    ]
    for decision in LISTED:
        selected = [row for row in rows if row["decision"] == decision]
        # Spread the sample evenly over the rows, which are sorted by current taxon, rather than taking the first few.
        step = max(1, len(selected) // SAMPLE_SIZE)
        sample = selected[::step][:SAMPLE_SIZE]
        lines += [
            "",
            f"## {decision}",
            "",
            textwrap.fill(
                f"{len(sample)} of {len(selected)}, spread evenly over them in order of current taxon "
                "(all of them are in `obsolete-id-decisions.csv`):",
                width=100,
            ),
            "",
            "| identifier | obsolete | current |",
            "|---|---|---|",
        ]
        lines += [
            f"| {row['identifier']} {row['label']} | {row['obsolete']} "
            f"| {row['current']} {row['current_scientific_name']} |"
            for row in sample
        ]
    (outdir / "obsolete-id-decisions.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:9])
