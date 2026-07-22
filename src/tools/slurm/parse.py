"""Shared parsers for Babel SLURM run artifacts.

Three kinds of artifact are produced by a Snakemake-on-SLURM run and copied into a
run-analysis directory such as ``data/babel-1.17/``:

- ``benchmarks/<rule>.tsv``     — Snakemake ``benchmark:`` output (actual usage).
- ``reports/slurm/slurm_efficiency_reports/`` — the SLURM executor's efficiency
  report (a *directory* containing ``efficiency_report_*.csv``).
- ``logs/rule_<name>/<jobid>.log`` — per-rule control-node logs (declared resources,
  timestamps, tracebacks).

Every reader tolerates partial runs and missing/``NA``/``-`` cells.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# --- numeric helpers ---------------------------------------------------------


def _to_float(value: str | None) -> float:
    """Parse a benchmark/report cell to float; missing markers become 0.0."""
    if value is None:
        return 0.0
    value = value.strip()
    if value in ("", "-", "NA", "nan"):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


# --- benchmark TSVs ----------------------------------------------------------


@dataclass
class Benchmark:
    """Worst-case actual resource usage for a rule across its benchmark rows.

    A benchmark TSV usually holds one row, but ``repeat()`` runs append more; we
    keep the per-column maximum so sizing decisions reflect the worst observed run.
    Memory figures are megabytes (Snakemake's benchmark unit); ``mean_load`` is a
    percentage where 100% == one fully-used core.
    """

    rule: str
    seconds: float
    max_rss_mb: float
    max_vms_mb: float
    max_pss_mb: float
    cpu_time: float
    mean_load: float
    io_in: float
    io_out: float

    @property
    def cores_used(self) -> float:
        """Approximate mean cores used (``mean_load`` is %CPU, 100% == 1 core)."""
        return self.mean_load / 100.0


def read_benchmarks(benchmarks_dir: str | Path) -> dict[str, Benchmark]:
    """Read every ``*.tsv`` benchmark in ``benchmarks_dir`` keyed by rule name.

    The rule name is the file stem (``anatomy_compendia.tsv`` -> ``anatomy_compendia``).
    """
    benchmarks_dir = Path(benchmarks_dir)
    result: dict[str, Benchmark] = {}
    for path in sorted(benchmarks_dir.glob("*.tsv")):
        with open(path, newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        if not rows:
            continue
        rule = path.stem
        result[rule] = Benchmark(
            rule=rule,
            seconds=max(_to_float(r.get("s")) for r in rows),
            max_rss_mb=max(_to_float(r.get("max_rss")) for r in rows),
            max_vms_mb=max(_to_float(r.get("max_vms")) for r in rows),
            max_pss_mb=max(_to_float(r.get("max_pss")) for r in rows),
            cpu_time=max(_to_float(r.get("cpu_time")) for r in rows),
            mean_load=max(_to_float(r.get("mean_load")) for r in rows),
            io_in=max(_to_float(r.get("io_in")) for r in rows),
            io_out=max(_to_float(r.get("io_out")) for r in rows),
        )
    return result


# --- SLURM efficiency report -------------------------------------------------


@dataclass
class EfficiencyRow:
    """Per-rule row from the SLURM executor's efficiency report.

    ``max_rss_mb`` and ``total_cpu_sec`` are frequently 0 on clusters without
    ``jobacct_gather``/cgroup accounting (the reason we trust :class:`Benchmark`
    for usage). ``requested_mem_mb`` and ``ncpus`` are always reliable.
    """

    rule: str
    requested_mem_mb: float
    ncpus: int
    elapsed_sec: float
    total_cpu_sec: float
    max_rss_mb: float


def _efficiency_csvs(path: str | Path) -> list[Path]:
    """Resolve *every* efficiency CSV shard from a file, the ``*.csv`` directory, or a parent.

    The SLURM executor writes ``slurm_efficiency_reports`` as a *directory* and appends a
    fresh ``efficiency_report_<uuid>.csv`` on every Snakemake (re)start, so a single run leaves
    many shards, each covering only the jobs from that invocation. We must read **all** of them
    -- picking just the newest (as an earlier version did) drops almost every rule, since the
    final restart usually re-ran only a handful of jobs.
    """
    path = Path(path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"No efficiency report found at {path}")
    candidates = sorted(path.rglob("efficiency_report_*.csv")) or sorted(path.rglob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No efficiency report CSV under {path}")
    return candidates


def read_efficiency_report(path: str | Path) -> dict[str, EfficiencyRow]:
    """Read the SLURM efficiency report keyed by rule name (``rule_`` prefix stripped).

    Merges every shard (see :func:`_efficiency_csvs`); when a rule appears in more than one shard
    (retries across restarts) we keep the per-column worst case, mirroring how
    :func:`read_benchmarks` keeps the worst observed run.
    """
    result: dict[str, EfficiencyRow] = {}
    for csv_path in _efficiency_csvs(path):
        with open(csv_path, newline="") as handle:
            for row in csv.DictReader(handle):
                rule = (row.get("RuleName") or "").strip()
                if rule.startswith("rule_"):
                    rule = rule[len("rule_") :]
                if not rule:
                    continue
                new = EfficiencyRow(
                    rule=rule,
                    requested_mem_mb=_to_float(row.get("RequestedMem_MB")),
                    ncpus=int(_to_float(row.get("NCPUS"))),
                    elapsed_sec=_to_float(row.get("Elapsed_sec")),
                    total_cpu_sec=_to_float(row.get("TotalCPU_sec")),
                    max_rss_mb=_to_float(row.get("MaxRSS_MB")),
                )
                prev = result.get(rule)
                if prev is None:
                    result[rule] = new
                else:
                    result[rule] = EfficiencyRow(
                        rule=rule,
                        requested_mem_mb=max(prev.requested_mem_mb, new.requested_mem_mb),
                        ncpus=max(prev.ncpus, new.ncpus),
                        elapsed_sec=max(prev.elapsed_sec, new.elapsed_sec),
                        total_cpu_sec=max(prev.total_cpu_sec, new.total_cpu_sec),
                        max_rss_mb=max(prev.max_rss_mb, new.max_rss_mb),
                    )
    return result


# --- per-rule control-node logs ---------------------------------------------

_MEM_RE = re.compile(r"\bmem_mb=(\d+)")
_RUNTIME_RE = re.compile(r"\bruntime=(\d+)")
_CPUS_RE = re.compile(r"\bcpus_per_task=(\d+)")
_BRACKET_TS_RE = re.compile(r"\[(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\w+ +\d+ [\d:]+ \d{4})\]")
_FAILURE_RE = re.compile(r"Error in rule |RuleException|Traceback \(most recent call last\):")


@dataclass
class RuleLog:
    """Declared resources, wall-clock span, and failure state from a rule's log."""

    rule: str
    job_id: str
    log_path: Path
    mem_mb: int | None
    runtime_min: int | None
    cpus: int | None
    start: datetime | None
    end: datetime | None
    failed: bool


def _parse_bracket_timestamps(text: str) -> tuple[datetime | None, datetime | None]:
    stamps = []
    for match in _BRACKET_TS_RE.finditer(text):
        try:
            stamps.append(datetime.strptime(match.group(1), "%b %d %H:%M:%S %Y"))
        except ValueError:
            continue
    if not stamps:
        return None, None
    return stamps[0], stamps[-1]


def read_rule_logs(logs_dir: str | Path) -> dict[str, RuleLog]:
    """Walk ``logs_dir/rule_<name>/<jobid>.log`` and summarize each rule.

    When a rule has several job logs (retries), the declared resources come from
    the newest log and ``failed`` is True if *any* attempt's log shows a failure.
    """
    logs_dir = Path(logs_dir)
    result: dict[str, RuleLog] = {}
    for rule_dir in sorted(logs_dir.glob("rule_*")):
        if not rule_dir.is_dir():
            continue
        rule = rule_dir.name[len("rule_") :]
        logs = sorted(rule_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
        if not logs:
            continue
        any_failed = False
        newest = logs[-1]
        newest_text = ""
        for log in logs:
            text = log.read_text(errors="replace")
            if _FAILURE_RE.search(text):
                any_failed = True
            if log == newest:
                newest_text = text
        text = newest_text
        mem = _MEM_RE.search(text)
        runtime = _RUNTIME_RE.search(text)
        cpus = _CPUS_RE.search(text)
        start, end = _parse_bracket_timestamps(text)
        result[rule] = RuleLog(
            rule=rule,
            job_id=newest.stem,
            log_path=newest,
            mem_mb=int(mem.group(1)) if mem else None,
            runtime_min=int(runtime.group(1)) if runtime else None,
            cpus=int(cpus.group(1)) if cpus else None,
            start=start,
            end=end,
            failed=any_failed,
        )
    return result


# --- aggregate sbatch error log (used by the ``errors`` subcommand) ----------

_SUBMIT_RE = re.compile(
    r"(?:INFO|ERROR) snakemake\.logging \[(\S+)\]: Job (\d+) has been submitted with SLURM jobid (\d+) \(log: (\S+)\)\."
)
_FINISH_RE = re.compile(r"(?:INFO|ERROR) snakemake\.logging \[(\S+)\]: Finished jobid: (\d+) \(Rule: (\w+)\)")
_ERROR_RE = re.compile(r"ERROR snakemake\.logging \[(\S+)\]: Error in rule (\w+), jobid: (\d+)")
_RULE_RE = re.compile(r"Error in rule (\w+):")
_LOG_RE = re.compile(r"log: (\S+\.log)")

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

# Characters that only appear in DuckDB's in-place progress bar. Snakemake captures every
# carriage-return redraw, so a single "line" can be hundreds of KB of repeated bar frames; we
# collapse any run of them to one marker so the full log stays readable.
_PROGRESS_BAR_RE = re.compile(r"[▕▏█▎▍▌▋▊▉▐]")


def find_err_file(version: str | None, logs_dir: Path) -> Path:
    """Locate the main Snakemake ``sbatch-<version>.err`` control-node log."""
    if version:
        path = logs_dir / f"sbatch-{version}.err"
        if not path.exists():
            raise FileNotFoundError(f"Error log not found: {path}")
        return path
    candidates = list(logs_dir.glob("sbatch-*.err"))
    if not candidates:
        raise FileNotFoundError(f"No sbatch-*.err files found in {logs_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def parse_failures(err_file: Path) -> list[tuple[str, Path]]:
    """Return ``(rule_name, log_path)`` pairs from the main Snakemake error log."""
    results: list[tuple[str, Path]] = []
    current_rule: str | None = None
    for line in err_file.read_text(errors="replace").splitlines():
        if m := _RULE_RE.search(line):
            current_rule = m.group(1)
        if (m := _LOG_RE.search(line)) and current_rule:
            results.append((current_rule, Path(m.group(1))))
            current_rule = None
    return results


def _collect_memory_diagnostics(lines: list[str]) -> list[str]:
    """Return the DuckDB memory-diagnostic lines anywhere in the log, in order, de-duplicated."""
    return list(
        dict.fromkeys(line.rstrip() for line in lines if any(marker in line for marker in _MEMORY_DIAGNOSTIC_MARKERS))
    )


def _collapse_progress_noise(lines: list[str]) -> list[str]:
    """Replace each run of DuckDB progress-bar redraw lines with a single elision marker."""
    cleaned: list[str] = []
    in_progress = False
    for line in lines:
        if _PROGRESS_BAR_RE.search(line):
            if not in_progress:
                cleaned.append("[... DuckDB progress-bar output elided ...]")
                in_progress = True
            continue
        in_progress = False
        cleaned.append(line)
    return cleaned


def extract_error_content(log_path: Path, max_lines: int, logs_dir: Path | None = None) -> str:
    """Return the failed rule's log for the report.

    We show the *whole* log (so the real exception is never hidden by tail/traceback heuristics --
    Snakemake's RuleException/OutOfMemory blocks are neither a Python "Traceback" nor always within
    the last N lines), with two cleanups: DuckDB's progress-bar redraw spam is collapsed, and the
    memory-diagnostic lines are echoed in a labelled section at the end so they are easy to find.
    ``max_lines`` caps a pathologically long log to a head + tail so the report stays usable.

    The main error log records each rule's log by its *absolute* path on the cluster. When
    analyzing a run copied off the cluster, that path won't resolve, so if ``logs_dir`` is given we
    fall back to the same ``rule_<name>/<jobid>.log`` under it (the relative form
    :func:`print_job_summary` already uses).
    """
    if not log_path.exists() and logs_dir is not None:
        local = logs_dir / log_relative(str(log_path))
        if local.exists():
            log_path = local
    if not log_path.exists():
        return f"(log file not found: {log_path})"

    raw_lines = log_path.read_text(errors="replace").splitlines()
    lines = _collapse_progress_noise(raw_lines)

    # Show the full (de-spammed) log, but guard against a pathologically long one by keeping a
    # generous head and tail. The cap is large enough that ordinary rule logs are shown in full.
    if len(lines) > max_lines:
        head = lines[: max_lines // 4]
        tail = lines[-(max_lines - max_lines // 4) :]
        elided = len(lines) - len(head) - len(tail)
        content = "\n".join(head + [f"[... {elided} log lines elided ...]"] + tail)
    else:
        content = "\n".join(lines)

    # Echo the memory diagnostics in a clearly-labelled trailer so they are easy to find even in a
    # long log (and present even if the head/tail cap dropped them).
    diagnostics = _collect_memory_diagnostics(raw_lines)
    if diagnostics:
        content += "\n\n--- DuckDB memory diagnostics ---\n" + "\n".join(diagnostics)

    return content


# --- job-event timeline (used by the ``errors`` subcommand's run summary) ----


@dataclass
class JobEvent:
    """One SLURM job attempt parsed from the main Snakemake error log."""

    snakemake_jobid: int
    slurm_jobid: int
    rule_name: str
    wildcard: str  # "" for simple rules; "Cell.txt" etc. for parametrised rules
    log_relative: str  # e.g. rule_get_HMDB/672.log
    submitted_at: datetime
    finished_at: datetime | None = None
    failed: bool = False


_TZ_OFFSET_RE = re.compile(r"([+-])(\d{2})(\d{2})$")


def _parse_ts(ts_str: str) -> datetime:
    # Normalise any bare ±HHMM offset → ±HH:MM for Python < 3.11 fromisoformat compatibility.
    ts_str = _TZ_OFFSET_RE.sub(r"\1\2:\3", ts_str)
    return datetime.fromisoformat(ts_str)


def log_relative(remote_log_path: str) -> str:
    """Extract the logs-dir-relative path (``rule_FOO/.../N.log``) from a remote path."""
    parts = remote_log_path.split("/rule_", 1)
    return ("rule_" + parts[1]) if len(parts) == 2 else remote_log_path


def declared_runtime_min(log_relative_path: str, logs_dir: Path, default: int = 120) -> int:
    """Read the declared ``runtime=`` (minutes) from a job's per-rule log, or ``default``."""
    local_log = logs_dir / log_relative_path
    if not local_log.exists():
        return default
    for line in local_log.read_text(errors="replace").splitlines():
        if "resources:" in line:
            if m := _RUNTIME_RE.search(line):
                return int(m.group(1))
    return default


def parse_job_events(err_file: Path) -> list[JobEvent]:
    """Return the SLURM job attempts parsed from the main Snakemake error log."""
    # Snakemake reuses the same snakemake jobid across retries, so we track both the
    # currently-open attempt per snakemake jobid and all superseded attempts separately.
    current: dict[int, JobEvent] = {}
    all_jobs: list[JobEvent] = []
    for line in err_file.read_text(errors="replace").splitlines():
        if m := _SUBMIT_RE.search(line):
            ts, snakemake_id, slurm_id, log_path = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            rel = log_relative(log_path)
            parts = rel.split("/")
            rule = parts[0][len("rule_") :]
            wildcard = "/".join(parts[1:-1])
            if snakemake_id in current:
                all_jobs.append(current[snakemake_id])  # save prior attempt before retry overwrites it
            current[snakemake_id] = JobEvent(
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
