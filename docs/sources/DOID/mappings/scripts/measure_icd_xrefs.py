"""Measure what DOID's ICD xrefs do to disease clique sizes.

Prints the four-scenario table quoted in ``docs/sources/DOID/mappings.md``:

* **ICD kept** -- every DOID ICD xref fed to glom(), the merge problem in the raw.
* **overuse-filtered** -- ``remove_overused_xrefs`` over the whole DOID concord, unscoped.
* **ICD overuse-filtered** -- what the pipeline does: the same filter scoped to the ICD prefixes.
* **ICD excluded** -- the ICD namespaces dropped outright, the treatment this replaced.

The middle two columns are why this script exists and why it survives the build-vs-build clique
diff: only one of the four is a build that will ever be made, and no diff can price the three that
will not.

All three columns sit on top of the *current* `config.yaml: disease_xref_prefixes` rename map, so
they isolate the ICD decision and nothing else. None of them reproduces a historical build --
before the renames landed, DOID's MIM:, SNOMEDCT_US_* and ORDO: rows reached glom() un-renamed. Use
`babel-clique-diff` for "what did this change do to the last build"; use this for "which ICD
treatment should we pick".

Each scenario rebuilds the DOID concord through the production
``build_disease_doid_relationships()`` -- toggling the production
``OVERUSE_FILTERED_CONCORDS`` -- and then replays the production
``compute_cliques_for_impact_report()`` over a finished build's ``intermediate/disease/``. Nothing
here reimplements the pipeline, so the measurement cannot drift from it (see docs/sources/CLAUDE.md,
"Replaying a pipeline function beats rebuilding to measure a change"). A replay only sees the
cliques the build already produced, so it cannot show cliques that move *between* compendia --
confirm with ``babel-clique-diff`` on a real build before trusting the totals.

The companion artifacts are not written here: both CSVs come from the ``babel-overused-xrefs``
tool (docs/tools/OverusedXrefs.md). Regenerate everything together::

    # every ICD row, kept or dropped -- subject_count says which side of the filter each is on
    uv run babel-overused-xrefs --concord babel_outputs/intermediate/disease/concords/DOID \
        --min-subjects 1 --target-prefixes ICD10,ICD9,ICD0,ICD11 \
        --out docs/sources/DOID/mappings/icd-targets.csv --mrconso babel_downloads/UMLS/MRCONSO.RRF
    # every overused target in the concord, ICD and not
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
import src.datahandlers.doid as doid
from src.prefixes import DOID

# Cliques probed individually in the report. Each is the preferred identifier of a clique that one
# ICD-10 code inflated; the label is MONDO's.
PROBES = {
    "MONDO:0019064": "hereditary spastic paraplegia",
    "MONDO:0000912": "autosomal recessive nonsyndromic hearing loss 5",
    "MONDO:0000910": "retinitis pigmentosa 6",
}


def build_concord(doid_json, outdir, exclude_icd=False):
    """Build one DOID concord through the production path, optionally excluding ICD outright.

    Both branches are production functions composed, not reimplemented: the pipeline no longer
    passes `excluded_target_prefixes`, so the "ICD excluded" scenario has to ask `doid.build_xrefs`
    for it directly, with the same rename map the build uses.
    """
    outfile = os.path.join(outdir, "DOID")
    if exclude_icd:
        doid.build_xrefs(
            doid_json,
            outfile,
            other_prefixes=dp.get_xref_prefix_map(DOID),
            excluded_target_prefixes=dp.DOID_ICD_XREF_PREFIXES,
        )
    else:
        dp.build_disease_doid_relationships(doid_json, outfile, os.path.join(outdir, "metadata-DOID.yaml"))
    return outfile


# Sentinel for "do not overuse-filter the DOID concord at all", distinct from None, which is the
# production spelling of "filter it over every namespace".
UNFILTERED = object()


def clique_stats(concords, ids, doid_filter=UNFILTERED):
    """Replay the production clique builder and summarize the clique-size distribution."""
    saved = dp.OVERUSE_FILTERED_CONCORDS
    try:
        if doid_filter is UNFILTERED:
            dp.OVERUSE_FILTERED_CONCORDS = {k: v for k, v in saved.items() if k != "DOID"}
        else:
            dp.OVERUSE_FILTERED_CONCORDS = saved | {"DOID": doid_filter}
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
        unfiltered = build_concord(args.doid_json, unfiltered_dir)
        filtered = build_concord(args.doid_json, filtered_dir, exclude_icd=True)

        icd = collections.Counter()
        with open(unfiltered) as inf:
            for line in inf:
                prefix = line.rstrip("\n").split("\t")[-1].split(":", 1)[0]
                if prefix.upper().startswith("ICD"):
                    icd[prefix] += 1
        total = sum(1 for _ in open(unfiltered))
        print(f"DOID concord: {total} rows, {sum(icd.values())} of them ICD {dict(icd.most_common())}\n")

        # Every scenario differs only in which DOID concord is substituted in, so a concords list
        # that does not contain the built one silently yields three identical columns presented as
        # a comparison. Fail instead of printing that.
        if built_concord not in concords:
            raise RuntimeError(
                f"{built_concord} is not among the concords found under {root}/concords -- the three "
                f"scenarios would be identical. Build the disease intermediates first "
                f"(`uv run snakemake -c all get_disease_doid_relationships`)."
            )

        # The intermediate on disk may predate the current doid.json; say so rather than silently
        # comparing against a concord the rest of the numbers don't come from.
        if sum(1 for _ in open(built_concord)) not in (total, total - sum(icd.values())):
            print(f"NOTE: {built_concord} matches neither rebuild; doid.json has moved since it was built.\n")

        def with_doid(path):
            return [path if c == built_concord else c for c in concords]

        # "ICD kept", not "as built": every column is built with the current rename map, so none of
        # them is the build that shipped before this change.
        scenarios = {
            "ICD kept": clique_stats(with_doid(unfiltered), ids),
            "overuse-filtered": clique_stats(with_doid(unfiltered), ids, doid_filter=None),
            "ICD overuse-filtered": clique_stats(with_doid(unfiltered), ids, doid_filter=dp.DOID_ICD_XREF_PREFIXES),
            "ICD excluded": clique_stats(with_doid(filtered), ids),
        }

    keys = list(next(iter(scenarios.values())))
    width = max(len(k) for k in keys)
    print(f"{'':{width}}" + "".join(f"{name:>23}" for name in scenarios))
    for key in keys:
        print(f"{key:{width}}" + "".join(f"{s[key]:>23,}" for s in scenarios.values()))


if __name__ == "__main__":
    main()
