"""Read Babel's intermediate files -- today, concord files.

This is the shared reader that https://github.com/NCATSTranslator/Babel/issues/736 proposes for
every intermediate format. It holds concords so far; ids files are still read by
``src.babel_utils.read_identifier_file()``, and the writers of both are still inline.

Concords
--------

A concord is a tab-separated ``subject<TAB>predicate<TAB>object`` file under
``<intermediate_root>/<pipeline>/concords/<SOURCE>``, and every row is fed to ``glom()`` as an
equivalence assertion.

:func:`read_concords` / :func:`parse_concord_line` are the one definition of a valid concord row,
and every reader of a concord goes through them: the compendium builders, ``glom_from_files()``,
the overuse audit in :mod:`src.model.concords`, and ``write_concord_metadata()``, which runs in the
rule that wrote the concord and so catches a bad row minutes into a build rather than hours later in
a compendium rule. A row that isn't valid raises :class:`MalformedConcordRowError`; nothing skips
it. That is #736's "decide the malformed-line contract once" for concords. The readers used to
disagree -- ``glom_from_files()`` silently dropped short rows, the protein loader crashed on them
with an ``IndexError``, and the metadata writer logged a warning nobody read -- so the same bad row
could be dropped from one pipeline and fatal in another.

The DuckDB export (``src/exporters/duckdb_exporters.py``) bulk-loads concords with ``read_csv``
rather than this parser, for speed; its strict mode is a backstop that checks only the column
count. ``babel-check-concords`` runs this parser over a build's concords, including a published
build's over HTTP.

Metadata sidecars
-----------------

A ``concords/`` or ``ids/`` directory also holds YAML metadata describing its files.
:func:`metadata_subject_filename` / :func:`is_metadata_sidecar` are the one definition of which file
is a sidecar rather than data; the DuckDB export, ``babel-check-concords`` and the source-impact
report's concord scan all use them, so they agree on which files are concords.
"""

from __future__ import annotations

import pathlib
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

# Concords are written and read as UTF-8. Every reader names the encoding rather than taking the
# locale's default, so the build, ``babel-check-concords`` and the DuckDB export (which reads UTF-8)
# decode the same bytes the same way on any host.
CONCORD_ENCODING = "utf-8"

# Intermediate metadata sidecar files are named ``metadata-<subject>.yaml`` (describing a sibling
# file) or a bare ``metadata.yaml`` (describing the directory it lives in). Matched
# case-insensitively, as the DuckDB export always has.
METADATA_FILENAME_PREFIX = "metadata-"
METADATA_FILENAME_SUFFIX = ".yaml"
METADATA_DIRECTORY_FILENAME = "metadata.yaml"


def metadata_subject_filename(filename: str) -> str | None:
    """Return the name of the file a metadata sidecar describes, or None if ``filename`` is not one.

    ``metadata-<subject>.yaml`` describes the sibling file ``<subject>``; a bare ``metadata.yaml``
    describes the directory it lives in, so its own name is returned unchanged. Any other file in a
    ``concords/`` or ``ids/`` directory -- including some other ``*.yaml`` -- is data.
    """
    lower_filename = filename.lower()
    if lower_filename.startswith(METADATA_FILENAME_PREFIX) and lower_filename.endswith(METADATA_FILENAME_SUFFIX):
        return filename[len(METADATA_FILENAME_PREFIX) : -len(METADATA_FILENAME_SUFFIX)]
    if lower_filename == METADATA_DIRECTORY_FILENAME:
        return filename
    return None


def is_metadata_sidecar(filename: str) -> bool:
    """True if ``filename`` (a bare name, not a path) is a metadata sidecar rather than a data file."""
    return metadata_subject_filename(filename) is not None


class MalformedConcordRowError(ValueError):
    """A concord row that isn't three non-empty, unpadded, tab-separated columns.

    ``reason`` is a short, stable category (``"2 columns"``, ``"empty column"``,
    ``"whitespace around a column"``) so a scan can tally rejects by kind; the message also names the
    file, the 1-based line number and the raw line.
    """

    def __init__(self, filename, line_number: int, line: str, reason: str):
        self.filename = filename
        self.line_number = line_number
        self.line = line
        self.reason = reason
        super().__init__(f"{filename}:{line_number} is not a valid concord row ({reason}): {line!r}")


