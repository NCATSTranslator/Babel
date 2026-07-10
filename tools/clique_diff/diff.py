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
Two cliques are "the same" when their leader and member-CURIE set are both unchanged. For
each before-clique whose leader or membership changed, the tool partitions its members by
where they ended up in the after build and emits one row per destination.

Output:

- ``--out-csv`` (required): one row per (changed before-clique, after-destination clique) group.
  Columns: ``compendium, before_leader, before_leader_label, before_leader_type,
  before_size, destination, destination_label, destination_kind, destination_compendium,
  destination_type, after_size, member_count, example_members``. ``destination_kind`` is one of:
  ``kept`` (members still under the same leader), ``leader_changed`` (the whole clique's
  membership is unchanged but its preferred identifier was reassigned), ``regrouped``
  (members were actually redistributed to a different after-clique in the same
  compendium), ``moved`` (the CURIE was retyped into a different compared compendium), or
  ``dropped`` (the CURIE is absent from every compared after compendium — it left the
  output entirely). Deterministically sorted. ``before_leader_label``/``before_leader_type``
  are the before-build label and Biolink type of the clique leader. Every row names a concrete
  destination *clique*: ``destination``/``destination_label``/``destination_type`` are the
  after-build leader, label and Biolink type of the clique the grouped members landed in, and
  ``destination_compendium`` is the file that clique lives in — equal to ``compendium`` except
  on ``moved`` rows, which is what makes a retyped member's new home readable straight off the
  row rather than inferable only from ``example_members``. ``dropped`` rows have no destination
  clique, so ``destination`` is ``(dropped)`` and the other destination columns are empty.
  ``example_members`` lists up to five members as ``CURIE "label"`` using before-build labels.
- ``--out-json`` (optional): a self-describing summary, ``{"about": …, "compendia": …}``.
  ``about`` records the two builds' labels (``--before-label``/``--after-label``, defaulting
  to the directory paths), a free-text ``note`` (``--note``), and the compared ``files`` — so a
  reader never has to guess which build was before vs after or what the diff isolates.
  ``compendia`` maps each filename to its counts: a nested ``clique_count``
  (``before``/``after``/``diff``/``diff_percent``) plus ``changed_before_cliques``,
  ``dropped_member_count`` (the headline regression signal), ``moved_member_count``,
  ``regrouped_member_count``, and ``leader_changed_count``. NOTE: a clique that exists only in
  the after build (no before counterpart — e.g. a wholly new MP-only clique) is not a change
  row, since the diff iterates before-cliques; such additions surface only as a positive
  ``clique_count.diff``, which is why a build adding thousands of cliques can show few rows.
