"""Aggregate Babel SLURM rule error logs into a single copy-pasteable report.

Reads the main Snakemake ``sbatch-<version>.err`` control-node log, follows each
failing rule to its per-rule log, and groups rules that share identical error
content so a recurring transient failure (e.g. an HTTP 503 from a data source)
shows up once. This is the fastest way to find which upstream rules to re-run so a
stalled DAG can finish.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parse import extract_error_content, find_err_file, parse_failures


def build_report(failures: list[tuple[str, Path]], markdown: bool, traceback_only: bool, fallback_lines: int) -> str:
    if not failures:
        return "No failures found."

    # Deduplicate: group rules that share identical error content.
    content_to_rules: dict[str, list[str]] = {}
    for rule, log_path in failures:
        content = extract_error_content(log_path, fallback_lines)
        if traceback_only and "Traceback (most recent call last):" not in content:
            continue
        label = f"{rule} ({log_path.name})"
        content_to_rules.setdefault(content.strip(), []).append(label)

    if not content_to_rules:
        return "No tracebacks found in failing rule logs." if traceback_only else "No content extracted from logs."

    sections: list[str] = []
    for content, rules in content_to_rules.items():
        header = "Rule(s): " + ", ".join(rules)
        if markdown:
            sections.append(f"## {header}\n\n```\n{content}\n```")
        else:
            bar = "=" * (len(header) + 8)
            sections.append(f"{bar}\n=== {header} ===\n{bar}\n{content}")

    return "\n\n".join(sections)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "errors",
        help="Aggregate failing-rule logs into one report.",
        description="Aggregate Babel SLURM error logs into a single copy-pasteable report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  uv run python -m tools.slurm errors 1.17-try-2
  uv run python -m tools.slurm errors 1.17-try-2 --markdown
  uv run python -m tools.slurm errors --traceback-only
""",
    )
    parser.add_argument(
        "version", nargs="?", help="Babel version tag (e.g. 1.17-try-2). Auto-detects newest .err file if omitted."
    )
    parser.add_argument(
        "--logs-dir",
        default="babel_outputs/logs",
        metavar="DIR",
        help="Directory containing log files (default: babel_outputs/logs).",
    )
    parser.add_argument(
        "--markdown", action="store_true", help="Wrap each error in a fenced code block for pasting into Claude."
    )
    parser.add_argument(
        "--traceback-only", action="store_true", help="Only include rules whose logs contain a Python traceback."
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=50,
        metavar="N",
        help="Fallback line count when no traceback is found (default: 50).",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    logs_dir = Path(args.logs_dir)
    try:
        err_file = find_err_file(args.version, logs_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {err_file}", file=sys.stderr)
    failures = parse_failures(err_file)
    if not failures:
        print("No rule failures found in error log.", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(failures)} failing rule(s).", file=sys.stderr)
    print(build_report(failures, args.markdown, args.traceback_only, args.lines))


def main() -> None:
    """Backward-compatible entry point for ``tools/babel-errors.py``."""
    parser = argparse.ArgumentParser(
        description="Aggregate Babel SLURM error logs into a single copy-pasteable report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  uv run tools/babel-errors.py 1.17-try-2
  uv run tools/babel-errors.py 1.17-try-2 --markdown
  uv run tools/babel-errors.py --traceback-only
  uv run tools/babel-errors.py 1.17-try-2 --markdown > /tmp/errors.md
""",
    )
    parser.add_argument(
        "version", nargs="?", help="Babel version tag (e.g. 1.17-try-2). Auto-detects newest .err file if omitted."
    )
    parser.add_argument("--logs-dir", default="babel_outputs/logs", metavar="DIR")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--traceback-only", action="store_true")
    parser.add_argument("--lines", type=int, default=50, metavar="N")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
