"""``babel-check-encoding`` — survey Babel files for encoding damage.

Argument parsing and output formatting only; the detector lives in :mod:`src.synonyms.encoding`,
so the pipeline's raising check and this report share one definition of "damaged".

Invocation::

    uv run babel-check-encoding babel_downloads/PUBCHEM.COMPOUND/labels
    uv run babel-check-encoding --recursive babel_downloads
    uv run babel-check-encoding --recursive babel_outputs/compendia --out-tsv issues.tsv

Accepts `labels` and `synonyms` files, compendium/synonym JSONL, or directories with
``--recursive``. Prints a per-file count with example rows, and exits 1 if anything was found so it
can gate a script.
"""

import argparse
import sys
from pathlib import Path

from src.synonyms.encoding import scan_file

# Files worth scanning when walking a directory. Babel's label and synonym files have no
# extension, so we match on name; the JSONL outputs are `.txt`.
SCANNABLE_NAMES = {"labels", "synonyms"}
SCANNABLE_SUFFIXES = {".txt"}


def find_files(paths, recursive):
    """Expand the given paths into a sorted list of files to scan."""
    files = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            if not recursive:
                raise RuntimeError(f"{path} is a directory; pass --recursive to walk it.")
            files.extend(
                p
                for p in path.rglob("*")
                if p.is_file() and (p.name in SCANNABLE_NAMES or p.suffix in SCANNABLE_SUFFIXES)
            )
        else:
            files.append(path)
    return sorted(set(files))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Survey Babel files for encoding damage.")
    parser.add_argument("paths", nargs="+", help="Files or (with --recursive) directories to scan.")
    parser.add_argument("--recursive", action="store_true", help="Walk directories for labels/synonyms/*.txt files.")
    parser.add_argument(
        "--examples", type=int, default=5, help="Example rows to print per file (default: 5, 0 for none)."
    )
    parser.add_argument("--out-tsv", help="Optional path to write every issue as a TSV.")
    args = parser.parse_args(argv)

    files = find_files(args.paths, args.recursive)
    all_issues = []
    files_with_issues = 0

    for path in files:
        issues = scan_file(path)
        if not issues:
            continue
        files_with_issues += 1
        all_issues.extend((path, *issue) for issue in issues)
        print(f"{path}: {len(issues):,} issue(s)")
        for _line_no, curie, text, reason in issues[: args.examples]:
            print(f"    {curie}\t{text!r}\t{reason}")
        if len(issues) > args.examples:
            print(f"    ... and {len(issues) - args.examples:,} more")

    if args.out_tsv:
        with open(args.out_tsv, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("file\tline\tcurie\ttext\treason\n")
            for path, line_no, curie, text, reason in all_issues:
                # The damaged text can itself contain a control character, which would corrupt the
                # TSV; repr() keeps every row on one line and makes the bad bytes visible.
                fh.write(f"{path}\t{line_no}\t{curie}\t{text!r}\t{reason}\n")
        print(f"Wrote {len(all_issues):,} issue(s) to {args.out_tsv}.")

    print(f"Scanned {len(files):,} file(s): {len(all_issues):,} issue(s) in {files_with_issues:,} file(s).")
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
