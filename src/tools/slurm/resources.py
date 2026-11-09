"""Recommend right-sized SLURM ``mem`` / ``cpus`` from run data.

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
from collections import Counter
from dataclasses import dataclass, fields
from pathlib import Path
from typing import TypeVar

from src.util import get_repo_root

from .parse import Benchmark, read_benchmarks, read_efficiency_report, read_rule_logs, read_snakefile_resources

# Every memory figure in this module is **decimal MB**, the unit SLURM and Snakemake use: `mem="8G"`
# reaches the scheduler as 8000 MB, and the efficiency report's RequestedMem_MB is decimal too. That
# makes a recommendation here literally the string to paste into a `resources:` block.
#
# Snakemake's benchmark TSVs are the one exception -- their "MB" columns are really mebibytes
# (psutil bytes / 1024 / 1024) -- so they are converted on the way in, at the single point in
# analyze() that reads them. Getting this wrong is a ~4.9% error in the *unsafe* direction: it makes
# a rule look further from its limit than it is.
_MB_PER_GB = 1000
MIB_TO_MB = 1.048576
MEM_BUCKETS_MB: list[int] = [
    b * _MB_PER_GB for b in (8, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536)
]

# Wall-time buckets in minutes (30m, 1h, 2h, 3h, 4h, 6h, 8h, 12h, 18h, 24h, 36h, 48h). Snakemake's
# `runtime` is minutes; these are the round numbers a `resources:` block would actually declare.
RUNTIME_BUCKETS_MIN: list[int] = [30, 60, 120, 180, 240, 360, 480, 720, 1080, 1440, 2160, 2880]

DEFAULT_SAFETY = 1.5
DEFAULT_FLOOR_MB = 8 * _MB_PER_GB
# Proposed new cluster-wide default to test rules against (slurm/config.yaml).
DEFAULT_NEW_DEFAULT_MEM_MB = 16 * _MB_PER_GB
DEFAULT_NEW_DEFAULT_CPUS = 1
# The cluster-wide default runtime a rule gets with no `resources:` block (slurm/config.yaml).
DEFAULT_RUNTIME_MIN = 120
# A rule using more than this fraction of its limit is one bad run away from being killed.
AT_RISK_FRACTION = 0.8


def recommend_mem_mb(actual_mb: float, safety: float, floor_mb: int) -> int:
    """Round ``actual_mb * safety`` up to the next bucket, never below ``floor_mb``."""
    target = max(actual_mb * safety, floor_mb)
    for bucket in MEM_BUCKETS_MB:
        if bucket >= target:
            return bucket
    # Above the largest bucket: round up to the next whole GB.
    return int(math.ceil(target / _MB_PER_GB) * _MB_PER_GB)


def recommend_cpus(cores_used: float) -> int:
    """Round mean cores used up to a whole CPU, floor of 1."""
    return max(1, math.ceil(cores_used - 1e-9))


def recommend_runtime_min(wall_sec: float, safety: float) -> int:
    """Round ``wall_sec * safety`` up to the next runtime bucket.

    Same reasoning as the memory recommendation -- a timeout kills the job outright and one run's
    wall time is a single sample -- but time also matters in the other direction: a limit far above
    the real duration makes Snakemake's remaining-time estimates useless and hides a job that has
    become pathologically slow, so the buckets stay tight rather than defaulting to "plenty".
    """
    target = wall_sec * safety / 60.0
    for bucket in RUNTIME_BUCKETS_MIN:
        if bucket >= target:
            return bucket
    return int(math.ceil(target / 60.0) * 60)


def rule_for_benchmark(stem: str, rule_names: list[str]) -> str:
    """Map a per-instance artifact key back to its rule name.

    A wildcard rule writes one benchmark per wildcard value
    (``export_compendia_to_duckdb_SmallMolecule.tsv`` for rule ``export_compendia_to_duckdb``) and one
    efficiency-report row per SLURM job (``export_compendia_to_duckdb_wildcards_SmallMolecule``), so an
    exact match is tried first and then the longest rule name the key extends. Falls back to the key
    itself, which is what a rule with no snakefile match would have been keyed by anyway.
    """
    if stem in rule_names:
        return stem
    for name in sorted(rule_names, key=len, reverse=True):
        if stem.startswith(name + "_"):
            return name
    return stem


_T = TypeVar("_T")


def group_by_rule(items: dict[str, _T], rule_names: list[str]) -> dict[str, list[_T]]:
    """Bucket per-instance artifacts (benchmarks, efficiency rows) under the rule they belong to.

    Everything on the *declared* side -- a snakefile's ``resources:`` block, ``slurm/README.md``,
    the recommendation this tool prints -- is per rule, so the analysis has to be too. Scoring each
    wildcard instance separately is wrong in both directions: the small instances are measured
    against a limit sized for the largest one (all ~24 ``generate_kgx`` instances read as ``over``
    against the limit ``generate_kgx_Publication`` needs), and each of them casts its own vote in
    :func:`detect_run_default_mem_mb`'s mode, which is enough to elect a wildcard rule's declared mem
    as "the run default".
    """
    grouped: dict[str, list[_T]] = {}
    for key, value in items.items():
        grouped.setdefault(rule_for_benchmark(key, rule_names), []).append(value)
    return grouped


def worst_case(rule: str, benchmarks: list[Benchmark]) -> Benchmark:
    """Fold a rule's wildcard instances into one per-column worst case.

    The same reduction :func:`read_benchmarks` already applies across the rows of a single
    ``repeat()``-ed benchmark, one level up: a rule needs enough memory and wall time for its
    *largest* instance. Columns may come from different instances, which is what a single limit
    covering all of them has to allow for anyway.
    """
    peaks = {f.name: max(getattr(b, f.name) for b in benchmarks) for f in fields(Benchmark) if f.name != "rule"}
    return Benchmark(rule=rule, **peaks)


def _fmt_gb(mb: float | None) -> str:
    if mb is None:
        return "-"
    return f"{mb / _MB_PER_GB:.1f}G"


def _fmt_min(minutes: float | None) -> str:
    """Minutes as `45m` or `7.0h`, so a 24-hour limit doesn't read as a four-digit number."""
    if minutes is None:
        return "-"
    return f"{minutes:.0f}m" if minutes < 90 else f"{minutes / 60:.1f}h"


