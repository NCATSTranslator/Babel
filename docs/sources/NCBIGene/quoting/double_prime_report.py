"""Report on '' occurrences in NCBIGene gene_info.gz that could be *genuine* name components
(e.g. double-prime nomenclature) rather than issue-#744 pipe-split artifacts.

Classification of a '' occurrence:

- **open-marker artifact**: a pipe-fragment that STARTS with '' (e.g. ``''cytochrome P450``) --
  the opening of a comma-containing value NCBI split across pipe-fields (issue #744).
- **close-marker artifact**: a pipe-fragment that ENDS with '' *in a field that also has an
  open-marker fragment* -- the closing end of the same split span (e.g. ``polypeptide 2''``).
- **potentially valid**: a '' that is NOT a split marker -- i.e. it could be real double-prime
  nomenclature (``U2B''``, RNA polymerase subunit ``beta''``). Three shapes qualify:
  - a ``Symbol`` / ``Symbol_from_nomenclature_authority`` field (single value, no pipe list), or
  - a synonym pipe-fragment ending in '' whose field contains no open-marker fragment, or
  - an ``internal`` '' (mid-fragment, text on both sides) -- a split marker only ever sits at a
    fragment boundary, so an embedded '' cannot be one.
- **balanced**: a single fragment both starting and ending with '' (``''X''``) -- reported separately.

Examples are DEDUPED by the token (the ''-bearing string), because the same symbol repeats across
many species; the report shows each distinct token, how many rows carry it, whether it equals the
gene's own ``Symbol`` (strong evidence it is the real symbol), and one example gene.

Usage:
    uv run python docs/sources/NCBIGene/quoting/double_prime_report.py [--limit 200] \
        [--input gene_info.gz] [--output double_prime_report.md]
"""

import argparse
import gzip
from collections import Counter, defaultdict
from pathlib import Path

from src.datahandlers.ncbigene import is_open_marker

TAX_ID, GENE_ID, SYMBOL, SYNONYMS, DESCRIPTION, SYMBOL_AUTH, FULL_NAME, OTHER_DESIG = 0, 1, 2, 4, 8, 10, 11, 13

DEFAULT_INPUT = Path("babel_downloads/NCBIGene/gene_info.gz")
DEFAULT_OUTPUT = Path(__file__).with_name("double_prime_report.md")


def classify_field(value: str):
    """Yield (category, token) for each ''-bearing unit in one raw field value.

    Categories: 'open', 'close', 'valid', 'balanced', 'internal'. Uses the shared
    src.datahandlers.ncbigene.is_open_marker() predicate so this report can't drift from what
    split_ncbigene_synonym_field actually treats as an open marker.
    """
    if "''" not in value:
        return
    fragments = value.split("|")
    flags = [(f, f.startswith("''"), f.endswith("''")) for f in fragments]
    has_open = any(is_open_marker(starts, ends) for _, starts, ends in flags)
    for f, starts, ends in flags:
        if "''" not in f:
            continue
        if starts and ends:
            yield "balanced", f
        elif starts:
            yield "open", f
        elif ends:
            yield ("close" if has_open else "valid"), f
        else:
            yield "internal", f


def analyze(input_path: Path):
    counts = Counter()
    # potentially-valid tokens: token -> {"rows": n, "is_symbol": n_where_equals_symbol, "example": (...)}
    valid_tokens = defaultdict(lambda: {"rows": 0, "is_symbol": 0, "example": None})
    balanced_tokens = Counter()

    with gzip.open(input_path, "rt", encoding="utf-8") as inf:
        inf.readline()
        for line in inf:
            r = line.rstrip("\n").split("\t")
            if len(r) <= OTHER_DESIG:
                continue
            symbol = r[SYMBOL]
            # Single-value Symbol columns: a trailing '' is unambiguously part of the recorded symbol.
            for col in (SYMBOL, SYMBOL_AUTH):
                v = r[col]
                if v not in ("", "-") and v.endswith("''") and not v.startswith("''"):
                    counts["symbol_field_valid"] += 1
                    _record_valid(valid_tokens, v, r, symbol)
            # Synonym list fields.
            for col in (SYNONYMS, OTHER_DESIG):
                v = r[col]
                if v in ("", "-") or "''" not in v:
                    continue
                for category, token in classify_field(v):
                    counts[f"{'aliases' if col == SYNONYMS else 'designations'}_{category}"] += 1
                    # 'internal' ('' mid-fragment) is genuine too: a split-marker only ever sits at a
                    # fragment boundary, so a '' embedded in text cannot be one.
                    if category in ("valid", "internal"):
                        _record_valid(valid_tokens, token, r, symbol)
                    elif category == "balanced":
                        balanced_tokens[token] += 1
    return counts, valid_tokens, balanced_tokens


