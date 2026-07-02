"""Compare the cliques in two Babel compendium builds and report what changed.

This is a *build-vs-build* clique diff: given the same compendium file(s) from two
different builds (``--before`` and ``--after``), it reports which cliques split,
merged, or otherwise changed membership, and which CURIEs moved between cliques.

It is deliberately distinct from the source-impact report
(``src/cli/source_impact_report.py``):

- The source-impact report answers "what does adding *source X* do?" by re-glomming
  the intermediate ids/concords with vs. without one source over the *same* code.
- This tool answers "how did the cliques change between *build A* and *build B*?" — the
  inputs are the same but the code/config (or upstream data) differs. It operates on the
  finished JSONL compendia rather than in-memory glom state, so it can compare any two
  builds — e.g. a local build against a published ``stars.renci.org`` build — without
  re-running glom. That makes it useful for validating any glom-logic change
  (close-match handling, ``unique_prefixes``, overuse filtering) or as a release
  regression check.

A clique is identified by its leader (the preferred identifier, ``identifiers[0].i``).
Two cliques are "the same" when their member-CURIE sets are equal. For each before-clique
whose membership changed, the tool partitions its members by where they ended up in the
after build and emits one row per destination.

Output:

- ``--out-csv`` (required): one row per (changed before-clique, after-destination) group.
  Columns: ``compendium, before_leader, before_size, destination, destination_kind,
  after_size, member_count, example_members``. ``destination_kind`` is one of:
  ``kept`` (members still under the same leader), ``regrouped`` (members moved to a
  different after-clique in the same compendium), ``moved`` (the CURIE was retyped into a
  different compared compendium), or ``dropped`` (the CURIE is absent from every compared
  after compendium — it left the output entirely). Deterministically sorted.
- ``--out-json`` (optional): a summary with per-compendium counts, including
  ``dropped_member_count`` — the headline regression signal.
"""

import argparse
import csv
import heapq
import json
from pathlib import Path


def load_cliques(path, need_curie_to_leader=True):
    """Load one compendium JSONL file into a list of member-CURIE sets and a CURIE→leader map.

    The leader is ``identifiers[0].i`` (the preferred identifier). Returns
    ``(cliques, curie_to_leader)`` where ``cliques`` maps leader → frozenset(member CURIEs).
    Raises ``ValueError`` if a line has no identifiers. Pass ``need_curie_to_leader=False`` to
    skip populating ``curie_to_leader`` when only clique membership is needed (e.g. the "before"
    side of a build-vs-build diff, which never looks up an after-leader) — for a large compendium
    that dict has one entry per member CURIE, so skipping it roughly halves transient allocation.
    """
    cliques = {}
    curie_to_leader = {}
    with open(path) as inf:
        for lineno, line in enumerate(inf, 1):
            line = line.strip()
            if not line:
                continue
            clique = json.loads(line)
            identifiers = clique.get("identifiers") or []
            if not identifiers:
                raise ValueError(f"{path}:{lineno}: clique has no identifiers")
            members = frozenset(i["i"] for i in identifiers)
            leader = identifiers[0]["i"]
            cliques[leader] = members
            if need_curie_to_leader:
                for curie in members:
                    curie_to_leader[curie] = leader
    return cliques, curie_to_leader


DROPPED = "(dropped)"
MOVED = "(moved-to-other-compendium)"