def detect_run_default_mem_mb(recs: list[Recommendation]) -> float | None:
    """The mem the run's cluster-wide default requested, inferred as the modal requested mem.

    The vast majority of rules carry no explicit ``resources:`` block and so request the
    cluster-wide default, which makes the most common requested value the default itself. This
    avoids hard-coding the default (and the SLURM 1000-vs-1024 GB ambiguity in how ``64G`` is
    recorded): a rule requesting the mode ran on the default and needs a new block before the
    default is lowered; a rule requesting anything else already declares its own.

    ``declared_mem_only`` rules are excluded here rather than at the call sites: their mem came from
    a snakefile ``resources:`` block, which is by definition not the default, and on a snapshot with
    no efficiency report *every* value comes from there -- so folding them in would elect one of
    those declarations as "the default". Filtering inside means the report headline and the
    ``ran_on_default`` marks can never disagree about which value the default is.
    """
    values = [round(r.requested_mem_mb) for r in recs if r.requested_mem_mb and not r.declared_mem_only]
    if not values:
        return None
    return float(Counter(values).most_common(1)[0][0])


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
    # Runtime fit, resolved independently of the memory fit above: rules almost never declare a
    # `runtime`, so the limit usually comes from the snakefiles or the cluster-wide default.
    rec_runtime_min: int = 0
    time_classification: str = "ok"  # over | ok | at-risk
    # True if the rule declares its own `runtime` in a snakefile; False if it runs on the cluster
    # default. Only a declared runtime can be trimmed rule-by-rule.
    declared_runtime: bool = False
    # True if `requested_mem_mb` was read from the snakefile rather than from what the scheduler was
    # actually asked for. Such a rule declares its own block by definition, so it never ran on the
    # default -- and its value must stay out of detect_run_default_mem_mb()'s mode.
    declared_mem_only: bool = False
    # True if the rule ran on the run's default mem (no explicit `resources:` block, so it needs a
    # new one before the default drops); False if it carried an explicit request; None if unknown
    # (no requested-side data). Set by analyze() from the run's modal requested mem.
    ran_on_default: bool | None = None
    # How many benchmark files this row folds together: 1 for an ordinary rule, one per wildcard
    # value for a wildcard rule, whose usage columns are then the worst case across them.
    instances: int = 1

    @property
    def mem_pct(self) -> float | None:
        if not self.requested_mem_mb:
            return None
        return 100.0 * self.actual_mem_mb / self.requested_mem_mb

    @property
    def wall_pct(self) -> float | None:
        """Wall time as a percentage of ``runtime_limit_min``, which is usually the cluster-wide
        default rather than anything the rule declared -- see ``declared_runtime``."""
        if not self.runtime_limit_min:
            return None
        return 100.0 * (self.wall_sec / 60.0) / self.runtime_limit_min


