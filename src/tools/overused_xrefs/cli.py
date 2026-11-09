"""``babel-overused-xrefs`` — which xref targets in a concord are claimed by many subjects?

Every concord row is fed to ``glom()`` as an equivalence, so one target claimed by many subjects
fuses all of them into a single clique. That is the failure mode
:func:`src.babel_utils.remove_overused_xrefs` drops and ``OVERUSE_FILTERED_CONCORDS`` opts a
source into; this tool shows what is actually in there before or after that decision.

Argument parsing and CSV writing only: the analysis is
:func:`src.model.concords.find_overused_xref_targets` and labels come from
:func:`src.reports.source_impact.load_labels_for_prefixes`.

Invocation::

    uv run babel-overused-xrefs --concord babel_outputs/intermediate/disease/concords/DOID \\
        --out overused-targets.csv [--mrconso babel_downloads/UMLS/MRCONSO.RRF]

Output is **long format** — one row per (target, subject) pair, not one row per target — so the
result sorts and filters in a spreadsheet without unpacking a delimited cell. Both endpoints
carry their preferred label where Babel knows one::

    target,target_label,target_prefix,subject_count,subject,subject_label
    ICD10:G11.4,Other hereditary spastic paraplegia,ICD10,60,DOID:0110764,hereditary spastic paraplegia 11

Labels come from ``babel_downloads/<PREFIX>/labels``. Prefixes Babel references but never
ingests (ICD-10, ICD-9, SNOMED) have no such file, so pass ``--mrconso`` to fill them in from
UMLS; without it those cells are empty. Rows are sorted most-claimed target first, then by target
and subject, so re-runs diff cleanly.
"""

import argparse
import csv
import pathlib
import sys

from src.model.concords import find_overused_xref_targets, load_mrconso_labels
from src.reports.source_impact import load_labels_for_prefixes
from src.util import Text, get_logger

logger = get_logger(__name__)

CSV_COLUMNS = ["target", "target_label", "target_prefix", "subject_count", "subject", "subject_label"]


def resolve_labels(curies, downloads_root, mrconso=None):
    """Return a CURIE->label map, from per-prefix label files plus an optional MRCONSO fallback."""
    # get_prefix(), not get_prefix_or_none(): the latter upper-cases, and a label file is looked
    # up by directory name, so `orphanet:558` would send us to babel_downloads/ORPHANET/labels --
    # a miss on any case-sensitive filesystem, i.e. every row blank on the cluster but fine on a
    # developer's Mac. Same for ComplexPortal, wikipedia.en and icd11.
    prefixes = {Text.get_prefix(c) for c in curies if ":" in c}
    by_prefix = load_labels_for_prefixes(sorted(prefixes), downloads_root, needed_curies=set(curies))
    labels = {curie: label for prefix_labels in by_prefix.values() for curie, label in prefix_labels.items()}
    missing = {c for c in curies if c not in labels}
    if missing and mrconso:
        from_mrconso = load_mrconso_labels(mrconso, missing)
        if not from_mrconso:
            # Asking for MRCONSO labels and getting none back means the file is not the one you
            # think it is -- truncated, a different release, or an RRF that is not MRCONSO. A
            # regenerated audit would otherwise be a page of bare codes with only a warning to say
            # so, and the committed CSV would look like a real result. See AGENTS.md, "A log
            # warning is not a control."
            raise RuntimeError(
                f"{mrconso} resolved no labels at all for {len(missing)} unlabelled CURIEs "
                f"(e.g. {sorted(missing)[:3]}). Expected a UMLS MRCONSO.RRF; check the path and "
                f"that the file is complete."
            )
        labels.update(from_mrconso)
        missing = {c for c in curies if c not in labels}
    if missing:
        unlabelled_prefixes = sorted({Text.get_prefix(c) for c in missing if ":" in c})
        hint = "" if mrconso else " (pass --mrconso to resolve ICD/SNOMED-style codes from UMLS)"
        logger.warning(
            "no label for %d of %d CURIEs, prefixes %s%s", len(missing), len(curies), unlabelled_prefixes, hint
        )
    return labels


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--concord", required=True, help="Path to a concord file (subject/predicate/object TSV).")
    parser.add_argument("--out", required=True, help="Where to write the CSV.")
    parser.add_argument(
        "--min-subjects",
        type=int,
        default=2,
        help="Report a target claimed by at least this many distinct subjects (default: 2, "
        "matching remove_overused_xrefs).",
    )
    parser.add_argument(
        "--target-prefixes",
        help="Comma-separated target prefixes to restrict the audit to (e.g. ICD10,ICD9). "
        "With --min-subjects 1 this enumerates every row targeting those namespaces, which is "
        "how a categorical prefix exclusion is reviewed.",
    )
    parser.add_argument(
        "--downloads-root",
        default="babel_downloads",
        help="Root holding per-prefix labels files (default: babel_downloads).",
    )
    parser.add_argument(
        "--mrconso",
        help="Optional UMLS MRCONSO.RRF, used to label CURIEs with no per-prefix labels file (ICD-10, ICD-9, SNOMED).",
    )
    args = parser.parse_args(argv)

    target_prefixes = (
        [p.strip() for p in args.target_prefixes.split(",") if p.strip()] if args.target_prefixes else None
    )
    overused = find_overused_xref_targets(args.concord, min_subjects=args.min_subjects, target_prefixes=target_prefixes)
    if not overused:
        logger.warning(
            "no target in %s is claimed by %d+ subjects%s",
            args.concord,
            args.min_subjects,
            f" within prefixes {target_prefixes}" if target_prefixes else "",
        )

    curies = {o.target for o in overused} | {s for o in overused for s in o.subjects}
    labels = resolve_labels(curies, args.downloads_root, mrconso=args.mrconso)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with out_path.open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(CSV_COLUMNS)
        for target in overused:
            for subject in sorted(target.subjects):
                writer.writerow(
                    [
                        target.target,
                        labels.get(target.target, ""),
                        target.prefix,
                        target.subject_count,
                        subject,
                        labels.get(subject, ""),
                    ]
                )
                rows += 1
    logger.info("wrote %s: %d rows across %d overused targets", out_path, rows, len(overused))
    return 0


if __name__ == "__main__":
    sys.exit(main())
