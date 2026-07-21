"""Detect encoding damage in labels and synonyms.

Babel reads several sources with a single-byte codec (PUBCHEM.COMPOUND and UNII are read as
`latin-1`/`windows-1252` in `src/datahandlers/`). When the source bytes are really UTF-8, that
misread produces mojibake: `é` becomes `Ã©`, `–` becomes `â€"`. The damage is invisible to every
downstream check because mojibake *is* valid UTF-8 -- just wrong text.

`find_encoding_issue()` is the detector; `check_encoding()` is the raising wrapper the pipeline
calls at the points where labels and synonyms are loaded (see `src/node.py`). Both are cheap enough
to run over every string in a full build -- see the `isascii()` note in `find_encoding_issue()`.
"""

import json
import re
from pathlib import Path

from src.util import get_config, get_logger

logger = get_logger(__name__)

# Characters that never legitimately appear in a label or synonym:
#   \x00-\x08, \x0b-\x1f  C0 controls, minus tab (\x09) and newline (\x0a). Those two are field and
#                         record separators, and a label is allowed to contain a tab:
#                         `NodeFactory.load_extra_labels()` in src/node.py splits with maxsplit=1
#                         precisely so that such a label survives, and a test pins that behaviour.
#   \x7f-\x9f             DEL and the C1 controls. Nothing emits these deliberately; in practice
#                         they are cp1252 bytes 0x80-0x9f (curly quotes, en-dashes) that were
#                         decoded as latin-1 instead, so they are themselves an encoding-bug tell.
#   �                U+FFFD REPLACEMENT CHARACTER -- unambiguous proof of a lossy decode.
#   ﻿                U+FEFF BOM left embedded in the text rather than consumed by the reader.
_SUSPECT = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f�﻿]")

# The ASCII subset of the above. Needed separately because `str.isprintable()` -- the cheap gate on
# the ASCII fast path -- also rejects tab and newline, which as noted are not damage.
_ASCII_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

_allowlist: frozenset[str] | None = None


def _get_allowlist() -> frozenset[str]:
    """Load (once) the set of strings that look damaged but are known to be correct."""
    global _allowlist
    if _allowlist is None:
        _allowlist = frozenset(get_config().get("encoding_check_allowlist", []) or [])
        if _allowlist:
            logger.info(f"Encoding check: loaded {len(_allowlist)} allowlisted strings.")
    return _allowlist


def find_encoding_issue(text: str) -> str | None:
    """Return a short human-readable reason if `text` looks encoding-damaged, else None.

    Two signals:

    1.  A successful single-byte -> UTF-8 round-trip that changes the string. This is the classic
        mojibake test (the core of what `ftfy` does): if the text can be encoded back to the codec
        that damaged it *and* those bytes decode as valid UTF-8 into something different, then it
        was UTF-8 misread as that codec. Legitimate non-ASCII text fails one of those two steps --
        `α` in `Nα-acetyltransferase` has no cp1252 byte, and `Ménière disease` re-encodes to bytes
        that aren't valid UTF-8 -- and so is never flagged.
    2.  A character from `_SUSPECT`: a control character, a replacement character, or a stray BOM.

    The round-trip runs first because it is the only signal that can name the *original* text, which
    is what makes the report actionable. Both codecs Babel actually reads with are tried:
    `datacollect.py` uses latin-1 and `unii.py` uses windows-1252, and they damage text differently
    (latin-1 turns bytes 0x80-0x9f into C1 controls, cp1252 into printable punctuation), so trying
    only one leaves the other diagnosable but unrepairable.

    The `isascii()` gate at the top matters for cost, not correctness: the overwhelming majority of
    biomedical labels are pure ASCII, and `str.isascii()` is a C-level scan that exits in
    nanoseconds. Only non-ASCII strings pay for the round-trip or the regex, which is what makes it
    affordable to check every label and synonym in a full build. ASCII text can still be damaged --
    a C0 control or DEL is never legitimate -- so the fast path falls through to `isprintable()`,
    also C-level, and only pays for a regex on the rare string that fails it.
    """
    if text.isascii():
        if text.isprintable():
            return None
        # isprintable() also rejects tab and newline, so confirm with the range that excludes them.
        return "contains a control character" if _ASCII_CONTROL.search(text) else None
    for codec in ("cp1252", "latin-1"):
        try:
            repaired = text.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue  # Doesn't round-trip through this codec; try the next.
        if repaired != text:
            return f"looks like mojibake (UTF-8 read as {codec}); probably meant to be {repaired!r}"
    if _SUSPECT.search(text):
        return "contains a control, replacement or byte-order-mark character"
    return None


def check_encoding(text: str, curie: str, source: str) -> None:
    """Raise RuntimeError if `text` is encoding-damaged.

    `curie` and `source` are only used to build the error message, but they are what makes it
    actionable -- the message has to say which identifier in which file to go and look at.

    Set `encoding_check_enabled: false` in `config.yaml` to disable the check entirely, or add a
    specific string to `encoding_check_allowlist` to exempt it.
    """
    if not text or not get_config().get("encoding_check_enabled", True):
        return
    if text in _get_allowlist():
        return
    reason = find_encoding_issue(text)
    if reason is None:
        return
    raise RuntimeError(
        f"Encoding issue in {source} for {curie}: {reason}. The text was {text!r}. "
        f"Fix the source ingest, or -- if this text is actually correct -- add it to "
        f"encoding_check_allowlist in config.yaml."
    )


def scan_file(path: Path) -> list[tuple[int, str, str, str]]:
    """Scan a labels, synonyms, or JSONL file and return every encoding issue found.

    Unlike `check_encoding()` this reports rather than raises, so it can survey a whole download
    directory in one pass. Returns `(line_number, curie, text, reason)` tuples.

    Supported shapes, chosen by what the line looks like rather than by the filename, because
    Babel's labels and synonyms files have no extension:
      - `<curie>\\t<label>`                    (a `labels` file)
      - `<curie>\\t<predicate>\\t<synonym>`    (a `synonyms` file)
      - a JSON object                          (a compendium or synonyms output file)
    """
    issues = []
    with open(path, encoding="utf-8", errors="replace") as inf:
        for line_no, line in enumerate(inf, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("{"):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Synonyms records are keyed on `curie`; compendium records lead with `identifiers`.
                curie = row.get("curie") or (row.get("identifiers") or [{}])[0].get("i", "?")
                texts = _texts_from_json(row)
            else:
                fields = line.split("\t")
                curie = fields[0]
                # A labels line is 2 fields, a synonyms line is 3+; the text is always last.
                texts = [fields[-1]] if len(fields) > 1 else []
            for text in texts:
                reason = find_encoding_issue(text)
                if reason:
                    issues.append((line_no, curie, text, reason))
    return issues


def _texts_from_json(row: dict) -> list[str]:
    """Pull every label-ish string out of a compendium or synonyms JSONL record."""
    texts = [identifier["l"] for identifier in row.get("identifiers", []) if identifier.get("l")]
    texts.extend(row.get("names", []))
    if row.get("preferred_name"):
        texts.append(row["preferred_name"])
    return texts
