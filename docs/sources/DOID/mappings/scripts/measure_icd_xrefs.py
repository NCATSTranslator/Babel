"""Measure what DOID's ICD xrefs do to disease clique sizes.

Prints the three-scenario table quoted in ``docs/sources/DOID/mappings.md``: the disease cliques
as they were built, with `remove_overused_xrefs` applied to DOID instead, and with the ICD
prefixes excluded (what the pipeline now does).

Each scenario rebuilds the DOID concord through the production
``build_disease_doid_relationships()`` -- toggling the production
``DOID_EXCLUDED_XREF_PREFIXES`` -- and then replays the production
``compute_cliques_for_impact_report()`` over a finished build's ``intermediate/disease/``. Nothing
here reimplements the pipeline, so the measurement cannot drift from it (see docs/sources/CLAUDE.md,
"Replaying a pipeline function beats rebuilding to measure a change"). A replay only sees the
cliques the build already produced, so it cannot show cliques that move *between* compendia --
confirm with ``babel-clique-diff`` on a real build before trusting the totals.

The companion artifacts are not written here: both CSVs come from the ``babel-overused-xrefs``
tool (docs/tools/OverusedXrefs.md). Regenerate everything together::

    # every row the ICD exclusion drops -- must run against a PRE-exclusion concord
    uv run babel-overused-xrefs --concord <concord built with DOID_EXCLUDED_XREF_PREFIXES=[]> \
        --min-subjects 1 --target-prefixes ICD10,ICD9,ICD0,ICD11 \
        --out docs/sources/DOID/mappings/icd-targets.csv --mrconso babel_downloads/UMLS/MRCONSO.RRF
    # what overuse remains afterwards
    uv run babel-overused-xrefs --concord babel_outputs/intermediate/disease/concords/DOID \
        --out docs/sources/DOID/mappings/overused-targets.csv --mrconso babel_downloads/UMLS/MRCONSO.RRF
    uv run python docs/sources/DOID/mappings/scripts/measure_icd_xrefs.py

Usage (needs a disease intermediate set *and* babel_downloads/DOID/doid.json):

    uv run python docs/sources/DOID/mappings/scripts/measure_icd_xrefs.py \
        [--intermediate-root babel_outputs/intermediate] [--doid-json babel_downloads/DOID/doid.json]
"""

import argparse
import collections
import glob
import os
import tempfile

import src.createcompendia.diseasephenotype as dp

# Cliques probed individually in the report. Each is the preferred identifier of a clique that one
# ICD-10 code inflated; the label is MONDO's.
PROBES = {
    "MONDO:0019064": "hereditary spastic paraplegia",
    "MONDO:0000912": "autosomal recessive nonsyndromic hearing loss 5",
    "MONDO:0000910": "retinitis pigmentosa 6",
}


def build_concord(doid_json, outdir, excluded_prefixes):
    """Build one DOID concord through the production path with a given exclusion list."""
    outfile = os.path.join(outdir, "DOID")
    saved = dp.DOID_EXCLUDED_XREF_PREFIXES
    try:
        dp.DOID_EXCLUDED_XREF_PREFIXES = excluded_prefixes
        dp.build_disease_doid_relationships(doid_json, outfile, os.path.join(outdir, "metadata-DOID.yaml"))
    finally:
        dp.DOID_EXCLUDED_XREF_PREFIXES = saved
    return outfile


def clique_stats(concords, ids, overuse_filter_doid=False):
    """Replay the production clique builder and summarize the clique-size distribution."""
    saved = dp.OVERUSE_FILTERED_CONCORDS
    try:
        if overuse_filter_doid:
            dp.OVERUSE_FILTERED_CONCORDS = saved | {"DOID"}
        dicts, _types = dp.compute_cliques_for_impact_report(concords, ids)
    finally:
        dp.OVERUSE_FILTERED_CONCORDS = saved
    sizes = sorted((len(c) for c in {frozenset(v) for v in dicts.values()}), reverse=True)
    stats = {
        "identifiers": len(dicts),
        "cliques": len(sizes),
        "largest clique": sizes[0],
        "cliques >= 50 ids": len([s for s in sizes if s >= 50]),
        "cliques >= 20 ids": len([s for s in sizes if s >= 20]),
    }
    stats.update({f"{label} ({probe})": len(dicts.get(probe, {probe})) for probe, label in PROBES.items()})
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intermediate-root", default="babel_outputs/intermediate")
    parser.add_argument("--doid-json", default="babel_downloads/DOID/doid.json")
    args = parser.parse_args()

    root = os.path.join(args.intermediate_root, "disease")
    concords = sorted(p for p in glob.glob(f"{root}/concords/*") if not os.path.basename(p).startswith("metadata"))
    ids = sorted(glob.glob(f"{root}/ids/*"))
    built_concord = os.path.join(root, "concords", "DOID")

    with tempfile.TemporaryDirectory() as tmp:
        unfiltered_dir, filtered_dir = os.path.join(tmp, "all"), os.path.join(tmp, "no-icd")
        os.makedirs(unfiltered_dir)
        os.makedirs(filtered_dir)
        unfiltered = build_concord(args.doid_json, unfiltered_dir, [])
        filtered = build_concord(args.doid_json, filtered_dir, dp.DOID_EXCLUDED_XREF_PREFIXES)

        dropped = collections.Counter()
        with open(unfiltered) as inf:
            for line in inf:
                prefix = line.rstrip("\n").split("\t")[-1].split(":", 1)[0]
                if prefix.upper().startswith("ICD"):
                    dropped[prefix] += 1
        total = sum(1 for _ in open(unfiltered))
        print(f"DOID concord: {total} rows, {sum(dropped.values())} dropped as ICD {dict(dropped.most_common())}\n")

        # The intermediate on disk may predate the current doid.json; say so rather than silently
        # comparing against a concord the rest of the numbers don't come from.
        if os.path.exists(built_concord) and sum(1 for _ in open(built_concord)) not in (
            total,
            total - sum(dropped.values()),
        ):
            print(f"NOTE: {built_concord} matches neither rebuild; doid.json has moved since it was built.\n")

        def with_doid(path):
            return [path if c == built_concord else c for c in concords]

        scenarios = {
            "as built": clique_stats(with_doid(unfiltered), ids),
            "overuse-filtered": clique_stats(with_doid(unfiltered), ids, overuse_filter_doid=True),
            "ICD excluded": clique_stats(with_doid(filtered), ids),
        }

    keys = list(next(iter(scenarios.values())))
    width = max(len(k) for k in keys)
    print(f"{'':{width}}" + "".join(f"{name:>20}" for name in scenarios))
    for key in keys:
        print(f"{key:{width}}" + "".join(f"{s[key]:>20,}" for s in scenarios.values()))


if __name__ == "__main__":
    main()