"""

import argparse
import csv
import heapq
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LoadedCompendium:
    """One compendium JSONL file parsed into the lookups the diff needs.

    - ``cliques``: leader → frozenset(member CURIEs).
    - ``curie_to_leader``: member CURIE → its clique leader (empty when
      ``need_curie_to_leader=False`` was passed to :func:`load_cliques`).
    - ``labels``: member CURIE → its label (``""`` when the source had none). Used to
      annotate the leader and example members in the CSV.
    - ``clique_type``: leader → the clique's Biolink type (e.g. ``biolink:Disease``).
    """

    cliques: dict = field(default_factory=dict)
    curie_to_leader: dict = field(default_factory=dict)
    labels: dict = field(default_factory=dict)
    clique_type: dict = field(default_factory=dict)

    def __iter__(self):
        # Preserve the historical 2-tuple unpacking ``cliques, curie_to_leader = load_cliques(...)``.
        return iter((self.cliques, self.curie_to_leader))


def load_cliques(path, need_curie_to_leader=True):
    """Load one compendium JSONL file into a :class:`LoadedCompendium`.

    The leader is ``identifiers[0].i`` (the preferred identifier). Each identifier also
    carries a label (``l``) and each clique a Biolink ``type``, both captured for CSV
    annotation. Raises ``ValueError`` if a line has no identifiers. Pass
    ``need_curie_to_leader=False`` to skip populating ``curie_to_leader`` when only clique
    membership is needed (e.g. the "before" side of a build-vs-build diff, which never looks
    up an after-leader) — for a large compendium that dict has one entry per member CURIE, so
    skipping it roughly halves transient allocation. The returned object still unpacks as the
    historical ``(cliques, curie_to_leader)`` 2-tuple.
    """
    loaded = LoadedCompendium()
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
            loaded.cliques[leader] = members
            loaded.clique_type[leader] = clique.get("type") or ""
            for identifier in identifiers:
                loaded.labels[identifier["i"]] = identifier.get("l") or ""
            if need_curie_to_leader:
                for curie in members:
                    loaded.curie_to_leader[curie] = leader
    return loaded


DROPPED = "(dropped)"
# Group key for members that left the output entirely: no after compendium, no after leader.
DROPPED_KEY = ("", DROPPED)


def _format_members(curies, labels):
    """Render up to five members (smallest CURIEs first) as ``CURIE "label"``.

    Labels come from the before build (``labels`` maps CURIE → label). A member with no
    known label renders as ``CURIE ""``. Deterministic so the CSV is byte-stable.
    """
    return "; ".join(f'{c} "{labels.get(c, "")}"' for c in heapq.nsmallest(5, curies))


def diff_compendium(compendium, before, after_by_file, after_location):
    """Diff one compendium's cliques between two builds.

    ``compendium`` is the filename being diffed; ``before`` is its :class:`LoadedCompendium`
    in the before build and ``after_by_file`` maps every compared filename to its
    :class:`LoadedCompendium` in the after build. ``after_location`` maps each CURIE present
    anywhere in the after build to the ``(filename, leader)`` of the after-clique it landed
    in — which is what lets a ``moved`` member name its real destination clique even though
    that clique lives in a different file.

    Members are partitioned by that ``(filename, leader)`` destination, so every row names a
    concrete after-clique rather than a sentinel. ``destination_kind`` is:

    - ``kept`` — destination is this compendium, under the same leader;
    - ``leader_changed`` — the whole before-clique landed under one different leader in this
      compendium whose membership is otherwise identical (the preferred identifier was
      reassigned, nothing else moved);
    - ``regrouped`` — destination is a different leader in this compendium (members were
      actually redistributed);
    - ``moved`` — destination is a clique in a *different* compared compendium (the CURIE was
      retyped);
    - ``dropped`` — the CURIE is absent from every compared after compendium. This is the
      consequential category: the identifier left the output entirely, so there is no
      destination clique and ``destination`` is ``(dropped)``.

    Returns one record per (before-clique, destination-clique) group, but only for
    before-cliques whose clique-vs-clique state actually changed — a before-clique that keeps
    the exact same leader and membership is skipped entirely (nothing to report). Each record
    has keys ``before_leader``, ``before_leader_label``, ``before_leader_type``,
    ``before_size``, ``destination``, ``destination_label``, ``destination_kind``,
    ``destination_compendium``, ``destination_type``, ``after_size``, ``member_count``,
    ``example_members``. ``destination``/``destination_label``/``destination_type``/
    ``after_size`` describe the destination clique in the after build (all empty or zero for
    ``dropped``); ``destination_compendium`` is the file it lives in, which differs from
    ``compendium`` exactly for ``moved`` rows. ``example_members`` is left empty for
    ``leader_changed`` rows, since ``before_leader``/``destination`` already say everything
    that changed (the old and new leader) and re-listing the unchanged membership adds no
    information.
    """
    after = after_by_file[compendium]
    records = []
    for before_leader, members in before.cliques.items():
        # Partition members by the after-clique they landed in, identified globally as
        # (filename, leader) so a member retyped into another compendium still names its clique.
        groups = {}
        for c in members:
            groups.setdefault(after_location.get(c, DROPPED_KEY), []).append(c)
        # Whole-clique case: every member landed under one after-clique in this same
        # compendium, whose membership is identical to the before-clique's.
        only_dest = next(iter(groups)) if len(groups) == 1 else None
        whole_clique_unchanged = (
            only_dest is not None and only_dest[0] == compendium and after.cliques.get(only_dest[1]) == members
        )
        if whole_clique_unchanged and only_dest[1] == before_leader:
            continue  # Same leader, same membership: nothing changed.
        for (dest_file, dest_leader), group_members in groups.items():
            if dest_file == "":
                destination_kind, after_size, destination_label, destination_type = "dropped", 0, "", ""
            else:
                dest_after = after_by_file[dest_file]
                if dest_file != compendium:
                    destination_kind = "moved"
                elif whole_clique_unchanged:
                    destination_kind = "leader_changed"
                else:
                    destination_kind = "kept" if dest_leader == before_leader else "regrouped"
                after_size = len(dest_after.cliques[dest_leader])
                destination_label = dest_after.labels.get(dest_leader, "")
                destination_type = dest_after.clique_type.get(dest_leader, "")
            records.append(
                {
                    "before_leader": before_leader,
                    "before_leader_label": before.labels.get(before_leader, ""),
                    "before_leader_type": before.clique_type.get(before_leader, ""),
                    "before_size": len(members),
                    "destination": dest_leader,
                    "destination_label": destination_label,
                    "destination_kind": destination_kind,
                    "destination_compendium": dest_file,
                    "destination_type": destination_type,
                    "after_size": after_size,
                    "member_count": len(group_members),
                    "example_members": (
                        "" if destination_kind == "leader_changed" else _format_members(group_members, before.labels)
                    ),
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
    # First pass: load everything and locate every after-CURIE as (filename, leader), so a
    # member retyped into another compendium can still name the after-clique it landed in.
    before_by_file, after_by_file = {}, {}
    after_location = {}
    for fname in filenames:
        before_path = Path(before_dir) / fname
        after_path = Path(after_dir) / fname
        if not before_path.exists() or not after_path.exists():
            raise FileNotFoundError(f"Missing compendium {fname} in before ({before_path}) or after ({after_path})")
        before_by_file[fname] = load_cliques(before_path, need_curie_to_leader=False)
        after = load_cliques(after_path)
        after_by_file[fname] = after
        for curie, leader in after.curie_to_leader.items():
            after_location[curie] = (fname, leader)

    rows = []
    summary = {}
    for fname in filenames:
        before = before_by_file[fname]
        after_cliques = after_by_file[fname].cliques
        records = diff_compendium(fname, before, after_by_file, after_location)
        for r in records:
            r["compendium"] = fname
            rows.append(r)
        before_count = len(before.cliques)
        after_count = len(after_cliques)
        summary[fname] = {
            # Nested so the headline magnitude reads at a glance. NOTE: a clique that exists
            # only in the after build (no before counterpart — e.g. a wholly new MP-only
            # clique) is NOT emitted as a change row; the diff iterates before-cliques. Such
            # additions appear *only* here, as a positive ``clique_count.diff``. That is why a
            # build that adds thousands of new cliques can still show few change rows.
            "clique_count": {
                "before": before_count,
                "after": after_count,
                "diff": after_count - before_count,
                # Percent change of the clique count (after vs before); 0.0 when unchanged.
                "diff_percent": (
                    0.0
                    if after_count == before_count
                    else (None if before_count == 0 else round(100 * (after_count - before_count) / before_count, 2))
                ),
            },
            "changed_before_cliques": len({r["before_leader"] for r in records}),
            "cliques_with_dropped_members": len(
                {r["before_leader"] for r in records if r["destination_kind"] == "dropped"}
            ),
            "dropped_member_count": sum(r["member_count"] for r in records if r["destination_kind"] == "dropped"),
            "moved_member_count": sum(r["member_count"] for r in records if r["destination_kind"] == "moved"),
            "regrouped_member_count": sum(r["member_count"] for r in records if r["destination_kind"] == "regrouped"),
            "leader_changed_count": sum(1 for r in records if r["destination_kind"] == "leader_changed"),
        }
    return rows, summary


CSV_COLUMNS = [
    "compendium",
    "before_leader",
    "before_leader_label",
    "before_leader_type",
    "before_size",
    "destination",
    "destination_label",
    "destination_kind",
    "destination_compendium",
    "destination_type",
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
        with open(args.out_json, "w") as fh:
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
