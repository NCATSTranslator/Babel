"""Characterize the quoting/punctuation used in the two NCBIGene free-text synonym columns.

NCBI's ``gene_info.gz`` packs multiple values into two pipe-delimited free-text columns:

- ``Synonyms``           (column index 4)  -- the NCBI "otheraliases" field
- ``Other_designations`` (column index 13) -- the NCBI "otherdesignations" field

Issue #744 showed that NCBI wraps some comma-containing values in ``''...''`` and then splits the
whole field on ``|``, leaving dangling fragments such as ``''cytochrome P450``. But a *trailing*
``''`` is also legitimate "double-prime" gene nomenclature (``U2B''``, ``ycf1''``). Before we can
say how the quoting is *meant* to work, we need to know what non-word/whitespace characters even
appear in these fields and in what combinations.

This script streams the raw file (fields are examined *before* splitting on ``|``) and, for each of
the two columns, accumulates:

- ``char_frequency`` -- per-character histograms of every non-word/whitespace character, both as
  total occurrences and as number of rows containing the character.
- ``tag_row_counts`` -- how many rows carry each independent boolean tag (has_comma,
  has_double_single_quote, ...).
- ``tag_combination_counts`` -- for each non-empty row, the combination of quoting-relevant tags it
  carries (e.g. ``only_commas``, ``commas_and_double_single_quotes``), counted -- this is the
  histogram that reveals co-occurrence patterns.
- ``delimiter_consistency`` -- whether ``|`` behaves as the sole, clean delimiter: multi-value vs
  single-value rows, over-splitting (``''`` spans whose internal pipes are converted commas), and
  under-splitting (a ``;`` joining distinct values in a field with no pipe at all).

A "non-word/whitespace character" is any character ``c`` with ``not c.isalnum() and not c.isspace()
and c != "_"`` -- i.e. punctuation/symbols, excluding Unicode letters (Greek etc. in gene names)
and digits.

Regenerate with:

    uv run python docs/sources/NCBIGene/quoting/analyze_quoting.py

See README.md in this directory for the findings and the deferred follow-up questions.
"""

import argparse
import gzip
import json
import re
from collections import Counter
from pathlib import Path

from src.babel_utils import make_local_name
from src.datahandlers.ncbigene import GENE_INFO_HEADER, field_has_open_marker

# The two columns we study, keyed by the NCBI web-API field name Babel users will recognize.
COLUMNS = {
    "otheraliases": GENE_INFO_HEADER.index("Synonyms"),
    "otherdesignations": GENE_INFO_HEADER.index("Other_designations"),
}

DEFAULT_INPUT = Path(make_local_name("gene_info.gz", subpath="NCBIGene"))
DEFAULT_OUTPUT = Path(__file__).with_name("counts.json")


def is_nonword(c: str) -> bool:
    """A non-word/whitespace character: punctuation/symbols, not a letter, digit, ``_`` or space."""
    return not c.isalnum() and not c.isspace() and c != "_"


# Characters that are structural (the pipe delimiter) rather than quoting, excluded from the
# "other" tag so multi-value rows don't all collapse into one meaningless bucket.
STRUCTURAL_CHARS = {"|"}
# Characters that get their own combination tag; everything else non-word/whitespace is "other".
NAMED_QUOTING_CHARS = {",", "'", '"', ";", "\\"}

# Ordered so combination keys read consistently (comma first, then the quote family, ...).
COMBINATION_TAG_ORDER = [
    "comma",
    "double_single_quote",
    "lone_single_quote",
    "double_quote",
    "semicolon",
    "backslash",
    "other",
]
COMBINATION_TAG_LABEL = {
    "comma": "commas",
    "double_single_quote": "double_single_quotes",
    "lone_single_quote": "single_quotes",
    "double_quote": "double_quotes",
    "semicolon": "semicolons",
    "backslash": "backslashes",
    "other": "other",
}

