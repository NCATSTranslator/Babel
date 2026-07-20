"""Primitives for diffing the cliques of two finished Babel compendium builds.

This is a *build-vs-build* clique diff: given the same compendium file(s) from two
different builds, it reports which cliques split, merged, or otherwise changed
membership, and which CURIEs moved between cliques or left the output entirely.

Distinct from :mod:`src.model.glom_diff`, which is the other clique diff in this package:

- ``glom_diff`` answers "what does adding *source X* do?" It diffs in-memory glom state
  (``dict[curie, set[curie]]``) from a re-glom with vs. without one source, over the same
  code. It is what the source-impact report is built on.
- This module answers "how did the cliques change between *build A* and *build B*?" The
  inputs are the same but the code, config, or upstream data differs. It reads the finished
  JSONL compendia rather than glom state, so it can compare any two builds — e.g. a local
  build against a published ``stars.renci.org`` build — without re-running glom. That makes
  it useful for validating any glom-logic change (close-match handling, ``unique_prefixes``,
  overuse filtering) or as a release regression check.

Both share :func:`load_compendium`, which lives here because compendium I/O is the lower
layer; ``glom_diff`` imports it. See `#759 <https://github.com/NCATSTranslator/Babel/issues/759>`_
for the eventual consolidation of all compendium reading and writing.

A clique is identified by its leader (the preferred identifier, ``identifiers[0].i``). Two
cliques are "the same" when their leader and member-CURIE set are both unchanged. For each
before-clique whose leader or membership changed, :func:`diff_compendium` partitions its
members by where they ended up in the after build and emits one record per destination.

The CLI wrapper is :mod:`src.tools.clique_diff.cli` (``babel-clique-diff``); see
``docs/tools/CliqueDiff.md`` for the rendered output and its caveats.
"""

from __future__ import annotations

import gzip
import heapq
import json
import pathlib
from collections.abc import Iterator
from dataclasses import dataclass, field

# The column order of the change CSV, and equivalently the keys of every record produced by
# ``diff_compendium`` (plus ``compendium``, which ``diff_builds`` adds). Defined here rather
# than in the CLI because it is the record schema, not a presentation choice.
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

# Sentinel destination, used where a real after-clique leader would otherwise go. Parenthesised
# so it can never collide with a CURIE.
DROPPED = "(dropped)"
# Group key for members that left the output entirely: no after compendium, no after leader.
DROPPED_KEY = ("", DROPPED)


def load_compendium(path: pathlib.Path | str) -> Iterator[dict]:
    """Stream clique dicts from a JSONL compendium file, skipping blank lines.

    Accepts both the uncompressed ``.txt`` a running pipeline produces and the ``.txt.gz`` a
    finished build distributes (see ``rule compress_compendium`` in the root ``Snakefile``), so
    the diff tools work against either an in-progress or a released build.
    """
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as inf:
        for line in inf:
            line = line.strip()
            if line:
                yield json.loads(line)


def resolve_compendium_path(root: pathlib.Path | str, filename: str) -> pathlib.Path | None:
    """Find a compendium in ``root``, preferring the uncompressed form over the gzipped one.

    ``filename`` is the bare compendium name as it appears in ``config.yaml``'s ``*_outputs``
    lists (e.g. ``Disease.txt``). A build in progress has the ``.txt``; a finished one has only
    the ``.txt.gz``. Returns ``None`` when neither exists, so callers keep their existing
    "skip what isn't there" behaviour.
    """
    root = pathlib.Path(root)
    for candidate in (root / filename, root / f"{filename}.gz"):
        if candidate.exists():
            return candidate
    return None


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


def load_cliques(path, need_curie_to_leader=True):
    """Load one compendium JSONL file into a :class:`LoadedCompendium`.

    The leader is ``identifiers[0].i`` (the preferred identifier). Each identifier also
    carries a label (``l``) and each clique a Biolink ``type``, both captured for CSV
    annotation. Raises ``ValueError`` if a clique has no identifiers, naming the offending
    record's ordinal. Pass ``need_curie_to_leader=False`` to skip populating
    ``curie_to_leader`` when only clique membership is needed (e.g. the "before" side of a
    build-vs-build diff, which never looks up an after-leader) — for a large compendium that
    dict has one entry per member CURIE, so skipping it roughly halves transient allocation.
    """
    loaded = LoadedCompendium()
    for record_number, clique in enumerate(load_compendium(path), 1):
        identifiers = clique.get("identifiers") or []
        if not identifiers:
            raise ValueError(f"{path}: clique {record_number} has no identifiers")
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
        # Either build may be an in-progress one (.txt) or a released one (.txt.gz).
        before_path = resolve_compendium_path(before_dir, fname)
        after_path = resolve_compendium_path(after_dir, fname)
        if before_path is None or after_path is None:
            raise FileNotFoundError(
                f"Missing compendium {fname} (as .txt or .txt.gz) in before ({before_dir}) or after ({after_dir})"
            )
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
