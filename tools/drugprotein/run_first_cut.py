#!/usr/bin/env python
"""
First-cut DrugProtein conflation estimate (issue #706), runnable against an existing build.

This is the ad-hoc companion to the ``drugprotein_conflation_report`` Snakemake rule: it calls the
same ``estimate_drugprotein_conflation()`` function, pointed at a finished build's
``babel_outputs`` directory, so you can produce the estimate on the HPC login node without
re-running the pipeline. The three small outputs are written next to each other and are what you
download to your laptop.

Usage (on the HPC, from the repo root, against a finished build):

    uv run python tools/drugprotein/run_first_cut.py \
        --babel-output /path/to/babel_outputs \
        --out-dir ./drugprotein-firstcut

Inputs it reads from --babel-output:
  - duckdb/parquet/filename=*/Edge.parquet and Clique.parquet  (clique membership + labels)
  - intermediate/drugchemical/concords/{RXNORM,UMLS,PUBCHEM_RXNORM}  (the bridge edges)
  - input_data/manual_concords/drugchemical.tsv (in the repo, not babel_outputs)
"""

import argparse
import os

from src.reports.drugprotein_conflation_report import estimate_drugprotein_conflation


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--babel-output", default="babel_outputs", help="Path to a finished babel_outputs directory.")
    parser.add_argument(
        "--manual-concord",
        default="input_data/manual_concords/drugchemical.tsv",
        help="Path to the manual DrugChemical concord (in the repo).",
    )
    parser.add_argument("--out-dir", default="drugprotein-firstcut", help="Where to write the three output files.")
    parser.add_argument("--top-n", type=int, default=200, help="How many of the largest merged cliques to list.")
    args = parser.parse_args()

    parquet_root = os.path.join(args.babel_output, "duckdb", "parquet")
    concords_dir = os.path.join(args.babel_output, "intermediate", "drugchemical", "concords")
    bridge_concords = [
        ("drugchemical/RXNORM", os.path.join(concords_dir, "RXNORM")),
        ("drugchemical/UMLS", os.path.join(concords_dir, "UMLS")),
        ("drugchemical/PUBCHEM_RXNORM", os.path.join(concords_dir, "PUBCHEM_RXNORM")),
    ]

    os.makedirs(args.out_dir, exist_ok=True)
    duckdb_filename = os.path.join(args.out_dir, "drugprotein_firstcut.duckdb")
    if os.path.exists(duckdb_filename):
        os.remove(duckdb_filename)

    estimate_drugprotein_conflation(
        parquet_root=parquet_root,
        bridge_concords=bridge_concords,
        manual_concord=args.manual_concord,
        duckdb_filename=duckdb_filename,
        out_summary_json=os.path.join(args.out_dir, "drugprotein_bridge_summary.json"),
        out_edges_tsv_gz=os.path.join(args.out_dir, "drugprotein_bridge_candidates.tsv.gz"),
        out_top_cliques_csv=os.path.join(args.out_dir, "drugprotein_top_cliques.csv"),
        top_n=args.top_n,
        # A login-node-friendly cap; raise if you have a largemem allocation.
        duckdb_config={"memory_limit": "16G", "threads": 4, "preserve_insertion_order": False},
    )

    print(f"Wrote DrugProtein first-cut estimate to {args.out_dir}/ — download these three files:")
    print("  drugprotein_bridge_summary.json   (counts, per-source breakdown, size histogram)")
    print("  drugprotein_bridge_candidates.tsv.gz  (every protein<->chemical bridge with labels)")
    print("  drugprotein_top_cliques.csv       (largest merged cliques; sanity-check insulin etc.)")


if __name__ == "__main__":
    main()
