"""Aggregate Babel SLURM rule error logs into a single copy-pasteable report.

Reads the main Snakemake ``sbatch-<version>.err`` control-node log, follows each failing rule to
its per-rule log, and groups rules that share identical error content so a recurring transient
failure (e.g. an HTTP 503 from a data source) shows up once. The trailing job summary classifies
every job attempt as completed / failed / still-running, with elapsed-vs-timeout for running jobs.
Together this is the fastest way to find which upstream rules to re-run so a stalled DAG can finish.

The parsing lives in :mod:`src.tools.slurm.parse`; this module is presentation + CLI only.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path

from .parse import (
    JobEvent,
    declared_runtime_min,
    extract_error_content,
    find_err_file,
    parse_failures,
    parse_job_events,
)


def _fmt_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def build_report(
    failures: list[tuple[str, Path]], markdown: bool, traceback_only: bool, max_lines: int, logs_dir: Path | None = None
) -> str:
    if not failures:
        return "No failures found."

    # Deduplicate: group rules that share identical error content.
    content_to_rules: dict[str, list[str]] = {}
    for rule, log_path in failures:
        content = extract_error_content(log_path, max_lines, logs_dir)
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


def print_job_summary(err_file: Path, logs_dir: Path) -> None:
    """Print a completed / failed / still-running summary of every job attempt to stderr."""
    jobs = parse_job_events(err_file)
    if not jobs:
        return

    now = datetime.now(UTC)

    # Group jobs by logical task (rule + wildcard), sorted by submission time within each group.
    sorted_jobs = sorted(jobs, key=lambda j: (j.rule_name, j.wildcard, j.submitted_at))
    completed_groups: list[list[JobEvent]] = []
    failed_groups: list[list[JobEvent]] = []
    incomplete_groups: list[tuple[list[JobEvent], list[JobEvent]]] = []
    for _, grp in groupby(sorted_jobs, key=lambda j: (j.rule_name, j.wildcard)):
        group = list(grp)
        running = [j for j in group if not j.finished_at and not j.failed]
        if running:
            incomplete_groups.append((group, running))
        elif any(j.finished_at and not j.failed for j in group):
            completed_groups.append(group)
        else:
            failed_groups.append(group)

    # Incomplete: one line per running job, with indented prior-failure sub-lines if retried.
    if incomplete_groups:
        print(f"Found {len(incomplete_groups)} incomplete rule(s):", file=sys.stderr)
        for group, running in sorted(incomplete_groups, key=lambda x: x[0][0].submitted_at):
            prior_failures = [j for j in group if j.failed]
            j = running[0]
            elapsed = (now - j.submitted_at).total_seconds()
            timeout_min = declared_runtime_min(j.log_relative, logs_dir)
            elapsed_str = _fmt_duration(elapsed)
            timeout_str = _fmt_duration(timeout_min * 60)
            remaining_str = _fmt_duration(max(0.0, timeout_min * 60 - elapsed))
            print(
                f" - Rule {j.rule_name} (SLURM jobid {j.slurm_jobid}):"
                f" {elapsed_str} / {timeout_str} ({remaining_str} left),"
                f" log at {logs_dir / j.log_relative}",
                file=sys.stderr,
            )
            for f in prior_failures:
                dur = _fmt_duration((f.finished_at - f.submitted_at).total_seconds()) if f.finished_at else "unknown"
                print(
                    f"   - Prior failure (SLURM jobid {f.slurm_jobid}):"
                    f" failed after {dur},"
                    f" log at {logs_dir / f.log_relative}",
                    file=sys.stderr,
                )
    else:
        print("Found 0 incomplete rules.", file=sys.stderr)

    # Completed: unique rule names on one line.
    unique_completed = list(dict.fromkeys(g[0].rule_name for g in completed_groups))
    if unique_completed:
        print(f"Found {len(unique_completed)} completed rule(s): {', '.join(unique_completed)}", file=sys.stderr)
    else:
        print("Found 0 completed rules.", file=sys.stderr)

    # Failed: only truly-dead tasks (no active retry). Summary line + one detail line per job.
    if failed_groups:
        all_failed_jobs = [j for g in failed_groups for j in g]
        # Count total job attempts per rule name (xN shows how many times the rule was retried).
        attempt_counts: Counter[str] = Counter(j.rule_name for j in all_failed_jobs)
        unique_names = dict.fromkeys(g[0].rule_name for g in failed_groups)
        name_parts = [f"{n} (x{attempt_counts[n]})" if attempt_counts[n] > 1 else n for n in unique_names]
        print(
            f"Found {len(all_failed_jobs)} failed job(s) across {len(name_parts)} rule(s): {', '.join(name_parts)}",
            file=sys.stderr,
        )
        for j in sorted(all_failed_jobs, key=lambda x: x.submitted_at):
            duration_str = (
                _fmt_duration((j.finished_at - j.submitted_at).total_seconds()) if j.finished_at else "unknown"
            )
            print(
                f" - Rule {j.rule_name} (SLURM jobid {j.slurm_jobid}):"
                f" failed after {duration_str},"
                f" log at {logs_dir / j.log_relative}",
                file=sys.stderr,
            )


def _add_args(parser: argparse.ArgumentParser) -> None:
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
        default=1000,
        metavar="N",
        help="Cap long logs to a head+tail of N lines total with an elision marker (default: 1000).",
    )


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "errors",
        help="Aggregate failing-rule logs into one report.",
        description="Aggregate Babel SLURM error logs into a single copy-pasteable report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  babel-slurm-errors 1.17-try-2
  babel-slurm-errors 1.17-try-2 --markdown
  babel-slurm-errors --traceback-only
""",
    )
    _add_args(parser)
    parser.set_defaults(func=run)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="babel-slurm-errors",
        description="Aggregate Babel SLURM error logs into a single copy-pasteable report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  babel-slurm-errors 1.17-try-2
  babel-slurm-errors 1.17-try-2 --markdown
  babel-slurm-errors --traceback-only
""",
    )
    _add_args(parser)
    run(parser.parse_args())


def run(args: argparse.Namespace) -> None:
    logs_dir = Path(args.logs_dir)
    try:
        err_file = find_err_file(args.version, logs_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    failures = parse_failures(err_file)
    print(build_report(failures, args.markdown, args.traceback_only, args.lines, logs_dir))

    sys.stdout.flush()
    print(f"\n--- Summary (read {err_file}) ---", file=sys.stderr)
    print_job_summary(err_file, logs_dir)