def analyze(
    run_dir: str | Path,
    *,
    safety: float = DEFAULT_SAFETY,
    floor_mb: int = DEFAULT_FLOOR_MB,
    new_default_mem_mb: int = DEFAULT_NEW_DEFAULT_MEM_MB,
    new_default_cpus: int = DEFAULT_NEW_DEFAULT_CPUS,
    snakefile_dir: str | Path | None = None,
    default_runtime_min: int = DEFAULT_RUNTIME_MIN,
) -> list[Recommendation]:
    """Build per-rule recommendations from the artifacts under ``run_dir``.

    ``run_dir`` is expected to contain ``benchmarks/``, ``logs/`` and (optionally)
    ``reports/slurm/``. Rules are keyed by the benchmark set (actual usage); the
    requested side comes from the efficiency report, falling back to the per-rule
    log's declared ``mem_mb`` / ``cpus_per_task``.

    ``snakefile_dir`` supplies each rule's statically-declared ``resources:``. It matters most for
    the runtime fit: the efficiency report has no time-limit column and a run usually retains logs
    for only a handful of rules, so without it nearly every rule falls back to
    ``default_runtime_min`` and a rule with an explicit ``runtime="24h"`` looks like a catastrophic
    overrun.
    """
    run_dir = Path(run_dir)
    benchmarks = read_benchmarks(run_dir / "benchmarks")
    try:
        efficiency = read_efficiency_report(run_dir / "reports" / "slurm")
    except FileNotFoundError:
        efficiency = {}
    logs = read_rule_logs(run_dir / "logs")
    declared = read_snakefile_resources(snakefile_dir) if snakefile_dir else {}
    rule_names = list(declared)

    # One row per *rule*, not per benchmark file: a wildcard rule's instances are folded into their
    # worst case, because a `resources:` block is declared once for the rule. See group_by_rule().
    grouped_efficiency = group_by_rule(efficiency, rule_names)

    recs: list[Recommendation] = []
    for rule, instances in group_by_rule(benchmarks, rule_names).items():
        bench = worst_case(rule, instances)
        eff_rows = grouped_efficiency.get(rule, [])
        log = logs.get(rule)
        decl = declared.get(rule)

        requested_mem = max((row.requested_mem_mb for row in eff_rows if row.requested_mem_mb), default=None) or (
            log.mem_mb if log else None
        )
        # A mem read from the snakefile is a *declared* block, not what the scheduler was asked for.
        # Keep the two apart: detect_run_default_mem_mb() infers the run's default as the modal
        # requested mem, and a declared value is by definition not the default -- folding them in
        # would let a reports-only snapshot (no efficiency report, so every value comes from here)
        # elect one of them as "the default" and mis-mark every rule sharing it as ran_on_default.
        declared_mem_only = False
        if not requested_mem and decl and decl.mem_mb:
            requested_mem, declared_mem_only = decl.mem_mb, True
        # Same three-step fallback as mem and runtime: what the scheduler was asked for, then the
        # job's log, then the snakefile. Without the last step a reports-only snapshot reports a
        # blank `req cpus` for every rule, including the ones that declare `cpus_per_task`.
        requested_cpus = (
            max((row.ncpus for row in eff_rows if row.ncpus), default=None)
            or (log.cpus if log else None)
            or (decl.cpus if decl else None)
        )
        # Prefer what the job actually ran with (the log), then the snakefile, then the profile
        # default -- a rule with no explicit block really does get the cluster-wide runtime.
        runtime_limit = (
            (log.runtime_min if log else None) or (decl.runtime_min if decl else None) or default_runtime_min
        )

        # The one unit conversion in this module: benchmark "MB" columns are mebibytes, everything
        # on the requested side is decimal MB. See the note beside MIB_TO_MB.
        actual_mem_mb = bench.max_rss_mb * MIB_TO_MB

        rec_mem = recommend_mem_mb(actual_mem_mb, safety, floor_mb)
        rec_cpus = recommend_cpus(bench.cores_used)
        rec_runtime = recommend_runtime_min(bench.seconds, safety)

        # Only a runtime someone actually wrote in a snakefile is trimmable. Almost every rule runs
        # for seconds against the cluster-wide default, so classifying those as over-provisioned
        # would bury the handful of real findings under three hundred rows nobody can act on --
        # whether the *default* is too generous is one decision, reported separately below.
        declared_runtime = bool(decl and decl.runtime_min)
        wall_min = bench.seconds / 60.0
        if wall_min > AT_RISK_FRACTION * runtime_limit:
            time_classification = "at-risk"
        elif declared_runtime and runtime_limit >= 2 * rec_runtime:
            time_classification = "over"
        else:
            time_classification = "ok"

        if not requested_mem:
            classification = "no-request-data"
        elif actual_mem_mb > AT_RISK_FRACTION * requested_mem:
            classification = "at-risk"
        elif requested_mem >= 2 * rec_mem:
            classification = "over"
        else:
            classification = "ok"

        needs_override = rec_mem > new_default_mem_mb or rec_cpus > new_default_cpus

        recs.append(
            Recommendation(
                rule=rule,
                instances=len(instances),
                actual_mem_mb=actual_mem_mb,
                requested_mem_mb=requested_mem,
                cores_used=bench.cores_used,
                requested_cpus=requested_cpus,
                wall_sec=bench.seconds,
                runtime_limit_min=runtime_limit,
                rec_mem_mb=rec_mem,
                rec_cpus=rec_cpus,
                classification=classification,
                needs_override=needs_override,
                rec_runtime_min=rec_runtime,
                time_classification=time_classification,
                declared_runtime=declared_runtime,
                declared_mem_only=declared_mem_only,
            )
        )
    # Mark which rules ran on the run's default (no explicit block) vs declared their own, so the
    # override list separates rules that need a *new* block from those that already carry one.
    run_default_mb = detect_run_default_mem_mb(recs)
    for rec in recs:
        if rec.requested_mem_mb is None:
            rec.ran_on_default = None
        elif rec.declared_mem_only:
            rec.ran_on_default = False
        elif run_default_mb is not None and abs(rec.requested_mem_mb - run_default_mb) <= 0.02 * run_default_mb:
            rec.ran_on_default = True
        else:
            rec.ran_on_default = False

    recs.sort(key=lambda r: r.actual_mem_mb, reverse=True)
    return recs


