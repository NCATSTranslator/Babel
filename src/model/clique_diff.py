"""Primitives for diffing Babel clique state with and without a given source.

The CLI in ``src/cli/source_impact_report.py`` is the main consumer. The "synthetic"
comparison mode calls a semantic-type-specific compute function (e.g.
``anatomy.compute_cliques_for_impact_report``) twice — once with the new source's
intermediate files excluded, once with them included — and then calls ``diff_cliques``
here to bucket the differences.

A clique is represented as a ``frozenset[str]`` of CURIEs. The glom output (used by
``build_compendia``) is a ``dict[curie, set[curie]]`` where every CURIE points to its
clique's mutable set; ``cliques_set`` collapses that to the deduplicated frozenset view.

The "remote" comparison mode reads JSONL compendia from a previous Babel build and uses
``cliques_from_compendia`` to derive the same frozenset view from disk.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field

GlomDict = Mapping[str, "Iterable[str]"]


@dataclass(frozen=True)
class ExpandedClique:
    """A before-clique that gained at least one source CURIE without merging.

    ``added_source_curies`` is the strict difference (after - before): source CURIEs that
    were not already in the before-clique. ``promoted_source_curies`` is the intersection:
    source CURIEs already pulled into the clique by some other source's xref, which the
    new source now claims as first-class typed identifiers. When ``added_source_curies``
    is empty, the clique's identifier set is unchanged — the new source only "promotes"
    pre-existing xref leaves into typed identifiers. Callers that want to count clique
    growth should check ``added_source_curies`` rather than ``promoted_source_curies``.
    """

    before_clique: frozenset[str]
    added_source_curies: frozenset[str]
    after_clique: frozenset[str]
    promoted_source_curies: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MergedClique:
    """Two or more before-cliques that were bridged into one after-clique by new-source
    CURIEs."""

    before_cliques: tuple[frozenset[str], ...]
    source_curies_involved: frozenset[str]
    after_clique: frozenset[str]


@dataclass
class SourceImpactDiff:
    """Result of comparing before/after clique state for a single semantic type."""

    semantic_type: str
    source_curies: frozenset[str]
    pure_new_cliques: list[frozenset[str]] = field(default_factory=list)
    expanded_cliques: list[ExpandedClique] = field(default_factory=list)
    merged_cliques: list[MergedClique] = field(default_factory=list)
    before_clique_count: int = 0
    after_clique_count: int = 0


def cliques_set(glom_dict: GlomDict) -> frozenset[frozenset[str]]:
    """Collapse a glom dict-of-sets to a deduplicated set of cliques.

    ``build_compendia`` produces a dict where every CURIE points to its mutable clique
    set; many keys share the same set object. We materialise that as a frozenset of
    frozensets for downstream set operations.
    """
    # Deduplicate by object identity first (many CURIEs share the same set object),
    # then freeze — reduces N freeze calls to K (one per unique clique).
    unique_sets = {id(v): v for v in glom_dict.values()}.values()
    return frozenset(frozenset(v) for v in unique_sets)


def _lookup_table(glom_dict: GlomDict) -> dict[str, frozenset[str]]:
    """Return a {curie: clique-as-frozenset} lookup derived from a glom dict."""
    out: dict[str, frozenset[str]] = {}
    for curie, members in glom_dict.items():
        out[curie] = frozenset(members)
    return out


def diff_cliques(
    before: GlomDict,
    after: GlomDict,
    source_curies: Iterable[str],
    *,
    semantic_type: str,
) -> SourceImpactDiff:
    """Bucket the differences between two clique states into pure_new / expanded / merged.

    For each after-clique that contains any source-attributed CURIE:

    - if the clique has no non-source CURIEs, or its non-source CURIEs were absent from
      ``before`` entirely, it's a **pure new** clique (the source contributed everything,
      either directly via its ids file or indirectly via its concord rows introducing new
      aliases);
    - if the non-source CURIEs all belonged to exactly one before-clique, the source
      **expanded** that clique;
    - if the non-source CURIEs spanned two or more before-cliques, the source **merged**
      them.

    Note that ``source_curies`` should be the union across all prefixes the source
    declared — it is intentionally not derived from ``source_prefix`` because a source
    may declare CURIEs under multiple prefixes.
    """
    source_curies_fs = frozenset(source_curies)
    before_lookup = _lookup_table(before)
    after_cliques = cliques_set(after)
    before_cliques = cliques_set(before)

    pure_new: list[frozenset[str]] = []
    expanded: list[ExpandedClique] = []
    merged: list[MergedClique] = []

    for clique in after_cliques:
        source_in_clique = clique & source_curies_fs
        if not source_in_clique:
            continue
        non_source = clique - source_curies_fs

        if not non_source:
            pure_new.append(clique)
            continue

        before_cliques_set: set[frozenset[str]] = set()
        for curie in non_source:
            bc = before_lookup.get(curie)
            if bc is not None:
                before_cliques_set.add(bc)

        if len(before_cliques_set) == 0:
            pure_new.append(clique)
        elif len(before_cliques_set) == 1:
            (only_bc,) = before_cliques_set
            truly_added = source_in_clique - only_bc
            already_present = source_in_clique & only_bc
            expanded.append(
                ExpandedClique(
                    before_clique=only_bc,
                    added_source_curies=truly_added,
                    promoted_source_curies=already_present,
                    after_clique=clique,
                )
            )
        else:
            ordered = tuple(sorted(before_cliques_set, key=lambda c: min(c)))
            merged.append(
                MergedClique(
                    before_cliques=ordered,
                    source_curies_involved=source_in_clique,
                    after_clique=clique,
                )
            )

    return SourceImpactDiff(
        semantic_type=semantic_type,
        source_curies=source_curies_fs,
        pure_new_cliques=pure_new,
        expanded_cliques=expanded,
        merged_cliques=merged,
        before_clique_count=len(before_cliques),
        after_clique_count=len(after_cliques),
    )


def load_compendium(path: pathlib.Path | str) -> Iterator[dict]:
    """Stream clique dicts from a JSONL compendium file."""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def cliques_from_compendia(paths: Iterable[pathlib.Path | str]) -> frozenset[frozenset[str]]:
    """Materialise the set of cliques across one or more compendium JSONL files.

    Each clique is represented as a frozenset of its identifier CURIEs (the ``i`` field
    of each entry in ``clique["identifiers"]``). Used by the remote-compare mode of the
    source-impact report.
    """
    out: set[frozenset[str]] = set()
    for path in paths:
        for clique in load_compendium(path):
            members = frozenset(ident["i"] for ident in clique.get("identifiers", []))
            if members:
                out.add(members)
    return frozenset(out)