def diff_compendium(before_cliques, after_cliques, after_leader_of, all_after_curies):
    """Diff one compendium's cliques between two builds.

    Each member of a before-clique lands in one of three kinds of destination in the
    after build:

    - a real after-clique leader (in this same compendium): ``destination_kind`` is
      ``kept`` if that leader equals the before leader, else ``regrouped``;
    - ``(moved-to-other-compendium)`` — the CURIE still exists in the after build but in a
      different compendium file (it was retyped);
    - ``(dropped)`` — the CURIE is absent from every compared after compendium. This is the
      consequential category: the identifier left the output entirely.

    Yields one record per (before-clique, destination) group, but only for before-cliques
    whose membership actually changed (a clique whose members are identical in both builds,
    even if its leader differs, is skipped). Each record has keys ``before_leader``,
    ``before_size``, ``destination``, ``destination_kind``, ``after_size``,
    ``member_count``, ``example_members``.
    """
    records = []
    for before_leader, members in before_cliques.items():
        # Partition members by their after-build destination.
        groups = {}
        for c in members:
            if c in after_leader_of:
                dest = after_leader_of[c]
            elif c in all_after_curies:
                dest = MOVED
            else:
                dest = DROPPED
            groups.setdefault(dest, []).append(c)
        # Unchanged: every member landed in the same single after-clique, and that
        # after-clique's membership is identical to the before-clique's — even if the
        # leader (preferred identifier) itself changed.
        if len(groups) == 1:
            (dest,) = groups
            if dest not in (DROPPED, MOVED) and after_cliques.get(dest) == members:
                continue
        for dest, group_members in groups.items():
            if dest == DROPPED:
                destination_kind, after_size = "dropped", 0
            elif dest == MOVED:
                destination_kind, after_size = "moved", 0
            else:
                destination_kind = "kept" if dest == before_leader else "regrouped"
                after_size = len(after_cliques[dest])
            records.append(
                {
                    "before_leader": before_leader,
                    "before_size": len(members),
                    "destination": dest,
                    "destination_kind": destination_kind,
                    "after_size": after_size,
                    "member_count": len(group_members),
                    "example_members": ";".join(heapq.nsmallest(5, group_members)),
                }
            )
    return records


def diff_builds(before_dir, after_dir, filenames):
    """Diff a set of compendium files between two build directories.

    Returns ``(rows, summary)``: ``rows`` is a list of change records (each also carrying
    a ``compendium`` key), and ``summary`` is a per-compendium counts dict. "Dropped" is
    judged against the union of all compared after compendia, so a CURIE retyped into one
    of the other ``filenames`` counts as ``moved``, not ``dropped``.
    """
    # First pass: load everything and compute the global set of CURIEs present after.
    before_by_file, after_by_file = {}, {}
    all_after_curies = set()
    for fname in filenames:
        before_path = Path(before_dir) / fname
        after_path = Path(after_dir) / fname
        if not before_path.exists() or not after_path.exists():
            raise FileNotFoundError(f"Missing compendium {fname} in before ({before_path}) or after ({after_path})")
        before_by_file[fname] = load_cliques(before_path, need_curie_to_leader=False)
        after_by_file[fname] = load_cliques(after_path)
        all_after_curies.update(after_by_file[fname][1])

    rows = []
    summary = {}
    for fname in filenames:
        before_cliques, _ = before_by_file[fname]
        after_cliques, after_leader_of = after_by_file[fname]
        records = diff_compendium(before_cliques, after_cliques, after_leader_of, all_after_curies)
        for r in records:
            r["compendium"] = fname
            rows.append(r)
        summary[fname] = {
            "before_clique_count": len(before_cliques),
            "after_clique_count": len(after_cliques),
            "changed_before_cliques": len({r["before_leader"] for r in records}),
            "cliques_with_dropped_members": len(
                {r["before_leader"] for r in records if r["destination_kind"] == "dropped"}
            ),
            "dropped_member_count": sum(r["member_count"] for r in records if r["destination_kind"] == "dropped"),
            "moved_member_count": sum(r["member_count"] for r in records if r["destination_kind"] == "moved"),
            "regrouped_member_count": sum(r["member_count"] for r in records if r["destination_kind"] == "regrouped"),
        }
    return rows, summary


CSV_COLUMNS = [
    "compendium",
    "before_leader",
    "before_size",
    "destination",
    "destination_kind",
    "after_size",
    "member_count",
    "example_members",
]


def write_csv(rows, out_csv):
    """Write change records to ``out_csv`` as a deterministically-ordered CSV.

    Forces LF line endings (``lineterminator="\\n"``) regardless of platform so the
    output is byte-stable when committed or diffed.
    """
    with open(out_csv, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in sorted(rows, key=lambda r: (r["compendium"], r["before_leader"], r["destination"])):
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
    args = parser.parse_args(argv)

    rows, summary = diff_builds(args.before, args.after, args.files)
    write_csv(rows, args.out_csv)
    if args.out_json:
        with open(args.out_json, "w") as fh:
            json.dump(summary, fh, indent=2, sort_keys=True)
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