def _label(rec: Recommendation) -> str:
    """The rule's name, marked with how many wildcard instances its numbers cover."""
    return rec.rule if rec.instances == 1 else f"{rec.rule} (×{rec.instances})"


def build_markdown(
    recs: list[Recommendation],
    new_default_mem_mb: int,
    new_default_cpus: int,
    default_runtime_min: int = DEFAULT_RUNTIME_MIN,
) -> str:
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
        / _MB_PER_GB
    )

    lines: list[str] = []
    lines.append("# SLURM resource analysis")
    lines.append("")
    lines.append(
        f"Rules with benchmarks: {total}  |  over-provisioned: {over}  |  at-risk: {at_risk}  |  no request data: {no_data}"
    )
    lines.append(f"Wasted reservation (requested minus used): {wasted_gb:.0f} GB across rules with a known request.")
    lines.append("")
    run_default_mb = detect_run_default_mem_mb(recs)
    actionable = [r for r in overrides if r.ran_on_default is True]
    unknown = [r for r in overrides if r.ran_on_default is None]
    lines.append(
        f"Proposed new default: mem={new_default_mem_mb // _MB_PER_GB}G, cpus={new_default_cpus}. "
        f"Detected run default: mem={_fmt_gb(run_default_mb)}."
    )
    lines.append(
        f"{len(actionable)} of {len(overrides)} exceeding rule(s) ran on the default and need a *new* "
        f"block; {len(overrides) - len(actionable) - len(unknown)} already carry one"
        + (f"; {len(unknown)} have no request data (check manually)." if unknown else ".")
    )
    lines.append("")
    lines.append("## Rules exceeding the proposed default")
    lines.append("")
    lines.append(
        "`ran on default` = **yes** → needs a new `resources:` block; **no** → already has one; **?** → unknown."
    )
    lines.append("")
    if overrides:
        # Actionable (ran on default) first, then unknown, then rules that already carry a block.
        order = {True: 0, None: 1, False: 2}
        lines.append("rule | actual RSS | rec mem | rec cpus | ran on default")
        lines.append("---- | ---------- | ------- | -------- | --------------")
        for r in sorted(overrides, key=lambda r: (order[r.ran_on_default], -r.actual_mem_mb)):
            flag = {True: "yes", False: "no", None: "?"}[r.ran_on_default]
            lines.append(f"{_label(r)} | {_fmt_gb(r.actual_mem_mb)} | {_fmt_gb(r.rec_mem_mb)} | {r.rec_cpus} | {flag}")
    else:
        lines.append("(none — the proposed default already covers every rule)")
    lines.append("")
    lines.append("## Runtime fit")
    lines.append("")
    lines.append(
        "Wall time against the declared `runtime` limit (from the rule's log, else its snakefile, "
        "else the cluster default). **at-risk** rules are close to being killed; **over** rules have "
        "a limit at least twice what they need, which makes Snakemake's remaining-time estimate "
        "useless and hides a job that has become pathologically slow."
    )
    lines.append("")
    time_at_risk = [r for r in recs if r.time_classification == "at-risk"]
    time_over = [r for r in recs if r.time_classification == "over"]
    lines.append(
        f"Rules at risk of timing out: {len(time_at_risk)}  |  declaring more time than they need: {len(time_over)}"
    )
    # Whether the cluster-wide default is too generous is one decision, not N rows in the table.
    on_default = [r for r in recs if not r.declared_runtime]
    if on_default:
        slowest = max(on_default, key=lambda r: r.wall_sec)
        # Divide by AT_RISK_FRACTION before bucketing: "not at risk" means the wall time is under
        # that fraction of the limit, so a bucket merely >= the wall time lands the slowest rule at
        # ~97% of the new default -- at-risk on arrival, the opposite of what this sentence promises.
        safe_default = recommend_runtime_min(slowest.wall_sec, 1 / AT_RISK_FRACTION)
        # Which direction that is depends on the current default, which is why it has to be passed
        # in: the same computation reads as a trim on one run and a *raise* on another, and printing
        # "could drop to 3.0h" against a 2.0h default is an instruction to do the opposite.
        if safe_default < default_runtime_min:
            verdict = f"so the default could drop from {_fmt_min(default_runtime_min)} to {_fmt_min(safe_default)}"
        elif safe_default > default_runtime_min:
            verdict = (
                f"so the {_fmt_min(default_runtime_min)} default is too tight and should rise to "
                f"{_fmt_min(safe_default)}"
            )
        else:
            verdict = f"so the current {_fmt_min(default_runtime_min)} default is already the tightest safe value"
        lines.append(
            f"{len(on_default)} rules ran on the default runtime; the slowest was `{slowest.rule}` at "
            f"{_fmt_min(slowest.wall_sec / 60)}, {verdict} — at that value none of them is at risk."
        )
    lines.append("")
    if time_at_risk or time_over:
        lines.append("rule | wall | limit | wall% | rec runtime | class")
        lines.append("---- | ---- | ----- | ----- | ----------- | -----")
        for r in sorted(time_at_risk + time_over, key=lambda r: -(r.wall_pct or 0)):
            pct = f"{r.wall_pct:.0f}%" if r.wall_pct is not None else "-"
            lines.append(
                f"{_label(r)} | {_fmt_min(r.wall_sec / 60)} | {_fmt_min(r.runtime_limit_min)} | {pct} | "
                f"{_fmt_min(r.rec_runtime_min)} | {r.time_classification}"
            )
    else:
        lines.append("(none — every rule fits its runtime limit without wasting it)")
    lines.append("")
    lines.append("## All rules (by actual peak RSS)")
    lines.append("")
    lines.append("rule | actual RSS | req mem | mem% | cores | req cpus | wall | rec mem | rec cpus | class")
    lines.append("---- | ---------- | ------- | ---- | ----- | -------- | ---- | ------- | -------- | -----")
    for r in recs:
        pct = f"{r.mem_pct:.0f}%" if r.mem_pct is not None else "-"
        lines.append(
            f"{_label(r)} | {_fmt_gb(r.actual_mem_mb)} | {_fmt_gb(r.requested_mem_mb)} | {pct} | "
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
                # Benchmark files folded into this row: >1 for a wildcard rule, whose usage columns
                # are then the worst case across its instances.
                "instances",
                "actual_rss_mb",
                "requested_mem_mb",
                "mem_pct",
                "cores_used",
                "requested_cpus",
                "wall_sec",
                # runtime_limit_min is always populated: a rule declaring none inherits the cluster
                # default, so declared_runtime is what says whether it can be trimmed rule-by-rule.
                "runtime_limit_min",
                "declared_runtime",
                "wall_pct",
                "rec_mem_mb",
                "rec_cpus",
                "rec_runtime_min",
                "classification",
                "time_classification",
                "needs_override",
                "ran_on_default",
            ]
        )
        for r in recs:
            writer.writerow(
                [
                    r.rule,
                    r.instances,
                    f"{r.actual_mem_mb:.1f}",
                    f"{r.requested_mem_mb:.0f}" if r.requested_mem_mb else "",
                    f"{r.mem_pct:.1f}" if r.mem_pct is not None else "",
                    f"{r.cores_used:.2f}",
                    r.requested_cpus if r.requested_cpus else "",
                    f"{r.wall_sec:.0f}",
                    r.runtime_limit_min if r.runtime_limit_min else "",
                    int(r.declared_runtime),
                    f"{r.wall_pct:.1f}" if r.wall_pct is not None else "",
                    r.rec_mem_mb,
                    r.rec_cpus,
                    r.rec_runtime_min,
                    r.classification,
                    r.time_classification,
                    int(r.needs_override),
                    "" if r.ran_on_default is None else int(r.ran_on_default),
                ]
            )


