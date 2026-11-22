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

The report also answers a question the categories above invite: if ''...'' is just quoting, can the
quoted value be rebuilt by rejoining the fragments between the markers? ``check_rejoinable`` tests
that against the row's own ``Full_name``/``Other_designations``, which carries the value intact.
The answer is no -- see the generated report -- because genuine unrelated aliases sit inside the
span and the value's internal commas became pipes.

Usage:
    uv run python docs/sources/NCBIGene/quoting/double_prime_report.py [--limit 10] \
        [--input gene_info.gz] [--output double_prime_report.md] [--csv double_prime_tokens.csv]
"""

import argparse
import csv
import gzip
import re
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

from src.babel_utils import make_local_name
from src.datahandlers.ncbigene import GENE_INFO_HEADER, field_has_open_marker, is_open_marker

TAX_ID = GENE_INFO_HEADER.index("#tax_id")
GENE_ID = GENE_INFO_HEADER.index("GeneID")
SYMBOL = GENE_INFO_HEADER.index("Symbol")
SYNONYMS = GENE_INFO_HEADER.index("Synonyms")
DESCRIPTION = GENE_INFO_HEADER.index("description")
SYMBOL_AUTH = GENE_INFO_HEADER.index("Symbol_from_nomenclature_authority")
FULL_NAME = GENE_INFO_HEADER.index("Full_name_from_nomenclature_authority")
OTHER_DESIG = GENE_INFO_HEADER.index("Other_designations")

DEFAULT_INPUT = Path(make_local_name("gene_info.gz", subpath="NCBIGene"))
DEFAULT_OUTPUT = Path(__file__).with_name("double_prime_report.md")
DEFAULT_CSV = Path(__file__).with_name("double_prime_tokens.csv")


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
    has_open = field_has_open_marker(value)
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


def check_rejoinable(row):
    """Can the ''...''-quoted value be rebuilt by rejoining the fragments between its markers?

    The intuitive reading of ''...'' is ordinary quoting: the fragments between the open and close
    markers are one comma-containing value, so rejoin them with ", " and recover it. This function
    tests that reading against the row's own Full_name/Other_designations, which carries the value
    intact. Returns None if the row has no open marker, else a dict recording whether the naive
    rejoin reproduces the true value and which fragments inside the span are foreign to it.
    """
    if not field_has_open_marker(row[SYNONYMS]):
        return None
    frags = [f.strip() for f in row[SYNONYMS].split("|")]
    flags = [(f, f.startswith("''"), f.endswith("''")) for f in frags]
    open_i = next(i for i, (_, s, e) in enumerate(flags) if is_open_marker(s, e))
    close_i = next((i for i in range(open_i + 1, len(frags)) if frags[i].endswith("''")), None)
    truth = next((row[c] for c in (FULL_NAME, OTHER_DESIG) if row[c] not in ("", "-")), None)
    # Where the open marker sits, and whether the fragment list is ASCII-sorted. The marker is always
    # fragment 0 in today's file -- but only because "'" (0x27) sorts below every letter and digit,
    # so a sorted alias list floats it to the front. That is incidental, which is why
    # field_has_open_marker() scans every fragment instead of testing value.startswith("''").
    position = {"open_index": open_i, "ascii_sorted": frags == sorted(frags)}
    if close_i is None or truth is None:
        # An open marker with no close marker, or with no Full_name to compare against: the rejoin
        # question is not decidable for this row. Counted separately so the denominators add up.
        return {"checkable": False, **position}

    span = frags[open_i : close_i + 1]
    rejoined = ", ".join(f.strip("'") for f in span)
    # Pieces of the true value, as they would appear once its commas became pipes.
    pieces = {p.strip() for p in truth.split(",")}
    # Fragments sitting inside the span that are NOT part of the true value: their presence is what
    # makes the span un-rejoinable (they are genuine, unrelated aliases, e.g. locus tags).
    foreign = [f for f in span if f.strip("'").strip() not in pieces]
    return {
        "checkable": True,
        "exact": rejoined == truth,
        "foreign": foreign,
        "example": (row[GENE_ID], row[SYMBOL], row[SYNONYMS], truth, rejoined),
        **position,
    }


def analyze(input_path: Path):
    counts = Counter()
    # potentially-valid tokens: token -> {"rows": n, "is_symbol": n_where_equals_symbol, "example": (...)}
    valid_tokens = defaultdict(lambda: {"rows": 0, "is_symbol": 0, "example": None})
    balanced_tokens = Counter()
    rejoin = {"rows": 0, "checkable": 0, "exact": 0, "interleaved": 0, "examples": []}
    # Where the open marker sits among the pipe-fragments, over every row that has one.
    position = {"open_marker_first": 0, "ascii_sorted": 0}

    with gzip.open(input_path, "rt", encoding="utf-8") as inf:
        inf.readline()
        for line in inf:
            r = line.rstrip("\n").split("\t")
            if len(r) <= OTHER_DESIG:
                continue
            symbol = r[SYMBOL]

            # Is the quoted span reconstructable by rejoining? (Spoiler: no -- see the report.)
            rj = check_rejoinable(r)
            if rj is not None:
                rejoin["rows"] += 1
                position["open_marker_first"] += rj["open_index"] == 0
                position["ascii_sorted"] += rj["ascii_sorted"]
                if rj["checkable"]:
                    rejoin["checkable"] += 1
                    if rj["exact"]:
                        rejoin["exact"] += 1
                    else:
                        rejoin["interleaved"] += 1
                        if len(rejoin["examples"]) < 5:
                            rejoin["examples"].append(rj)

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
    return counts, valid_tokens, balanced_tokens, rejoin, position


def _record_valid(valid_tokens, token, row, symbol):
    entry = valid_tokens[token]
    entry["rows"] += 1
    if token == symbol:
        entry["is_symbol"] += 1
    if entry["example"] is None:
        desc = next((row[c] for c in (DESCRIPTION, FULL_NAME) if row[c] not in ("", "-")), "-")
        entry["example"] = (row[GENE_ID], row[TAX_ID], desc)


def representative_sample(ranked, limit):
    """Pick `limit` tokens covering both genuine double-prime shapes, most common of each first.

    Ranking purely by row count buries the chemical-position locants (2''-O-xylosyltransferase and
    friends, first at rank ~13) under the protein-subunit names (beta'', B'', c''), so a short head
    of the list would misrepresent what '' is used for. Split on the character before the '' --
    digit means locant, anything else means subunit -- and take half the sample from each.
    """
    digit_led = [kv for kv in ranked if re.search(r"\d''", kv[0])]
    other = [kv for kv in ranked if not re.search(r"\d''", kv[0])]
    half = limit // 2
    sample = other[: limit - half] + digit_led[:half]
    return sorted(sample, key=lambda kv: (-kv[1]["rows"], kv[0]))


def para(text):
    """Wrap a prose paragraph to 100 characters, the MD013 limit rumdl enforces on this file.

    This report is regenerated, so the generator -- not a one-off `rumdl fmt` -- has to emit
    lint-clean Markdown; otherwise every re-run dirties the committed file.
    """
    return textwrap.fill(text, width=100) + "\n"


def write_position_section(lines, rejoin, position):
    """Where does the open marker sit -- and can a parser rely on it being first?"""
    n = rejoin["rows"]
    lines.append("## Is the open marker always the first fragment?\n")
    lines.append("```text")
    lines.append(f"{'rows with an open marker':44s} {n:>6,}")
    lines.append(f"{'  open marker is fragment 0':44s} {position['open_marker_first']:>6,}")
    lines.append(f"{'  fragment list is ASCII-sorted':44s} {position['ascii_sorted']:>6,}")
    lines.append("```\n")
    lines.append(
        para(
            "Yes today -- and the second count says why. The alias list is ASCII-sorted, and `'` "
            "(0x27) sorts below every letter and digit, so a fragment starting with `''` floats to "
            "the front on its own. NCBI is not placing the marker first on purpose; it falls out of "
            "the sort. (The same sort is why the *close* marker lands mid-list rather than at the "
            "end.)"
        )
    )
    lines.append(
        para(
            "So a parser should not harden this into `value.startswith(\"''\")`. "
            "`split_ncbigene_synonym_field` scans every fragment for the open-marker shape instead, "
            "which survives NCBI changing its sort order, and costs nothing: the `\"''\" not in "
            "value` guard skips the ~70M rows that carry no `''` at all."
        )
    )


def write_rejoin_section(lines, rejoin):
    """Append the "can the quoted span be rejoined?" findings to the report."""
    lines.append("## Can the quoted value be reconstructed by rejoining the span?\n")
    if not rejoin["rows"]:
        lines.append("No rows with an open marker found.\n")
        return
    lines.append(
        para(
            "Tests the intuitive reading of `''…''` as ordinary quoting: rejoin the fragments "
            'between the markers with `", "` and compare against the row\'s own '
            "`Full_name`/`Other_designations`, which carries the value intact."
        )
    )
    undecidable = rejoin["rows"] - rejoin["checkable"]
    lines.append("```text")
    lines.append(f"{'rows with an open marker':38s} {rejoin['rows']:>10,}")
    lines.append(f"{'  no close marker / no Full_name':38s} {undecidable:>10,}   (not decidable)")
    lines.append(f"{'  checkable':38s} {rejoin['checkable']:>10,}")
    lines.append(f"{'    naive rejoin == true value':38s} {rejoin['exact']:>10,}")
    lines.append(f"{'    rejoin produces something else':38s} {rejoin['interleaved']:>10,}")
    lines.append("```\n")
    if not rejoin["exact"]:
        lines.append(
            para(
                "**Not reconstructable.** The span is not a contiguous run of the value's pieces: "
                "genuine, unrelated aliases (locus tags and the like) sit *inside* it, the fragment "
                "order is meaningless, and the value's internal commas became `|` — indistinguishable "
                "from the delimiter. Rejoining yields garbage."
            )
        )
        lines.append(
            para(
                "This costs nothing: `Full_name_from_nomenclature_authority` / `Other_designations` "
                "carry the correct value, and Babel already reads both. See issue #932 for the junk "
                "comma-pieces that do remain."
            )
        )
    for e in rejoin["examples"]:
        gid, sym, syn, truth, rejoined = e["example"]
        lines.append(f"### Gene {gid} (`{sym}`)\n")
        lines.append("```text")
        lines.append(f"Synonyms  : {syn}")
        lines.append(f"true value: {truth}")
        lines.append(f"rejoined  : {rejoined}")
        lines.append(f"foreign fragments inside the span (not part of the value): {e['foreign']}")
        lines.append("```\n")


def write_csv(ranked, out_path):
    """Every distinct potentially-valid token, the exhaustive record the Markdown only samples."""
    with out_path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out, lineterminator="\n")  # csv defaults to \r\n; keep the file LF-only.
        writer.writerow(
            [
                "token",
                "rows",
                "rows_where_token_is_the_symbol",
                "example_gene_id",
                "example_tax_id",
                "example_full_name",
            ]
        )
        for token, e in ranked:
            gid, tax, name = e["example"]
            writer.writerow([token, e["rows"], e["is_symbol"], gid, tax, name])


def write_report(counts, valid_tokens, balanced_tokens, rejoin, position, limit, out_path, csv_path, input_path):
    total_valid_rows = sum(e["rows"] for e in valid_tokens.values())
    lines = []
    lines.append("# NCBIGene `''` (double single quote): valid vs. split-artifact\n")
    lines.append(f"Source: `{input_path}`. Generated by `double_prime_report.py`.")
    lines.append(f"Every distinct token is in [`{csv_path.name}`](./{csv_path.name}).\n")
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
    sample = representative_sample(ranked, limit)
    lines.append(f"## Distinct potentially-valid tokens ({len(sample)} of {len(ranked):,})\n")
    lines.append("`token` — rows — is_symbol (rows where it equals the gene's own Symbol) — example gene\n")
    lines.append(
        para(
            "The most common tokens of each genuine double-prime shape: a *letter* before the `''` "
            "(subunit nomenclature — RNA polymerase `beta''`, snRNP `B''`) and a *digit* before it "
            "(chemical-position locants — `6''-O-malonyltransferase`). Purely top-by-row-count would "
            f"be all subunit names. All {len(ranked):,} tokens are in "
            f"[`{csv_path.name}`](./{csv_path.name})."
        )
    )
    lines.append("| token | rows | is_symbol | example GeneID | example tax | example full name |")
    lines.append("| --- | ---: | ---: | --- | --- | --- |")
    for token, e in sample:
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

    write_position_section(lines, rejoin, position)
    write_rejoin_section(lines, rejoin)

    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    p.add_argument("--limit", type=int, default=10, help="distinct tokens to sample into the table (default 10)")
    args = p.parse_args()
    counts, valid_tokens, balanced_tokens, rejoin, position = analyze(args.input)
    ranked = sorted(valid_tokens.items(), key=lambda kv: (-kv[1]["rows"], kv[0]))
    write_csv(ranked, args.csv)
    write_report(counts, valid_tokens, balanced_tokens, rejoin, position, args.limit, args.output, args.csv, args.input)
    total_valid_rows = sum(e["rows"] for e in valid_tokens.values())
    print(  # noqa: T201
        f"Wrote {args.output} and {args.csv}: {total_valid_rows:,} valid-'' rows, "
        f"{len(valid_tokens):,} distinct tokens; "
        f"{rejoin['exact']:,}/{rejoin['rows']:,} quoted spans rejoin to their true value"
    )


if __name__ == "__main__":
    main()
