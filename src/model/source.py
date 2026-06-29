"""Discover how a Babel source contributes to the build outputs.

Given a source name like "EMAPA", walks every
``<intermediate_root>/<pipeline>/ids/<name>`` and
``<intermediate_root>/<pipeline>/concords/<name>`` and assembles a structured
description that the source-impact report tool can render.

A Babel source can vary along three axes simultaneously, so every aggregate is a
collection:

- multiple pipelines (e.g., MESH contributes to anatomy, chemical, disease)
- multiple biolink types within a pipeline (UBERON declares both
  ``biolink:AnatomicalEntity`` and ``biolink:GrossAnatomicalStructure`` in one ids file)
- multiple prefixes per ids file (rare but supported)

.. note::
    PR #742 (source-impact report tool) also uses the old ``semantic_type`` / ``by_semantic_type``
    naming in its own variables (``SEMANTIC_TYPE_CONFIG``, ``diffs_by_semantic_type``,
    ``--semantic-types`` CLI flag). Update those when rebasing #742 onto this branch.
"""

from __future__ import annotations

import pathlib
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property


def _prefix_of(curie: str) -> str:
    return curie.split(":", 1)[0]


def scan_concords_for_curies(
    concords_dir: pathlib.Path | str,
    source_curies: Iterable[str],
) -> list[tuple[str, str, str, str]]:
    """Scan every concord file in a directory tree for rows touching any source CURIE.

    Returns ``(subject, predicate, object, asserted_by)`` tuples where ``asserted_by`` is
    the path of the concord file relative to ``concords_dir`` — the source that *declared*
    the cross-reference. A source's cross-references frequently live in *another* source's
    concord file (e.g. EMAPA's own concord is empty, but UBERON's concord carries
    ``UBERON:… xref EMAPA:…`` rows), so this scans every file in the directory tree rather
    than only the source's own concord. Subdirectories are included (e.g.
    ``chemicals/concords/UNICHEM/UNICHEM_*`` files). Metadata sidecars
    (``metadata-*`` / ``*.yaml``) are skipped.
    """
    concords_dir = pathlib.Path(concords_dir)
    source_set = frozenset(source_curies)
    rows: list[tuple[str, str, str, str]] = []
    if not concords_dir.exists():
        return rows
    for path in sorted(concords_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("metadata-") or path.name.endswith(".yaml"):
            continue
        asserted_by = str(path.relative_to(concords_dir))
        with path.open() as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                subject, predicate, obj = parts[0], parts[1], parts[2]
                if subject in source_set or obj in source_set:
                    rows.append((subject, predicate, obj, asserted_by))
    return rows


@dataclass
class PipelineContribution:
    """One source's contribution within a single babel_pipeline directory."""

    pipeline: str
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
    """Aggregated description of a source across every babel_pipeline it touches."""

    name: str
    by_pipeline: dict[str, PipelineContribution]

    @property
    def pipelines(self) -> frozenset[str]:
        return frozenset(self.by_pipeline.keys())

    @property
    def prefixes(self) -> frozenset[str]:
        out: set[str] = set()
        for pc in self.by_pipeline.values():
            out.update(pc.curies_by_prefix.keys())
        return frozenset(out)

    @property
    def declared_biolink_types(self) -> frozenset[str]:
        out: set[str] = set()
        for pc in self.by_pipeline.values():
            out.update(pc.declared_biolink_types)
        return frozenset(out)

    @property
    def declared_type_counts(self) -> dict[str, int]:
        """Total CURIEs declaring each biolink type, summed across all pipelines.

        Rows without a declared type are bucketed under the empty string (mirroring
        ``PipelineContribution.declared_type_counts``).
        """
        counts: dict[str, int] = defaultdict(int)
        for pc in self.by_pipeline.values():
            for declared, count in pc.declared_type_counts.items():
                counts[declared] += count
        return dict(counts)

    @property
    def total_identifier_count(self) -> int:
        return sum(len(pc.all_curies) for pc in self.by_pipeline.values())

    @property
    def total_concord_row_count(self) -> int:
        return sum(len(pc.concord_pairs) for pc in self.by_pipeline.values())


def discover_source(name: str, intermediate_root: pathlib.Path | str) -> SourceContribution:
    """Discover where a named source contributes across the intermediate build outputs.

    Walks ``<intermediate_root>/<pipeline>/ids/<name>`` and
    ``<intermediate_root>/<pipeline>/concords/<name>`` for every pipeline subdirectory
    and records a PipelineContribution wherever the source has either file. Returns a
    SourceContribution; callers can check ``by_pipeline`` to detect a source name that is
    not present anywhere.
    """
    intermediate_root = pathlib.Path(intermediate_root)
    if not intermediate_root.exists():
        raise FileNotFoundError(f"Intermediate root does not exist: {intermediate_root}")
    by_pipeline: dict[str, PipelineContribution] = {}
    for pipeline_dir in sorted(intermediate_root.iterdir()):
        if not pipeline_dir.is_dir():
            continue
        ids_path = pipeline_dir / "ids" / name
        concords_path = pipeline_dir / "concords" / name
        has_ids = ids_path.exists()
        has_concords = concords_path.exists()
        if not (has_ids or has_concords):
            continue
        by_pipeline[pipeline_dir.name] = PipelineContribution(
            pipeline=pipeline_dir.name,
            ids_path=ids_path if has_ids else None,
            concords_path=concords_path if has_concords else None,
        )
    return SourceContribution(name=name, by_pipeline=by_pipeline)