# Heuristics for classifying a ';' in a field with no '|': a ';' followed by a letter is very
# likely a separator joining two phrases (e.g. "ribosomal protein S2;uncharacterized protein"),
# whereas a ';' flanked by digits is within-name nomenclature (e.g. "PIP1;2", "CYCLIN D3;3").
SEMICOLON_SEPARATOR_RE = re.compile(r";\s*[A-Za-z]")
SEMICOLON_WITHIN_NAME_RE = re.compile(r"\d;\d")

# Fixed output order for the delimiter_consistency block (logical grouping, not sorted by count).
DELIMITER_KEY_ORDER = [
    "rows_multi_value_pipe",
    "rows_single_value_no_pipe",
    "pipe_rows_with_empty_fragment",
    "pipe_rows_spaced_or_padded",
    "pipe_rows_with_open_marker",
    "no_pipe_rows_with_semicolon",
    "no_pipe_semicolon_separator_like",
    "no_pipe_semicolon_within_name_like",
    "no_pipe_rows_with_comma",
]


class FieldStats:
    """Accumulates all counts for a single column across the whole file."""

    def __init__(self):
        self.rows_total = 0
        self.rows_nonempty = 0
        self.total_occurrences = Counter()
        self.rows_with_char = Counter()
        self.tag_row_counts = Counter()
        self.tag_combination_counts = Counter()
        self.delimiter = Counter()

    def observe(self, value: str) -> None:
        self.rows_total += 1
        if value == "" or value == "-":
            self.tag_row_counts["empty"] += 1
            return
        self.rows_nonempty += 1

        nonword_chars = [c for c in value if is_nonword(c)]
        self.total_occurrences.update(nonword_chars)
        for c in set(nonword_chars):
            self.rows_with_char[c] += 1

        # Independent presence tags (superset of the combination tags).
        double_single = "''" in value
        # A lone single quote is a "'" left over after removing every "''" pair. The `"'" in value`
        # guard first: most of the ~70M values contain no quote at all, and .replace() allocates a
        # copy of the string even when there is nothing to replace.
        lone_single = "'" in value and "'" in value.replace("''", "")
        has = {
            "has_pipe": "|" in value,
            "has_comma": "," in value,
            "has_double_single_quote": double_single,
            "has_lone_single_quote": lone_single,
            "has_double_quote": '"' in value,
            "has_semicolon": ";" in value,
            "has_paren": "(" in value or ")" in value,
            "has_bracket": "[" in value or "]" in value,
            "has_brace": "{" in value or "}" in value,
            "has_backslash": "\\" in value,
            "has_other_nonword": any(
                is_nonword(c) and c not in NAMED_QUOTING_CHARS and c not in STRUCTURAL_CHARS for c in value
            ),
        }
        for tag, present in has.items():
            if present:
                self.tag_row_counts[tag] += 1

        self.tag_combination_counts[self._combination_key(value, double_single, lone_single, has)] += 1
        self._observe_delimiters(value, double_single, has)

    def _observe_delimiters(self, value: str, double_single: bool, has: dict) -> None:
        """Account for how consistently '|' delimits multiple values in this field.

        Threats to "pipe is the sole, clean delimiter": over-splitting (a '' span whose internal
        pipes are converted commas, not value boundaries -- issue #744) and under-splitting (a
        semicolon joining distinct values with no pipe at all).
        """
        if has["has_pipe"]:
            self.delimiter["rows_multi_value_pipe"] += 1
            if any(frag == "" for frag in value.split("|")):
                self.delimiter["pipe_rows_with_empty_fragment"] += 1
            if " | " in value or value.strip() != value:
                self.delimiter["pipe_rows_spaced_or_padded"] += 1
            # Not just "contains ''" -- a '' is usually genuine double-prime nomenclature. Only an
            # *open* marker (a fragment starting but not ending with '') means NCBI split one
            # logical value across pipe-fields; key off the production predicate so this can't drift.
            if double_single and field_has_open_marker(value):
                self.delimiter["pipe_rows_with_open_marker"] += 1
        else:
            self.delimiter["rows_single_value_no_pipe"] += 1
            if has["has_semicolon"]:
                self.delimiter["no_pipe_rows_with_semicolon"] += 1
                if SEMICOLON_SEPARATOR_RE.search(value):
                    self.delimiter["no_pipe_semicolon_separator_like"] += 1
                if SEMICOLON_WITHIN_NAME_RE.search(value):
                    self.delimiter["no_pipe_semicolon_within_name_like"] += 1
            if has["has_comma"]:
                self.delimiter["no_pipe_rows_with_comma"] += 1

    @staticmethod
    def _combination_key(value: str, double_single: bool, lone_single: bool, has: dict) -> str:
        active = []
        if has["has_comma"]:
            active.append("comma")
        if double_single:
            active.append("double_single_quote")
        if lone_single:
            active.append("lone_single_quote")
        if has["has_double_quote"]:
            active.append("double_quote")
        if has["has_semicolon"]:
            active.append("semicolon")
        if has["has_backslash"]:
            active.append("backslash")
        if has["has_other_nonword"]:
            active.append("other")

        if not active:
            return "none"
        labels = [COMBINATION_TAG_LABEL[t] for t in COMBINATION_TAG_ORDER if t in active]
        if len(labels) == 1:
            return f"only_{labels[0]}"
        return "_and_".join(labels)

    def to_dict(self) -> dict:
        return {
            "rows_total": self.rows_total,
            "rows_nonempty": self.rows_nonempty,
            "char_frequency": {
                "total_occurrences": _sorted_desc(self.total_occurrences),
                "rows_with_char": _sorted_desc(self.rows_with_char),
            },
            "tag_row_counts": _sorted_desc(self.tag_row_counts),
            "tag_combination_counts": _sorted_desc(self.tag_combination_counts),
            "delimiter_consistency": {k: self.delimiter.get(k, 0) for k in DELIMITER_KEY_ORDER},
        }


