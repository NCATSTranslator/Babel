#!/usr/bin/env python3
"""Aggregate Babel SLURM rule error logs into a single report for debugging."""

import argparse
import re
import sys
from pathlib import Path


def find_err_file(version: str | None, logs_dir: Path) -> Path:
    if version:
        path = logs_dir / f"sbatch-{version}.err"
        if not path.exists():
            raise FileNotFoundError(f"Error log not found: {path}")
        return path
    candidates = sorted(logs_dir.glob("sbatch-*.err"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No sbatch-*.err files found in {logs_dir}")
    return candidates[-1]


def parse_failures(err_file: Path) -> list[tuple[str, Path]]:
    """Return (rule_name, log_path) pairs extracted from the main Snakemake error log."""
    text = err_file.read_text(errors="replace")
    rule_re = re.compile(r"Error in rule (\w+):")
    log_re = re.compile(r"log: (\S+\.log)")

    results: list[tuple[str, Path]] = []
    current_rule: str | None = None
    for line in text.splitlines():
        if m := rule_re.search(line):
            current_rule = m.group(1)
        if (m := log_re.search(line)) and current_rule:
            results.append((current_rule, Path(m.group(1))))
            current_rule = None
    return results


def extract_error_content(log_path: Path, fallback_lines: int) -> str:
    if not log_path.exists():
        return f"(log file not found: {log_path})"

    lines = log_path.read_text(errors="replace").splitlines()

    # Use the last Python traceback block if present.
    last_tb_start: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Traceback (most recent call last):"):
            last_tb_start = i

    if last_tb_start is not None:
        return "\n".join(lines[last_tb_start:])

    return "\n".join(lines[-fallback_lines:])


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


def main() -> None:
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
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
