"""Shared parsers for Babel SLURM run artifacts.

Three kinds of artifact are produced by a Snakemake-on-SLURM run and copied into a
run-analysis directory such as ``data/babel-1.17/``:

- ``benchmarks/<rule>.tsv``     — Snakemake ``benchmark:`` output (actual usage).
- ``reports/slurm/slurm_efficiency_report.csv/`` — the SLURM executor's efficiency
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


def _resolve_efficiency_csv(path: str | Path) -> Path:
    """Resolve the efficiency CSV from a file, the ``*.csv`` directory, or a parent.

    The SLURM executor writes ``slurm_efficiency_report.csv`` as a *directory*
    containing ``efficiency_report_<uuid>.csv`` files; accept any of:
    the inner CSV file, that directory, or a run dir containing
    ``reports/slurm/...``. Picks the newest CSV when several exist.
    """
    path = Path(path)
    if path.is_file():
        return path
    candidates: list[Path]
    if path.is_dir():
        candidates = sorted(path.rglob("efficiency_report_*.csv"))
        if not candidates:
            candidates = sorted(path.rglob("*.csv"))
    else:
        raise FileNotFoundError(f"No efficiency report found at {path}")
    if not candidates:
        raise FileNotFoundError(f"No efficiency report CSV under {path}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_efficiency_report(path: str | Path) -> dict[str, EfficiencyRow]:
    """Read the SLURM efficiency report keyed by rule name (``rule_`` prefix stripped)."""
    csv_path = _resolve_efficiency_csv(path)
    result: dict[str, EfficiencyRow] = {}
    with open(csv_path, newline="") as handle:
        for row in csv.DictReader(handle):
            rule = (row.get("RuleName") or "").strip()
            if rule.startswith("rule_"):
                rule = rule[len("rule_") :]
            if not rule:
                continue
            result[rule] = EfficiencyRow(
                rule=rule,
                requested_mem_mb=_to_float(row.get("RequestedMem_MB")),
                ncpus=int(_to_float(row.get("NCPUS"))),
                elapsed_sec=_to_float(row.get("Elapsed_sec")),
                total_cpu_sec=_to_float(row.get("TotalCPU_sec")),
                max_rss_mb=_to_float(row.get("MaxRSS_MB")),
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
        for log in logs:
            text = log.read_text(errors="replace")
            if _FAILURE_RE.search(text):
                any_failed = True
        text = newest.read_text(errors="replace")
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


def find_err_file(version: str | None, logs_dir: Path) -> Path:
    """Locate the main Snakemake ``sbatch-<version>.err`` control-node log."""
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
    """Return ``(rule_name, log_path)`` pairs from the main Snakemake error log."""
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
    """Return the last traceback block from a log, or its trailing lines."""
    if not log_path.exists():
        return f"(log file not found: {log_path})"

    lines = log_path.read_text(errors="replace").splitlines()

    last_tb_start: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Traceback (most recent call last):"):
            last_tb_start = i

    if last_tb_start is not None:
        return "\n".join(lines[last_tb_start:])

    return "\n".join(lines[-fallback_lines:])
