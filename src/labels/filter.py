import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_instance: Optional["LabelFilter"] = None


def get_label_filter() -> "LabelFilter":
    global _instance, logger
    if _instance is None:
        # Deferred import: label_filter.py sits near the top of the module graph,
        # so we defer util to avoid triggering config loading at import time.
        from src.util import get_config, get_logger

        logger = get_logger(__name__)
        config = get_config()
        filter_file = Path(config.get("input_directory", "input_data")) / "obsolete_labels.yaml"
        _instance = LabelFilter(filter_file)
    return _instance


@dataclass
class _FilterEntry:
    reason: str
    only_for_types: frozenset  # empty = applies to all Biolink types; non-empty = type-scoped
    sources_seen: list  # documentation only; records which upstream sources emit this term
    action: str = "remove"  # "remove" = drop term; "warn" = keep but log
    _exact: str | None = field(default=None, repr=False)  # lowercased label text
    _partial: bool = field(default=False, repr=False)  # True → substring match; False → whole-label
    _pattern: re.Pattern | None = field(default=None, repr=False)

    def matches(self, label_lower: str) -> bool:
        if self._pattern is not None:
            return bool(self._pattern.search(label_lower))
        if self._exact is not None:
            return self._exact in label_lower if self._partial else self._exact == label_lower
        return False


class LabelFilter:
    """Filter obsolete labels and synonyms from Babel output.

    Loaded from input_data/obsolete_labels.yaml. Each entry carries its own action:

    action="remove" (default): drop the term — should_suppress() returns True and the caller skips it.
    action="warn":             keep the term but log a warning — should_suppress() returns False.

    A warning is always emitted on match so build logs are searchable regardless of action.
    """

    def __init__(self, filter_file: Path):
        self._entries: list[_FilterEntry] = []
        self.filtered_count: int = 0
        self.filtered_by_source: dict[str, int] = {}
        self._load(filter_file)

    def _load(self, path: Path) -> None:
        if not path.exists():
            logger.warning(f"LabelFilter: filter file not found at {path}; no labels will be filtered.")
            return
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for raw in data.get("obsolete_labels", []):
            reason = raw.get("reason", "(no reason given)")
            only_for_types = frozenset(raw.get("only_for_types", []))
            sources_seen = raw.get("sources_seen", [])
            partial = bool(raw.get("partial", False))
            action = raw.get("action", "remove")
            if action not in ("remove", "warn"):
                logger.warning(f"LabelFilter: invalid action {action!r} in {path}; defaulting to 'remove'")
                action = "remove"
            if "label" in raw:
                self._entries.append(
                    _FilterEntry(
                        reason=reason,
                        only_for_types=only_for_types,
                        sources_seen=sources_seen,
                        action=action,
                        _exact=raw["label"].lower(),
                        _partial=partial,
                    )
                )
            elif "pattern" in raw:
                self._entries.append(
                    _FilterEntry(
                        reason=reason,
                        only_for_types=only_for_types,
                        sources_seen=sources_seen,
                        action=action,
                        _pattern=re.compile(raw["pattern"], re.IGNORECASE),
                    )
                )
            else:
                logger.warning(
                    f"LabelFilter: skipping malformed entry in {path} (no 'label' or 'pattern' key): {raw!r}"
                )
        logger.info(f"LabelFilter: loaded {len(self._entries)} entries from {path}")

    def should_suppress(self, label: str, source: str, node_types: list | None = None) -> bool:
        """Return True if label matches a 'remove' entry; False if it matches a 'warn' entry or no entry.

        A warning is always emitted on any match so build logs are searchable and the
        originating data source can be identified and reported.

        label:      the label or synonym text to check.
        source:     human-readable description of where the label came from (e.g. "UMLS labels file").
        node_types: full Biolink ancestor list for the node (most-specific first), used to honour
                    type-scoped filter entries (only_for_types in the YAML).  Pass None to skip
                    type-scope gating — entries with an empty only_for_types will still match.
        """
        if not label:
            return False
        label_lower = label.lower()
        for entry in self._entries:
            # Type-scoped check: skip entries whose only_for_types doesn't overlap this node's types.
            # When node_types=None we don't know the type, so we skip scoped entries to avoid false positives.
            if entry.only_for_types and (node_types is None or not any(t in entry.only_for_types for t in node_types)):
                continue
            if entry.matches(label_lower):
                logger.warning(
                    f"Obsolete label '{label}' (reason: {entry.reason}) found in {source}; action={entry.action}"
                )
                self.filtered_count += 1
                self.filtered_by_source[source] = self.filtered_by_source.get(source, 0) + 1
                return entry.action == "remove"
        return False
