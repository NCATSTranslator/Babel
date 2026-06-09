#!/usr/bin/env python3
"""Aggregate Babel SLURM rule error logs into a single report for debugging."""

import argparse
import dataclasses
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path

_SUBMIT_RE = re.compile(
    r"(?:INFO|ERROR) snakemake\.logging \[(\S+)\]: "
    r"Job (\d+) has been submitted with SLURM jobid (\d+) \(log: (\S+)\)\."
)
_FINISH_RE = re.compile(
    r"(?:INFO|ERROR) snakemake\.logging \[(\S+)\]: "
    r"Finished jobid: (\d+) \(Rule: (\w+)\)"
)
_ERROR_RE = re.compile(
    r"ERROR snakemake\.logging \[(\S+)\]: "
    r"Error in rule (\w+), jobid: (\d+)"
)
_RUNTIME_RE = re.compile(r"\bruntime=(\d+)\b")

# Substrings identifying the DuckDB memory-diagnostic log lines emitted by
# src/exporters/duckdb_exporters.py. These pinpoint cgroup vs memory_limit headroom and the
# tracked/untracked split at a `bad allocation` OOM. The connect-time headroom line sits near the
# top of the log and the threads>1 SIGABRT path leaves no traceback, so the default
# "last N lines" / traceback extraction misses them; we scan the whole log and surface them
# explicitly. (We deliberately do not match the verbose per-setting dump, e.g. " - memory_limit:".)
_MEMORY_DIAGNOSTIC_MARKERS = (
    "DuckDB memory headroom:",
    "Memory snapshot (",
    "DuckDB operation failed during",
)


@dataclasses.dataclass
class _JobEvent:
    snakemake_jobid: int
    slurm_jobid: int
    rule_name: str
    wildcard: str  # "" for simple rules; "Cell.txt" etc. for parametrised rules
    log_relative: str  # e.g. rule_get_HMDB/672.log
    submitted_at: datetime
    finished_at: datetime | None = None
    failed: bool = False


def _parse_ts(ts_str: str) -> datetime:
    # Normalise +0000 → +00:00 for Python < 3.11 fromisoformat compatibility.
    return datetime.fromisoformat(ts_str.replace("+0000", "+00:00"))


def _fmt_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def _log_relative(remote_log_path: str) -> str:
    """Extract the logs-dir-relative path (rule_FOO/.../N.log) from a remote path."""
    parts = remote_log_path.split("/rule_", 1)
    return ("rule_" + parts[1]) if len(parts) == 2 else remote_log_path


def _get_runtime_minutes(log_relative: str, logs_dir: Path, default: int = 120) -> int:
    local_log = logs_dir / log_relative
    if not local_log.exists():
        return default
    for line in local_log.read_text(errors="replace").splitlines():
        if "resources:" in line:
            m = _RUNTIME_RE.search(line)
            if m:
                return int(m.group(1))
    return default


def _parse_job_events(err_file: Path) -> list[_JobEvent]:
    """Return a list of SLURM job events parsed from the main Snakemake error log."""
    # Snakemake reuses the same snakemake jobid across retries, so we track both the
    # currently-open attempt per snakemake jobid and all superseded attempts separately.
    current: dict[int, _JobEvent] = {}
    all_jobs: list[_JobEvent] = []
    for line in err_file.read_text(errors="replace").splitlines():
        if m := _SUBMIT_RE.search(line):
            ts, snakemake_id, slurm_id, log_path = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            rel = _log_relative(log_path)
            parts = rel.split("/")
            rule = parts[0][len("rule_") :]
            wildcard = "/".join(parts[1:-1])
            if snakemake_id in current:
                all_jobs.append(current[snakemake_id])  # save prior attempt before retry overwrites it
            current[snakemake_id] = _JobEvent(
                snakemake_jobid=snakemake_id,
                slurm_jobid=slurm_id,
                rule_name=rule,
                wildcard=wildcard,
                log_relative=rel,
                submitted_at=_parse_ts(ts),
            )
        elif m := _FINISH_RE.search(line):
            snakemake_id = int(m.group(2))
            if snakemake_id in current:
                current[snakemake_id].finished_at = _parse_ts(m.group(1))
        elif m := _ERROR_RE.search(line):
            snakemake_id = int(m.group(3))
            if snakemake_id in current:
                current[snakemake_id].failed = True
                current[snakemake_id].finished_at = _parse_ts(m.group(1))
    all_jobs.extend(current.values())
    return all_jobs


