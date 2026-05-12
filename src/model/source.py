"""Discover how a Babel source contributes to the build outputs.

Given a source name like "EMAPA", walks every
``<intermediate_root>/<semantic_type>/ids/<name>`` and
``<intermediate_root>/<semantic_type>/concords/<name>`` and assembles a structured
description that the source-impact report tool can render.

A Babel source can vary along three axes simultaneously, so every aggregate is a
collection:

- multiple semantic types (e.g., MESH contributes to anatomy, chemical, disease)
- multiple biolink types within a semantic type (UBERON declares both
  ``biolink:AnatomicalEntity`` and ``biolink:GrossAnatomicalStructure`` in one ids file)
- multiple prefixes per ids file (rare but supported)
"""

from __future__ import annotations

import pathlib
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property


def _prefix_of(curie: str) -> str:
    return curie.split(":", 1)[0]


@dataclass
class SemanticTypeContribution:
    """One source's contribution within a single semantic type."""

    semantic_type: str
    ids_path: pathlib.Path | None
    concords_path: pathlib.Path | None

    @cached_property
    def _ids_rows(self) -> list[tuple[str, str | None]]:
        if self.ids_path is None or not self.ids_path.exists():
            return []
        rows: list[tuple[str, str | None]] = []
        with self.ids_path.open() as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if not parts or not parts[0]:
                    continue
                curie = parts[0]
                declared_type = parts[1] if len(parts) > 1 and parts[1] else None
                rows.append((curie, declared_type))
        return rows

    @cached_property
    def all_curies(self) -> frozenset[str]:
        return frozenset(curie for curie, _ in self._ids_rows)

    @cached_property
    def curies_by_prefix(self) -> dict[str, frozenset[str]]:
        buckets: dict[str, set[str]] = defaultdict(set)
        for curie, _ in self._ids_rows:
            buckets[_prefix_of(curie)].add(curie)
        return {k: frozenset(v) for k, v in buckets.items()}

    @cached_property
    def declared_types_by_curie(self) -> dict[str, str | None]:
        return {curie: declared for curie, declared in self._ids_rows}

    @cached_property
    def declared_biolink_types(self) -> frozenset[str]:
        return frozenset(t for t in self.declared_types_by_curie.values() if t)

    @cached_property
    def declared_type_counts(self) -> dict[str, int]:
        """How many CURIEs in this source's ids file declare each biolink type.

        Rows without a declared type are bucketed under the empty string so callers can
        report "undeclared" explicitly.
        """
        counts: dict[str, int] = defaultdict(int)
        for declared in self.declared_types_by_curie.values():
            counts[declared or ""] += 1
        return dict(counts)

    @cached_property
    def concord_pairs(self) -> list[tuple[str, str, str]]:
        if self.concords_path is None or not self.concords_path.exists():
            return []
        triples: list[tuple[str, str, str]] = []
        with self.concords_path.open() as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                triples.append((parts[0], parts[1], parts[2]))
        return triples

    @cached_property
    def concord_partner_prefix_counts(self) -> dict[str, int]:
        """Count of partner-prefix occurrences across the concord file.

        For each row in the concord file, contributes one count to whichever endpoint's
        prefix is *not* one of the source's own (as declared in the ids file). This
        isolates how many bridges go to each external vocabulary.
        """
        own_prefixes = set(self.curies_by_prefix.keys())
        counts: dict[str, int] = defaultdict(int)
        for c1, _, c2 in self.concord_pairs:
            for c in (c1, c2):
                prefix = _prefix_of(c)
                if prefix not in own_prefixes:
                    counts[prefix] += 1
        return dict(counts)


@dataclass
class SourceContribution:
    """Aggregated description of a source across every semantic type it touches."""

    name: str
    by_semantic_type: dict[str, SemanticTypeContribution]

    @property
    def semantic_types(self) -> frozenset[str]:
        return frozenset(self.by_semantic_type.keys())

    @property
    def prefixes(self) -> frozenset[str]:
        out: set[str] = set()
        for stc in self.by_semantic_type.values():
            out.update(stc.curies_by_prefix.keys())
        return frozenset(out)

    @property
    def declared_biolink_types(self) -> frozenset[str]:
        out: set[str] = set()
        for stc in self.by_semantic_type.values():
            out.update(stc.declared_biolink_types)
        return frozenset(out)

    @property
    def total_identifier_count(self) -> int:
        return sum(len(stc.all_curies) for stc in self.by_semantic_type.values())

    @property
    def total_concord_row_count(self) -> int:
        return sum(len(stc.concord_pairs) for stc in self.by_semantic_type.values())


def discover_source(name: str, intermediate_root: pathlib.Path | str) -> SourceContribution:
    """Discover where a named source contributes across the intermediate build outputs.

    Walks ``<intermediate_root>/<semantic_type>/ids/<name>`` and
    ``<intermediate_root>/<semantic_type>/concords/<name>`` for every semantic-type
    subdirectory and records a SemanticTypeContribution wherever the source has either
    file. Returns a SourceContribution; callers can check ``by_semantic_type`` to detect
    a source name that is not present anywhere.
    """
    intermediate_root = pathlib.Path(intermediate_root)
    if not intermediate_root.exists():
        raise FileNotFoundError(f"Intermediate root does not exist: {intermediate_root}")
    by_st: dict[str, SemanticTypeContribution] = {}
    for st_dir in sorted(intermediate_root.iterdir()):
        if not st_dir.is_dir():
            continue
        ids_path = st_dir / "ids" / name
        concords_path = st_dir / "concords" / name
        has_ids = ids_path.exists()
        has_concords = concords_path.exists()
        if not (has_ids or has_concords):
            continue
        by_st[st_dir.name] = SemanticTypeContribution(
            semantic_type=st_dir.name,
            ids_path=ids_path if has_ids else None,
            concords_path=concords_path if has_concords else None,
        )
    return SourceContribution(name=name, by_semantic_type=by_st)
