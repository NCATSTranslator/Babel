"""Analyse a concord file's cross-references.

A concord is a tab-separated ``subject<TAB>predicate<TAB>object`` file under
``<intermediate_root>/<pipeline>/concords/<SOURCE>``, and every row is fed to :func:`glom` as an
equivalence assertion. That makes an *overused* xref target — one object claimed by many distinct
subjects — a merge hazard: `glom()` fuses every subject that names it into a single clique.

Overuse is what :func:`src.babel_utils.remove_overused_xrefs` drops (any target claimed by 2+
subjects), and what ``diseasephenotype.OVERUSE_FILTERED_CONCORDS`` opts a source into. This module
answers the question that decision needs: *which* targets are overused in a given concord, by how
much, and by whom. See ``docs/sources/CLAUDE.md`` ("An OBO ``hasDbXref`` is not an equivalence")
for why a source's xrefs deserve auditing before they are trusted.

Labels come from the same per-prefix ``babel_downloads/<PREFIX>/labels`` files the build uses,
with an optional UMLS ``MRCONSO.RRF`` fallback for the classification vocabularies (ICD-10, ICD-9,
SNOMED) that Babel references but does not ingest as sources of their own — without those, an
audit of ICD-shaped overuse is a page of bare codes.
"""

from __future__ import annotations

import pathlib
from collections import defaultdict
from dataclasses import dataclass, field

from src.util import Text, get_logger

logger = get_logger(__name__)

# MRCONSO.RRF is pipe-separated and positional; these are the columns this module reads.
_MRCONSO_LAT = 1
_MRCONSO_SAB = 11
_MRCONSO_TTY = 12
_MRCONSO_CODE = 13
_MRCONSO_STR = 14
_MRCONSO_SUPPRESS = 16

# MRCONSO term types worth taking as a preferred label, best first. PT is the source vocabulary's
# preferred term; PN a "metathesaurus preferred name"; ET an entry term, which is the only thing
# some ICD-10-CM codes carry.
_MRCONSO_TTY_PRIORITY = ("PT", "PN", "ET")


@dataclass
class OverusedTarget:
    """One xref target claimed by more than one subject in a concord file."""

    target: str
    subjects: set[str] = field(default_factory=set)

    @property
    def prefix(self) -> str:
        return Text.get_prefix_or_none(self.target) or ""

    @property
    def subject_count(self) -> int:
        return len(self.subjects)


def find_overused_xref_targets(concord_path: pathlib.Path | str, min_subjects: int = 2) -> list[OverusedTarget]:
    """Return every xref target in ``concord_path`` claimed by ``min_subjects`` or more subjects.

    Sorted most-claimed first, then by target, so re-runs diff cleanly. The default of 2 matches
    :func:`src.babel_utils.remove_overused_xrefs`, which drops a target the moment a second
    subject claims it -- so the default result is exactly the set of rows that filter would remove.
    """
    subjects_by_target: dict[str, set[str]] = defaultdict(set)
    with open(concord_path) as inf:
        for line_no, line in enumerate(inf, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                raise RuntimeError(f"{concord_path}:{line_no} is not a valid concord row (got {len(parts)} columns)")
            subject, _predicate, target = (p.strip() for p in parts)
            subjects_by_target[target].add(subject)
    overused = [
        OverusedTarget(target=target, subjects=subjects)
        for target, subjects in subjects_by_target.items()
        if len(subjects) >= min_subjects
    ]
    overused.sort(key=lambda o: (-o.subject_count, o.target))
    return overused


def load_mrconso_labels(
    mrconso_path: pathlib.Path | str, needed_curies: set[str], language: str = "ENG"
) -> dict[str, str]:
    """Resolve labels for ``needed_curies`` from a UMLS ``MRCONSO.RRF``, one streaming pass.

    Babel references ICD-10/ICD-9/SNOMED codes through other sources' xrefs but never ingests
    them as sources, so they have no ``babel_downloads/<PREFIX>/labels`` file and an audit shows
    them as bare codes. MRCONSO carries their strings.

    A CURIE is matched to an MRCONSO row when the row's ``CODE`` equals the CURIE's local id and
    the row's ``SAB`` starts with the CURIE prefix's first underscore-delimited token -- so
    ``ICD10:G11.4`` matches ``SAB=ICD10CM``, and DOID's version-stamped
    ``SNOMEDCT_US_2025_09_01:267692008`` matches ``SAB=SNOMEDCT_US``. That is a heuristic, not a
    curated SAB map: it is generous by design (an audit wants a readable string, not an
    authoritative one), and it can attach a label from a sibling vocabulary sharing a code space.
    Suppressed rows are skipped, only ``language`` rows are considered (MRCONSO is multilingual,
    and without this filter a Dutch or Spanish string wins the race for many ICD-10 codes), and
    the best available TTY wins (see ``_MRCONSO_TTY_PRIORITY``).
    """
    # Indexed by local id alone: an MRCONSO row is looked up by CODE, then its SAB is checked
    # against the candidate CURIEs' prefixes. Indexing by (prefix, code) instead would need the
    # exact SAB spelling up front, which is the thing we are deliberately not hard-coding.
    wanted_by_code: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for curie in needed_curies:
        prefix, _, local_id = curie.partition(":")
        if not local_id:
            continue
        wanted_by_code[local_id].append((prefix.split("_")[0], curie))
    if not wanted_by_code:
        return {}

    best: dict[str, tuple[int, str]] = {}
    with open(mrconso_path, encoding="utf-8", errors="replace") as inf:
        for line in inf:
            cols = line.split("|")
            # Keep only SUPPRESS=N. The other values are all forms of "do not show this string":
            # O (obsolete), E (editor-suppressed), Y (suppressible). Retired SNOMED concepts that
            # DOID still xrefs are the common case here, and surfacing their obsolete strings as
            # current labels would be worse than leaving the cell empty.
            if len(cols) <= _MRCONSO_SUPPRESS or cols[_MRCONSO_SUPPRESS] != "N":
                continue
            if cols[_MRCONSO_LAT] != language:
                continue
            tty = cols[_MRCONSO_TTY]
            if tty not in _MRCONSO_TTY_PRIORITY:
                continue
            candidates = wanted_by_code.get(cols[_MRCONSO_CODE])
            if not candidates:
                continue
            sab = cols[_MRCONSO_SAB]
            rank = _MRCONSO_TTY_PRIORITY.index(tty)
            for prefix_token, curie in candidates:
                if not sab.startswith(prefix_token):
                    continue
                if curie not in best or rank < best[curie][0]:
                    best[curie] = (rank, cols[_MRCONSO_STR])
    logger.info("resolved %d of %d CURIEs from %s", len(best), len(needed_curies), mrconso_path)
    return {curie: label for curie, (_rank, label) in best.items()}