def parse_concord_line(line: str, filename, line_number: int) -> tuple[str, str, str]:
    """Split one concord line into ``(subject, predicate, object)``, or raise.

    Only the line terminator is removed before splitting. ``line.strip()`` -- what every reader used
    to do -- also eats the tabs that delimit an empty first or last column, so ``"A\\teq\\t\\n"`` was
    counted as two columns and ``"A\\teq\\tB\\t\\n"`` as three (while DuckDB's ``read_csv`` sees
    four). Splitting the unstripped line gives the column count every other reader sees.

    A column that is empty or has whitespace around it is rejected rather than cleaned: no CURIE or
    predicate contains either, so such a column means the writer is broken, and silently trimming it
    would also make the build disagree with the DuckDB export, which reads columns verbatim.
    ``babel-check-concords`` over the 2025dec11 build's 224 million concord rows found 478 that this
    rejects, from two writers: EFO xrefs with a padded literal, and PubMed DOIs ending in a space or
    tab. ``EFOgraph.get_xrefs()`` now strips its literals; PubMed is now read from a pubmed2db
    export whose reader repairs or skips any DOI containing whitespace. The readers had been hiding
    both with ``line.strip()``. See ``docs/tools/CheckConcords.md`` for the full scan and the
    2026jul22 cross-check before loosening this.

    ``filename`` and ``line_number`` are only used in the error message.
    """
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) != 3:
        raise MalformedConcordRowError(filename, line_number, line, f"{len(fields)} columns")
    for column in fields:
        if not column:
            raise MalformedConcordRowError(filename, line_number, line, "empty column")
        if column[0].isspace() or column[-1].isspace():
            raise MalformedConcordRowError(filename, line_number, line, "whitespace around a column")
    return fields[0], fields[1], fields[2]


def read_concords(concord_path: pathlib.Path | str) -> Iterator[tuple[str, str, str]]:
    """Yield every row of a concord file as ``(subject, predicate, object)``.

    Raises :class:`MalformedConcordRowError` on the first invalid row (see
    :func:`parse_concord_line`); blank lines are invalid too, since no concord writer emits one.
    """
    with open(concord_path, encoding=CONCORD_ENCODING) as inf:
        for line_number, line in enumerate(inf, start=1):
            yield parse_concord_line(line, concord_path, line_number)


def read_concord_pairs(concord_path: pathlib.Path | str) -> Iterator[tuple[str, str]]:
    """Yield every row of a concord file as a ``(subject, object)`` pair, in file order.

    This is the shape ``glom()`` takes: it treats every row as an equivalence, so the predicate is
    dropped. Two choices here keep a large concord's memory down, and both are worth keeping when
    building pairs some other way:

    * **A pair is a 2-tuple, not a 2-set or a 2-list.** ``glom()`` accepts any of them and
      ``remove_overused_xrefs()`` unpacks ``for k, v``, but a 2-tuple is 64 bytes held in a list,
      a 2-set 224, and a list of 2-lists copied into a list of 2-sets (what the readers built
      before) 305 -- measured with ``tracemalloc`` over a million pairs on Python 3.13, CURIE
      strings excluded. ``UNICHEM_PUBCHEM.COMPOUND`` alone has 116 million rows.
    * **It is a generator, so a caller that needs no whole-file step can pass it straight to
      ``glom()``** and never hold the file's pairs at all. That is safe only when nothing between
      the read and the merge depends on the clique state: ``glom()`` mutates it pair by pair, so a
      filter that consults it (anatomy's and process's UMLS gate) must see the file read into a
      list first, as must ``remove_overused_xrefs()``, which counts the whole file.

      Streaming gives up one thing: the file is no longer validated before any of it is merged. A
      malformed row raises :class:`MalformedConcordRowError` partway through ``glom()``, after the
      rows above it are already merged. That is harmless while the error aborts the build, but a
      caller that catches it and keeps going (a replay or report tool reusing a builder) must
      discard the clique dict, which is left half-merged with no sign of it -- or read the file into
      a list first, which validates every row before ``glom()`` sees one.

    File order is kept either way, and it matters: ``glom()``'s ``unique_prefixes`` keeps whichever
    competing pair it sees first (#902).
    """
    for subject, _predicate, obj in read_concords(concord_path):
        yield subject, obj


@dataclass
class ConcordRowScan:
    """What :func:`scan_concord_lines` found in one concord file."""

    filename: str
    rows: int = 0
    rejects: Counter = field(default_factory=Counter)
    # The first rejected line for each reason, as (line_number, line), so a report can show one.
    examples: dict[str, tuple[int, str]] = field(default_factory=dict)

    @property
    def rejected(self) -> int:
        return sum(self.rejects.values())


def scan_concord_lines(lines: Iterable[str], filename: str) -> ConcordRowScan:
    """Run :func:`parse_concord_line` over every line, tallying rejects instead of raising.

    This is how to find out, before a build does, whether a set of concords would trip the
    parser -- and which rows, by kind.
    """
    scan = ConcordRowScan(filename=filename)
    for line_number, line in enumerate(lines, start=1):
        scan.rows += 1
        try:
            parse_concord_line(line, filename, line_number)
        except MalformedConcordRowError as err:
            scan.rejects[err.reason] += 1
            scan.examples.setdefault(err.reason, (line_number, line))
    return scan