def _add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("run_dir", help="Run-analysis directory with benchmarks/, logs/, reports/slurm/.")
    parser.add_argument(
        "--safety", type=float, default=DEFAULT_SAFETY, help=f"Safety factor on peak RSS (default: {DEFAULT_SAFETY})."
    )
    parser.add_argument(
        "--floor-gb",
        type=int,
        default=DEFAULT_FLOOR_MB // _MB_PER_GB,
        help="Minimum recommended mem in GB (default: 8).",
    )
    parser.add_argument(
        "--new-default-mem-gb",
        type=int,
        default=DEFAULT_NEW_DEFAULT_MEM_MB // _MB_PER_GB,
        help="Proposed new cluster default mem in GB to test rules against (default: 16).",
    )
    parser.add_argument(
        "--new-default-cpus",
        type=int,
        default=DEFAULT_NEW_DEFAULT_CPUS,
        help="Proposed new cluster default cpus to test rules against (default: 1).",
    )
    parser.add_argument(
        "--snakefile-dir",
        default=str(get_repo_root() / "src" / "snakefiles"),
        help="Directory of .snakefile files supplying each rule's declared resources (default: this "
        "repo's src/snakefiles). Mainly needed for the runtime fit: a run's logs usually cover only "
        "a handful of rules and the efficiency report has no time-limit column.",
    )
    parser.add_argument(
        "--default-runtime-min",
        type=int,
        default=DEFAULT_RUNTIME_MIN,
        help=f"Cluster-wide default runtime in minutes for rules that declare none, matching "
        f"slurm/config.yaml (default: {DEFAULT_RUNTIME_MIN}).",
    )
    parser.add_argument("--csv", metavar="PATH", help="Also write the full per-rule table to this CSV.")


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "resources",
        help="Recommend right-sized mem/cpus from benchmark + efficiency data.",
        description="Compare actual resource usage against requested resources and recommend right-sized limits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  babel-slurm-resources data/babel-1.17
  babel-slurm-resources data/babel-1.17 --csv /tmp/resources.csv
  babel-slurm-resources data/babel-1.17 --new-default-mem-gb 16 --safety 2.0
""",
    )
    _add_args(parser)
    parser.set_defaults(func=run)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="babel-slurm-resources",
        description="Compare actual resource usage against requested resources and recommend right-sized limits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  babel-slurm-resources data/babel-1.17
  babel-slurm-resources data/babel-1.17 --csv /tmp/resources.csv
  babel-slurm-resources data/babel-1.17 --new-default-mem-gb 16 --safety 2.0
""",
    )
    _add_args(parser)
    run(parser.parse_args())


def run(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"error: not a directory: {run_dir}", file=sys.stderr)
        sys.exit(1)

    new_default_mem_mb = args.new_default_mem_gb * _MB_PER_GB
    recs = analyze(
        run_dir,
        safety=args.safety,
        floor_mb=args.floor_gb * _MB_PER_GB,
        new_default_mem_mb=new_default_mem_mb,
        new_default_cpus=args.new_default_cpus,
        snakefile_dir=args.snakefile_dir,
        default_runtime_min=args.default_runtime_min,
    )
    if args.csv:
        write_csv(recs, args.csv)
        print(f"Wrote {len(recs)} rows to {args.csv}", file=sys.stderr)
    print(build_markdown(recs, new_default_mem_mb, args.new_default_cpus, args.default_runtime_min))
