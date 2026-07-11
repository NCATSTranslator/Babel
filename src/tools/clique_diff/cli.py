"""``babel-clique-diff`` — compare the cliques in two Babel compendium builds.

Argument parsing and output formatting only; the diff itself lives in
:mod:`src.model.compendium_diff`, so a second tool or a pipeline rule can reuse it.

Invocation::

    uv run babel-clique-diff --before <dir> --after <dir> --files Disease.txt \\
        --out-csv diff.csv --out-json summary.json

Output:

- ``--out-csv`` (required): one row per (changed before-clique, after-destination clique)
  group, with the columns of ``compendium_diff.CSV_COLUMNS``. ``destination_kind`` is one of
  ``kept``, ``leader_changed``, ``regrouped``, ``moved``, or ``dropped``; see
  :func:`src.model.compendium_diff.diff_compendium` for what each means. Deterministically
  sorted.
- ``--out-json`` (optional): a self-describing summary, ``{"about": …, "compendia": …}``.
  ``about`` records the two builds' labels (``--before-label``/``--after-label``, defaulting
  to the directory paths), a free-text ``note`` (``--note``), and the compared ``files`` — so
  a reader never has to guess which build was before vs after, or what the diff isolates.
  ``compendia`` maps each filename to its counts: a nested ``clique_count``
  (``before``/``after``/``diff``/``diff_percent``) plus ``changed_before_cliques``,
  ``dropped_member_count`` (the headline regression signal), ``moved_member_count``,
  ``regrouped_member_count``, and ``leader_changed_count``. ``diff_percent`` is ``null`` when
  the before build had no cliques at all but the after build has some — the percentage is
  undefined there, and reporting ``0.0`` would read as "nothing changed". NOTE: a clique that
  exists only in the after build (no before counterpart — e.g. a wholly new MP-only clique) is
  not a change row, since the diff iterates before-cliques; such additions surface only as a
  positive ``clique_count.diff``, which is why a build adding thousands of cliques can show
  few rows.

See ``docs/tools/CliqueDiff.md``.
"""

import argparse
import csv
import json

from src.model.compendium_diff import CSV_COLUMNS, diff_builds


def write_csv(rows, out_csv):
    """Write change records to ``out_csv`` as a deterministically-ordered CSV.

    Forces LF line endings (``lineterminator="\\n"``) regardless of platform so the
    output is byte-stable when committed or diffed.
    """
    with open(out_csv, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in sorted(
            rows, key=lambda r: (r["compendium"], r["before_leader"], r["destination_compendium"], r["destination"])
        ):
            writer.writerow({k: r[k] for k in CSV_COLUMNS})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Diff the cliques in two Babel compendium builds.")
    parser.add_argument("--before", required=True, help="Directory of the baseline build's compendia.")
    parser.add_argument("--after", required=True, help="Directory of the comparison build's compendia.")
    parser.add_argument(
        "--files",
        required=True,
        nargs="+",
        help="Compendium filenames to compare (e.g. Disease.txt PhenotypicFeature.txt).",
    )
    parser.add_argument("--out-csv", required=True, help="Path to write the per-clique change CSV.")
    parser.add_argument("--out-json", help="Optional path to write the per-compendium summary JSON.")
    # Baseline labels make the summary self-describing: a reader shouldn't have to know which
    # build was --before vs --after (e.g. "main (no MP)" vs "mp-hp-disjoint"). Default to the
    # directory paths so the provenance is never blank.
    parser.add_argument("--before-label", help="Human label for the --before build (defaults to its path).")
    parser.add_argument("--after-label", help="Human label for the --after build (defaults to its path).")
    parser.add_argument("--note", help="Free-text note recorded in the summary (e.g. what change this diff isolates).")
    args = parser.parse_args(argv)

    rows, summary = diff_builds(args.before, args.after, args.files)
    write_csv(rows, args.out_csv)
    if args.out_json:
        out = {
            "about": {
                "before": args.before_label or args.before,
                "after": args.after_label or args.after,
                "note": args.note or "",
                "files": list(args.files),
            },
            "compendia": summary,
        }
        with open(args.out_json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")

    total_changed = sum(s["changed_before_cliques"] for s in summary.values())
    total_dropped = sum(s["dropped_member_count"] for s in summary.values())
    print(f"Wrote {len(rows)} change rows across {len(summary)} compendia ({total_changed} changed before-cliques).")
    for fname, s in sorted(summary.items()):
        print(
            f"  {fname}: {s['changed_before_cliques']} changed cliques, "
            f"{s['dropped_member_count']} dropped members, {s['moved_member_count']} moved"
        )
    print(f"Total members dropped from the compared compendia: {total_dropped}")


if __name__ == "__main__":
    main()