def print_job_summary(err_file: Path, logs_dir: Path) -> None:
    jobs = _parse_job_events(err_file)
    if not jobs:
        return

    now = datetime.now(UTC)

    # Group jobs by logical task (rule + wildcard), sorted by submission time within each group.
    sorted_jobs = sorted(jobs, key=lambda j: (j.rule_name, j.wildcard, j.submitted_at))
    completed_groups: list[list[_JobEvent]] = []
    failed_groups: list[list[_JobEvent]] = []
    incomplete_groups: list[list[_JobEvent]] = []
    for _, grp in groupby(sorted_jobs, key=lambda j: (j.rule_name, j.wildcard)):
        group = list(grp)
        running = [j for j in group if not j.finished_at and not j.failed]
        if running:
            incomplete_groups.append(group)
        elif any(j.finished_at and not j.failed for j in group):
            completed_groups.append(group)
        else:
            failed_groups.append(group)

    # Incomplete: one line per running job, with indented prior-failure sub-lines if retried.
    if incomplete_groups:
        print(f"Found {len(incomplete_groups)} incomplete rule(s):", file=sys.stderr)
        for group in sorted(incomplete_groups, key=lambda g: g[0].submitted_at):
            running = [j for j in group if not j.finished_at and not j.failed]
            prior_failures = [j for j in group if j.failed]
            j = running[0]
            elapsed = (now - j.submitted_at).total_seconds()
            timeout_min = _get_runtime_minutes(j.log_relative, logs_dir)
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
    seen: set[str] = set()
    unique_completed: list[str] = []
    for group in completed_groups:
        name = group[0].rule_name
        if name not in seen:
            seen.add(name)
            unique_completed.append(name)
    if unique_completed:
        print(f"Found {len(unique_completed)} completed rule(s): {', '.join(unique_completed)}", file=sys.stderr)
    else:
        print("Found 0 completed rules.", file=sys.stderr)

    # Failed: only truly-dead tasks (no active retry). Summary line + one detail line per job.
    if failed_groups:
        all_failed_jobs = [j for g in failed_groups for j in g]
        # Count total job attempts per rule name (xN shows how many times the rule was retried).
        attempt_counts: Counter[str] = Counter(j.rule_name for j in all_failed_jobs)
        seen_names: set[str] = set()
        name_parts: list[str] = []
        for group in failed_groups:
            name = group[0].rule_name
            if name not in seen_names:
                seen_names.add(name)
                c = attempt_counts[name]
                name_parts.append(f"{name} (x{c})" if c > 1 else name)
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


def _collect_memory_diagnostics(lines: list[str]) -> list[str]:
    """Return the DuckDB memory-diagnostic lines anywhere in the log, in order, de-duplicated."""
    found: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if any(marker in line for marker in _MEMORY_DIAGNOSTIC_MARKERS):
            stripped = line.rstrip()
            if stripped not in seen:
                seen.add(stripped)
                found.append(stripped)
    return found


def extract_error_content(log_path: Path, fallback_lines: int) -> str:
    if not log_path.exists():
        return f"(log file not found: {log_path})"

    lines = log_path.read_text(errors="replace").splitlines()

    # Use the last Python traceback block if present, otherwise the tail of the log.
    last_tb_start: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Traceback (most recent call last):"):
            last_tb_start = i

    content = "\n".join(lines[last_tb_start:]) if last_tb_start is not None else "\n".join(lines[-fallback_lines:])

    # Surface the DuckDB memory diagnostics even when they fall outside the extracted slice: the
    # connect-time headroom line is near the top of the log, and a threads>1 background-thread OOM
    # aborts with SIGABRT and no traceback. Only append the lines not already shown.
    extras = [line for line in _collect_memory_diagnostics(lines) if line not in content]
    if extras:
        content = content + "\n\n--- DuckDB memory diagnostics (from elsewhere in log) ---\n" + "\n".join(extras)

    return content


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

    failures = parse_failures(err_file)
    if failures:
        print(build_report(failures, args.markdown, args.traceback_only, args.lines))

    sys.stdout.flush()
    print(f"\n--- Summary (read {err_file}) ---", file=sys.stderr)
    print_job_summary(err_file, logs_dir)


if __name__ == "__main__":
    main()