def _record_valid(valid_tokens, token, row, symbol):
    entry = valid_tokens[token]
    entry["rows"] += 1
    if token == symbol:
        entry["is_symbol"] += 1
    if entry["example"] is None:
        desc = next((row[c] for c in (DESCRIPTION, FULL_NAME) if row[c] not in ("", "-")), "-")
        entry["example"] = (row[GENE_ID], row[TAX_ID], desc)


def write_report(counts, valid_tokens, balanced_tokens, limit, out_path, input_path):
    total_valid_rows = sum(e["rows"] for e in valid_tokens.values())
    lines = []
    lines.append("# NCBIGene `''` (double single quote): valid vs. split-artifact\n")
    lines.append(f"Source: `{input_path}`. Generated by `double_prime_report.py`.\n")
    lines.append("## How often\n")
    lines.append("Occurrence counts by category (see the script docstring for definitions).")
    lines.append("'open'/'close' are issue-#744 pipe-split markers (artifacts); 'valid' (trailing")
    lines.append("`''`, no open marker), 'internal' (`''` mid-text), and 'symbol_field_valid' are")
    lines.append("all genuine double-prime candidates.\n")
    lines.append("```text")
    for key in sorted(counts):
        lines.append(f"{key:34s} {counts[key]:>10,}")
    lines.append("```\n")
    lines.append(
        f"**Potentially-valid `''` occurrences: {total_valid_rows:,} rows across "
        f"{len(valid_tokens):,} distinct tokens.**\n"
    )

    ranked = sorted(valid_tokens.items(), key=lambda kv: (-kv[1]["rows"], kv[0]))
    lines.append(f"## Distinct potentially-valid tokens (top {min(limit, len(ranked))} by row count)\n")
    lines.append("`token` — rows — is_symbol (rows where it equals the gene's own Symbol) — example gene\n")
    lines.append("| token | rows | is_symbol | example GeneID | example tax | example full name |")
    lines.append("| --- | ---: | ---: | --- | --- | --- |")
    for token, e in ranked[:limit]:
        gid, tax, name = e["example"]
        safe = token.replace("|", "\\|")
        name = name.replace("|", "\\|")[:70]
        lines.append(f"| `{safe}` | {e['rows']:,} | {e['is_symbol']:,} | {gid} | {tax} | {name} |")
    lines.append("")

    if balanced_tokens:
        lines.append(
            f"## Balanced `''X''` fragments ({sum(balanced_tokens.values()):,} rows, "
            f"{len(balanced_tokens):,} distinct)\n"
        )
        lines.append("| token | rows |")
        lines.append("| --- | ---: |")
        for token, n in balanced_tokens.most_common(min(limit, len(balanced_tokens))):
            lines.append(f"| `{token.replace('|', chr(92) + '|')}` | {n:,} |")
        lines.append("")

    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--limit", type=int, default=200, help="max distinct tokens to list (default 200)")
    args = p.parse_args()
    counts, valid_tokens, balanced_tokens = analyze(args.input)
    write_report(counts, valid_tokens, balanced_tokens, args.limit, args.output, args.input)
    total_valid_rows = sum(e["rows"] for e in valid_tokens.values())
    print(f"Wrote {args.output}: {total_valid_rows:,} valid-'' rows, {len(valid_tokens):,} distinct tokens")  # noqa: T201


if __name__ == "__main__":
    main()
