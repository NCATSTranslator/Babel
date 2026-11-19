"""Analyse a concord file's cross-references.

A concord is a tab-separated ``subject<TAB>predicate<TAB>object`` file under
``<intermediate_root>/<pipeline>/concords/<SOURCE>``, and every row is fed to :func:`glom` as an
equivalence assertion. Rows are read with :func:`src.model.intermediates.read_concords`, the parser
every concord reader shares. That makes an *overused* xref target — one object claimed by many
distinct subjects — a merge hazard: `glom()` fuses every subject that names it into a single clique.

Overuse is what :func:`src.babel_utils.remove_overused_xrefs` drops (any target claimed by 2+
subjects), and what ``diseasephenotype.OVERUSE_FILTERED_CONCORDS`` opts a source into. This module
answers the question that decision needs: *which* targets are overused in a given concord, by how
much, and by whom. See ``docs/sources/AGENTS.md`` ("An OBO ``hasDbXref`` is not an equivalence")
for why a source's xrefs deserve auditing before they are trusted.

Labels come from the same per-prefix ``babel_downloads/<PREFIX>/labels`` files the build uses,
with an optional UMLS ``MRCONSO.RRF`` fallback for the classification vocabularies (ICD-10, ICD-9,
SNOMED) that Babel references but does not ingest as sources of their own — without those, an
audit of ICD-shaped overuse is a page of bare codes.
"""

from __future__ import annotations

import pathlib
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from src.model.intermediates import read_concords
from src.util import Text, get_logger

logger = get_logger(__name__)


# MRCONSO.RRF is pipe-separated and positional; these are the columns this module reads. These names
# exist only here -- five other modules index the same columns with bare integers -- so when the
# column layout moves to one place (https://github.com/NCATSTranslator/Babel/issues/1040), move these
# rather than adding a seventh private copy.
#
# Note that this module deliberately applies a *stricter* SUPPRESS rule than
# datahandlers/umls.check_mrconso_line(), which gates the build: that one rejects O and E and so
# keeps Y, while load_mrconso_labels() below keeps only N. The difference is intentional and was
# introduced with this module, not inherited -- a string you *display* should be filtered harder
# than a row you *join on*, and SUPPRESS=Y means "do not show this string". Nothing here touches the
# compendia; load_mrconso_labels() only fills label cells in an audit CSV.
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

# CURIE prefixes whose MRCONSO SAB is spelled differently enough that the startswith() heuristic
# below cannot bridge them. Kept to the aliases actually seen in Babel's concords rather than grown
# into a curated SAB map -- an audit wants a readable string, not an authoritative one.
_SAB_ALIASES = {"MIM": "OMIM"}


def _sab_token(prefix: str) -> str:
    """Reduce a CURIE prefix to the upper-cased token its MRCONSO SAB should start with.

    Upper-cased because SABs are, and a concord prefix need not be: without this `orphanet:558`
    never matches `SAB=ORPHANET`. The first underscore-delimited token is taken so DOID's
    release-stamped `SNOMEDCT_US_2025_09_01:` still finds `SAB=SNOMEDCT_US`.
    """
    token = prefix.upper().split("_")[0]
    return _SAB_ALIASES.get(token, token)


@dataclass
class OverusedTarget:
    """One xref target claimed by more than one subject in a concord file."""

    target: str
    subjects: set[str] = field(default_factory=set)

    @property
    def prefix(self) -> str:
        # get_prefix(), not get_prefix_or_none(): the latter upper-cases, which would report
        # "ORPHANET" in the audit's target_prefix column for a CURIE that reads "orphanet:558".
        return Text.get_prefix(self.target) if ":" in self.target else ""

    @property
    def subject_count(self) -> int:
        return len(self.subjects)