def _sorted_desc(counter: Counter) -> dict:
    """Return a plain dict ordered by descending count (ties broken by key for stability)."""
    return {k: v for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))}


def analyze(input_path: Path) -> dict:
    stats = {name: FieldStats() for name in COLUMNS}
    total_data_rows = 0
    malformed_rows = 0
    max_index = max(COLUMNS.values())

    with gzip.open(input_path, "rt", encoding="utf-8") as inf:
        header = inf.readline().rstrip("\n").split("\t")
        if header != GENE_INFO_HEADER:
            raise ValueError(f"Unexpected gene_info.gz header; upstream layout changed:\n{header}")
        for line in inf:
            row = line.rstrip("\n").split("\t")
            total_data_rows += 1
            if len(row) <= max_index:
                malformed_rows += 1
                continue
            for name, index in COLUMNS.items():
                stats[name].observe(row[index])

    result = {
        "meta": {
            "source_file": str(input_path),
            "generated_by": "docs/sources/NCBIGene/quoting/analyze_quoting.py",
            # Deliberately no generated_at: this file is committed and regenerated, and a timestamp
            # would make every re-run dirty it even when no count changed -- hiding the real diff,
            # which is the only thing worth reviewing. Git history records when it was last written.
            "total_data_rows": total_data_rows,
            "malformed_rows": malformed_rows,
            "columns_analyzed": {
                "otheraliases": "Synonyms (col 4)",
                "otherdesignations": "Other_designations (col 13)",
            },
            "nonword_definition": "not alnum, not whitespace, not underscore",
            "notes": (
                "Fields analyzed raw, before splitting on '|'. '' is a two-char sequence handled by "
                "the tag analysis, not the single-char histogram. '|' is the field delimiter and is "
                "excluded from the combination 'other' bucket."
            ),
        },
    }
    for name in COLUMNS:
        result[name] = stats[name].to_dict()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT, help=f"gene_info.gz path (default: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help=f"output JSON path (default: {DEFAULT_OUTPUT})"
    )
    args = parser.parse_args()

    result = analyze(args.input)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({result['meta']['total_data_rows']:,} data rows)")  # noqa: T201


if __name__ == "__main__":
    main()
