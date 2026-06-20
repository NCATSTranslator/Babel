"""Recommend right-sized SLURM ``mem`` / ``cpus`` / ``runtime`` from run data.

Joins *actual* usage (Snakemake ``benchmark:`` TSVs) against *requested* resources
(the SLURM efficiency report, falling back to the per-rule logs) and, for each rule,
classifies the fit and recommends a size. The recommendation is the observed peak
times a safety factor, rounded up to a sensible bucket, because an OOM is a hard
kill that wastes the whole job and a single benchmark captures only one run's peak
(inputs grow between runs).

Critically, it lists the rules that would need an *explicit* ``resources:`` override
before the cluster-wide default can be lowered -- the rules whose recommended size
exceeds the proposed new default. Lowering the default without those overrides would
silently starve them (e.g. ``get_uniprotkb_labels`` peaks at ~41 GB on the 64 GB
default with no explicit ``resources:`` block).
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from .parse import read_benchmarks, read_efficiency_report, read_rule_logs

# Buckets in MB (8, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768 GB, 1, 1.5 TB).
_GIB = 1024
MEM_BUCKETS_MB: list[int] = [b * _GIB for b in (8, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536)]

DEFAULT_SAFETY = 1.5
DEFAULT_FLOOR_MB = 8 * _GIB
# Proposed new cluster-wide default to test rules against (slurm/config.yaml).
DEFAULT_NEW_DEFAULT_MEM_MB = 16 * _GIB
DEFAULT_NEW_DEFAULT_CPUS = 1


def recommend_mem_mb(actual_mb: float, safety: float, floor_mb: int) -> int:
    """Round ``actual_mb * safety`` up to the next bucket, never below ``floor_mb``."""
    target = max(actual_mb * safety, floor_mb)
    for bucket in MEM_BUCKETS_MB:
        if bucket >= target:
            return bucket
    # Above the largest bucket: round up to the next whole GiB.
    return int(math.ceil(target / _GIB) * _GIB)


def recommend_cpus(cores_used: float) -> int:
    """Round mean cores used up to a whole CPU, floor of 1."""
    return max(1, math.ceil(cores_used - 1e-9))


def _fmt_gb(mb: float | None) -> str:
    if not mb:
        return "-"
    return f"{mb / _GIB:.1f}G"


@dataclass
class Recommendation:
    rule: str
    actual_mem_mb: float
    requested_mem_mb: float | None
    cores_used: float
    requested_cpus: int | None
    wall_sec: float
    runtime_limit_min: int | None
    rec_mem_mb: int
    rec_cpus: int
    classification: str  # over | ok | at-risk | no-request-data
    needs_override: bool

    @property
    def mem_pct(self) -> float | None:
        if not self.requested_mem_mb:
            return None
        return 100.0 * self.actual_mem_mb / self.requested_mem_mb


def analyze(
    run_dir: str | Path,
    *,
    safety: float = DEFAULT_SAFETY,
    floor_mb: int = DEFAULT_FLOOR_MB,
    new_default_mem_mb: int = DEFAULT_NEW_DEFAULT_MEM_MB,
    new_default_cpus: int = DEFAULT_NEW_DEFAULT_CPUS,
) -> list[Recommendation]:
    """Build per-rule recommendations from the artifacts under ``run_dir``.

    ``run_dir`` is expected to contain ``benchmarks/``, ``logs/`` and (optionally)
    ``reports/slurm/``. Rules are keyed by the benchmark set (actual usage); the
    requested side comes from the efficiency report, falling back to the per-rule
    log's declared ``mem_mb`` / ``cpus_per_task``.
    """
    run_dir = Path(run_dir)
    benchmarks = read_benchmarks(run_dir / "benchmarks")
    try:
        efficiency = read_efficiency_report(run_dir / "reports" / "slurm")
    except FileNotFoundError:
        efficiency = {}
    logs = read_rule_logs(run_dir / "logs")

    recs: list[Recommendation] = []
    for rule, bench in benchmarks.items():
        eff = efficiency.get(rule)
        log = logs.get(rule)

        requested_mem = eff.requested_mem_mb if eff and eff.requested_mem_mb else (log.mem_mb if log else None)
        requested_cpus = eff.ncpus if eff and eff.ncpus else (log.cpus if log else None)
        runtime_limit = log.runtime_min if log else None

        rec_mem = recommend_mem_mb(bench.max_rss_mb, safety, floor_mb)
        rec_cpus = recommend_cpus(bench.cores_used)

        if not requested_mem:
            classification = "no-request-data"
        elif bench.max_rss_mb > 0.8 * requested_mem:
            classification = "at-risk"
        elif requested_mem >= 2 * rec_mem:
            classification = "over"
        else:
            classification = "ok"

        needs_override = rec_mem > new_default_mem_mb or rec_cpus > new_default_cpus

        recs.append(
            Recommendation(
                rule=rule,
                actual_mem_mb=bench.max_rss_mb,
                requested_mem_mb=requested_mem,
                cores_used=bench.cores_used,
                requested_cpus=requested_cpus,
                wall_sec=bench.seconds,
                runtime_limit_min=runtime_limit,
                rec_mem_mb=rec_mem,
                rec_cpus=rec_cpus,
                classification=classification,
                needs_override=needs_override,
            )
        )
    recs.sort(key=lambda r: r.actual_mem_mb, reverse=True)
    return recs


def build_markdown(recs: list[Recommendation], new_default_mem_mb: int, new_default_cpus: int) -> str:
    if not recs:
        return "No benchmark data found."

    total = len(recs)
    over = sum(1 for r in recs if r.classification == "over")
    at_risk = sum(1 for r in recs if r.classification == "at-risk")
    no_data = sum(1 for r in recs if r.classification == "no-request-data")
    overrides = [r for r in recs if r.needs_override]
    # Wasted = requested but unused, summed over rules with a known request.
    wasted_gb = (
        sum(
            (r.requested_mem_mb - r.actual_mem_mb)
            for r in recs
            if r.requested_mem_mb and r.requested_mem_mb > r.actual_mem_mb
        )
        / _GIB
    )

    lines: list[str] = []
    lines.append("# SLURM resource analysis")
    lines.append("")
    lines.append(
        f"Rules with benchmarks: {total}  |  over-provisioned: {over}  |  at-risk: {at_risk}  |  no request data: {no_data}"
    )
    lines.append(f"Wasted reservation (requested minus used): {wasted_gb:.0f} GB across rules with a known request.")
    lines.append("")
    lines.append(
        f"Proposed new default: mem={new_default_mem_mb // _GIB}G, cpus={new_default_cpus}. "
        f"{len(overrides)} rule(s) need an explicit override first (below)."
    )
    lines.append("")
    lines.append("## Rules needing an explicit override before lowering the default")
    lines.append("")
    if overrides:
        lines.append("rule | actual RSS | rec mem | rec cpus")
        lines.append("---- | ---------- | ------- | --------")
        for r in overrides:
            lines.append(f"{r.rule} | {_fmt_gb(r.actual_mem_mb)} | {_fmt_gb(r.rec_mem_mb)} | {r.rec_cpus}")
    else:
        lines.append("(none — the proposed default already covers every rule)")
    lines.append("")
    lines.append("## All rules (by actual peak RSS)")
    lines.append("")
    lines.append("rule | actual RSS | req mem | mem% | cores | req cpus | wall | rec mem | rec cpus | class")
    lines.append("---- | ---------- | ------- | ---- | ----- | -------- | ---- | ------- | -------- | -----")
    for r in recs:
        pct = f"{r.mem_pct:.0f}%" if r.mem_pct is not None else "-"
        lines.append(
            f"{r.rule} | {_fmt_gb(r.actual_mem_mb)} | {_fmt_gb(r.requested_mem_mb)} | {pct} | "
            f"{r.cores_used:.1f} | {r.requested_cpus or '-'} | {r.wall_sec:.0f}s | "
            f"{_fmt_gb(r.rec_mem_mb)} | {r.rec_cpus} | {r.classification}"
        )
    return "\n".join(lines)


def write_csv(recs: list[Recommendation], path: str | Path) -> None:
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rule",
                "actual_rss_mb",
                "requested_mem_mb",
                "mem_pct",
                "cores_used",
                "requested_cpus",
                "wall_sec",
                "runtime_limit_min",
                "rec_mem_mb",
                "rec_cpus",
                "classification",
                "needs_override",
            ]
        )
        for r in recs:
            writer.writerow(
                [
                    r.rule,
                    f"{r.actual_mem_mb:.1f}",
                    f"{r.requested_mem_mb:.0f}" if r.requested_mem_mb else "",
                    f"{r.mem_pct:.1f}" if r.mem_pct is not None else "",
                    f"{r.cores_used:.2f}",
                    r.requested_cpus if r.requested_cpus else "",
                    f"{r.wall_sec:.0f}",
                    r.runtime_limit_min if r.runtime_limit_min else "",
                    r.rec_mem_mb,
                    r.rec_cpus,
                    r.classification,
                    int(r.needs_override),
                ]
            )


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "resources",
        help="Recommend right-sized mem/cpus/runtime from benchmark + efficiency data.",
        description="Compare actual resource usage against requested resources and recommend right-sized limits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  uv run python -m tools.slurm resources data/babel-1.17
  uv run python -m tools.slurm resources data/babel-1.17 --csv /tmp/resources.csv
  uv run python -m tools.slurm resources data/babel-1.17 --new-default-mem-gb 16 --safety 2.0
""",
    )
    parser.add_argument("run_dir", help="Run-analysis directory with benchmarks/, logs/, reports/slurm/.")
    parser.add_argument(
        "--safety", type=float, default=DEFAULT_SAFETY, help=f"Safety factor on peak RSS (default: {DEFAULT_SAFETY})."
    )
    parser.add_argument(
        "--floor-gb", type=int, default=DEFAULT_FLOOR_MB // _GIB, help="Minimum recommended mem in GB (default: 8)."
    )
    parser.add_argument(
        "--new-default-mem-gb",
        type=int,
        default=DEFAULT_NEW_DEFAULT_MEM_MB // _GIB,
        help="Proposed new cluster default mem in GB to test rules against (default: 16).",
    )
    parser.add_argument(
        "--new-default-cpus",
        type=int,
        default=DEFAULT_NEW_DEFAULT_CPUS,
        help="Proposed new cluster default cpus to test rules against (default: 1).",
    )
    parser.add_argument("--csv", metavar="PATH", help="Also write the full per-rule table to this CSV.")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"error: not a directory: {run_dir}", file=sys.stderr)
        sys.exit(1)

    new_default_mem_mb = args.new_default_mem_gb * _GIB
    recs = analyze(
        run_dir,
        safety=args.safety,
        floor_mb=args.floor_gb * _GIB,
        new_default_mem_mb=new_default_mem_mb,
        new_default_cpus=args.new_default_cpus,
    )
    if args.csv:
        write_csv(recs, args.csv)
        print(f"Wrote {len(recs)} rows to {args.csv}", file=sys.stderr)
    print(build_markdown(recs, new_default_mem_mb, args.new_default_cpus))
