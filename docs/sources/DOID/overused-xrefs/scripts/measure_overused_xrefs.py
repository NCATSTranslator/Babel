"""Measure what DOID's overused xref targets do to disease clique sizes.

Prints the clique statistics quoted in ``docs/sources/DOID/overused-xrefs.md`` with and without
``"DOID"`` in ``OVERUSE_FILTERED_CONCORDS``. The numbers come from replaying the production
``compute_cliques_for_impact_report()`` over a finished build's ``intermediate/disease/`` rather
than rebuilding, so they cannot drift from what the pipeline does (see docs/sources/CLAUDE.md,
"Replaying a pipeline function beats rebuilding to measure a change"). A replay only sees the
cliques the build already produced, so it cannot show cliques that move *between* compendia --
confirm with ``babel-clique-diff`` on a real build before trusting the totals.

The companion artifact, ``overused-targets.csv``, is not written here: it is a general concord
audit, so it comes from the ``babel-overused-xrefs`` tool (docs/tools/OverusedXrefs.md).
Regenerate both together::

    uv run babel-overused-xrefs \
        --concord babel_outputs/intermediate/disease/concords/DOID \
        --out docs/sources/DOID/overused-xrefs/overused-targets.csv \
        --mrconso babel_downloads/UMLS/MRCONSO.RRF
    uv run python docs/sources/DOID/overused-xrefs/scripts/measure_overused_xrefs.py

Usage (needs a local or downloaded disease intermediate set):

    uv run python docs/sources/DOID/overused-xrefs/scripts/measure_overused_xrefs.py \
        [--intermediate-root babel_outputs/intermediate]
"""

import argparse
import collections
import glob
import os

import src.createcompendia.diseasephenotype as dp
from src.model.concords import find_overused_xref_targets

# Cliques probed individually in the report. Each is the preferred identifier of a clique that
# one ICD-10 code inflated; the label is MONDO's.
PROBES = {
    "MONDO:0019064": "hereditary spastic paraplegia",
    "MONDO:0000912": "autosomal recessive nonsyndromic hearing loss 5",
    "MONDO:0000910": "retinitis pigmentosa 6",
}


def clique_stats(concords, ids):
    """Replay the production clique builder and summarize the clique-size distribution."""
    dicts, _types = dp.compute_cliques_for_impact_report(concords, ids)
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
    args = parser.parse_args()

    root = os.path.join(args.intermediate_root, "disease")
    concords = sorted(p for p in glob.glob(f"{root}/concords/*") if not os.path.basename(p).startswith("metadata"))
    ids = sorted(glob.glob(f"{root}/ids/*"))

    # Same detection babel-overused-xrefs writes to CSV, and the same rule remove_overused_xrefs
    # applies -- reported here only as the headline the clique numbers below explain.
    overused = find_overused_xref_targets(os.path.join(root, "concords", "DOID"))
    prefixes = collections.Counter(o.prefix for o in overused)
    print(f"{len(overused)} overused targets in DOID's concord, by prefix {dict(prefixes.most_common(6))}\n")

    # OVERUSE_FILTERED_CONCORDS is read at glom time, so toggling it here exercises exactly the
    # production code path.
    dp.OVERUSE_FILTERED_CONCORDS = dp.OVERUSE_FILTERED_CONCORDS - {"DOID"}
    before = clique_stats(concords, ids)
    dp.OVERUSE_FILTERED_CONCORDS = dp.OVERUSE_FILTERED_CONCORDS | {"DOID"}
    after = clique_stats(concords, ids)

    width = max(len(k) for k in before)
    print(f"{'':{width}}  {'DOID unfiltered':>16}  {'DOID filtered':>14}")
    for key in before:
        print(f"{key:{width}}  {before[key]:>16,}  {after[key]:>14,}")


if __name__ == "__main__":
    main()