def find_overused_xref_targets(
    concord_path: pathlib.Path | str,
    min_subjects: int = 2,
    target_prefixes: Iterable[str] | None = None,
) -> list[OverusedTarget]:
    """Return every xref target in ``concord_path`` claimed by ``min_subjects`` or more subjects.

    Sorted most-claimed first, then by target, so re-runs diff cleanly. The default of 2 matches
    :func:`src.babel_utils.remove_overused_xrefs`, which drops a target the moment a second
    subject claims it -- so the default result is exactly the set of rows that filter would remove.

    ``target_prefixes`` (matched case-insensitively) restricts the result to targets in those
    namespaces. Combined with ``min_subjects=1`` that turns the audit into "every row targeting
    these prefixes", which is how a *categorical* prefix exclusion -- the other treatment a
    source's xrefs can get, e.g. ``EFO_EXCLUDED_XREF_PREFIXES`` -- is enumerated for review.
    """
    wanted_prefixes = {p.upper() for p in target_prefixes} if target_prefixes is not None else None
    subjects_by_target: dict[str, set[str]] = defaultdict(set)
    for subject, _predicate, target in read_concords(concord_path):
        subjects_by_target[target].add(subject)
    overused = [
        OverusedTarget(target=target, subjects=subjects)
        for target, subjects in subjects_by_target.items()
        if len(subjects) >= min_subjects
        and (wanted_prefixes is None or (Text.get_prefix_or_none(target) or "").upper() in wanted_prefixes)
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
    the row's ``SAB`` starts with the CURIE prefix's leading token, upper-cased (see
    :func:`_sab_token`) -- so ``ICD10:G11.4`` matches ``SAB=ICD10CM``, DOID's release-stamped
    ``SNOMEDCT_US_2025_09_01:267692008`` matches ``SAB=SNOMEDCT_US``, and ``orphanet:558`` matches
    ``SAB=ORPHANET`` rather than missing on case. That is a heuristic, not a curated SAB map: it is
    generous by design (an audit wants a readable string, not an authoritative one), and it can
    attach a label from a sibling vocabulary sharing a code space.
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
        wanted_by_code[local_id].append((_sab_token(prefix), curie))
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
            sab = cols[_MRCONSO_SAB].upper()
            rank = _MRCONSO_TTY_PRIORITY.index(tty)
            for prefix_token, curie in candidates:
                if not sab.startswith(prefix_token):
                    continue
                if curie not in best or rank < best[curie][0]:
                    best[curie] = (rank, cols[_MRCONSO_STR])
    logger.info("resolved %d of %d CURIEs from %s", len(best), len(needed_curies), mrconso_path)
    return {curie: label for curie, (_rank, label) in best.items()}


# Unknown prefixes


def known_curie_prefixes(biolink_prefixes: Iterable[str]) -> frozenset[str]:
    """Every prefix a concord CURIE may carry: ``biolink_prefixes`` plus every one in ``src/prefixes.py``.

    Pass the Biolink Model's prefix map for the build's ``biolink_version``
    (``get_biolink_prefix_map().prefix_map``). ``src/prefixes.py`` adds the few Babel uses that
    Biolink's map lacks (``icd11``, ``ICD0``, ``ICD10CM``, ``GARD``). Matching is exact, because ``glom()``
    compares CURIEs as strings: ``MEDGEN:C1`` and ``medgen:C1`` are two identifiers to it.
    """
    return frozenset(biolink_prefixes) | frozenset(Text.prefixmap.values())


@dataclass
class UnknownPrefix:
    """A prefix in one column of a concord that neither Biolink nor ``src/prefixes.py`` defines."""

    column: str  # "subject" or "object"
    prefix: str | None  # None for a CURIE with no colon at all
    rows: int
    example: str
    # The known prefix this one matches case-insensitively, if any. glom() compares CURIEs as
    # strings, so the two spellings never join each other, although the compendium writer later
    # fixes the case of a prefix Biolink registers for the clique's class (MONDO's 21,738 MEDGEN:
    # xrefs ship as medgen: in 2026jul22).
    case_variant_of: str | None = None


def find_unknown_prefixes(scan, known: frozenset[str]) -> list[UnknownPrefix]:
    """List the prefixes of ``scan`` (a ``ConcordRowScan`` made with ``count_prefixes=True``) not in ``known``.

    A CURIE with an unknown prefix joins nothing: no ids file carries it, and ``write_compendium()``
    drops it as unregistered. But it still reaches ``glom()``, so a target that two subjects cite
    merges them. The usual causes are a missing rename (``SCTID``, ``MIM``,
    ``SNOMEDCT_US_2025_09_01``), a mangled xref (``https``), and a vocabulary Babel doesn't use
    (UBERON's ``ZFA``-style xrefs to other anatomy ontologies). See docs/tools/CheckConcords.md.

    Sorted by column, then most rows first, then by prefix, so re-runs diff cleanly.
    """
    by_upper = {prefix.upper(): prefix for prefix in known}
    found = [
        UnknownPrefix(
            column=column,
            prefix=prefix,
            rows=rows,
            example=scan.prefix_examples[(column, prefix)],
            case_variant_of=by_upper.get(prefix.upper()) if prefix is not None else None,
        )
        for (column, prefix), rows in scan.prefixes.items()
        if prefix not in known
    ]
    found.sort(key=lambda u: (u.column != "subject", -u.rows, u.prefix or ""))
    return found
