# Performance tracking and SLURM resource tuning

Babel runs on the RENCI Hatteras cluster as a Snakemake-on-SLURM pipeline. Each rule reserves
memory, CPUs, and wall time; over-reserving throttles parallelism (a 191 GB batch node fits only
~3 jobs that each ask for 64 GB), while under-reserving causes OOM kills and timeouts. This page
describes how we measure what rules actually use and turn that into right-sized `resources:`.

## The data a run produces

A Snakemake-on-SLURM run leaves three kinds of artifact under `babel_outputs/`. To analyze a run
(including a partial one), copy these into a run directory such as `data/babel-1.17/`:

- `benchmarks/<rule>.tsv` — Snakemake `benchmark:` output, written from *inside* each job. Columns
  include `s` (wall seconds), `max_rss` (peak RAM, MB), `mean_load` (%CPU, 100 = one core), and
  `cpu_time`. This is the **authoritative source for actual memory and CPU usage**.
- `reports/slurm/slurm_efficiency_reports/` — a *directory* of `efficiency_report_<uuid>.csv`
  from the SLURM executor, with `RequestedMem_MB`, `NCPUS`, and `Elapsed_sec` per job. The executor
  appends a **fresh shard on every Snakemake (re)start**, and each shard covers only that
  invocation's jobs — so a run that restarted several times leaves many shards, and the final one
  usually holds just a handful of rules. The analyzer therefore reads and merges *all* shards
  (worst-case per rule); reading only the newest (as an early version did) drops the requested-side
  data for almost every rule.
- `logs/rule_<name>/<jobid>.log` — per-rule control-node logs: the declared `resources:` line,
  start/end timestamps, and any traceback.

### Why the benchmark TSVs, not the efficiency report

The SLURM efficiency report is the natural place to look for memory and CPU efficiency, but on
Hatteras its `MaxRSS` and `TotalCPU` columns come back **empty** — the cluster's
`jobacct_gather`/cgroup accounting isn't capturing per-step usage. Every `CPU Efficiency (%)` and
`Memory Usage (%)` value is therefore `0`. We use the efficiency report only for the *requested*
side (`RequestedMem_MB`, `NCPUS`) and rely on the Snakemake `benchmark:` TSVs for actual usage.
Issue (c) in [Open issues](#open-issues) tracks fixing the accounting so the report can serve as a
cross-check.

## The tooling: `tools/slurm`

`tools/slurm` is a small package with two subcommands sharing one parsing layer
(`tools/slurm/parse.py`):

```bash
# Recommend right-sized mem/cpus/runtime from a run directory:
uv run python -m tools.slurm resources data/babel-1.17
uv run python -m tools.slurm resources data/babel-1.17 --csv /tmp/resources.csv

# Aggregate failing-rule logs into one copy-pasteable report (to decide what to re-run):
uv run python -m tools.slurm errors 1.17-try-2 --markdown
```

The `errors` subcommand is the successor to the old `tools/babel-errors.py` script (removed): its
full failing-log extraction, DuckDB memory-diagnostic surfacing, and completed/failed/running job
summary now live in `tools.slurm` alongside the resource analyzer, sharing `tools/slurm/parse.py`.

### What the resource analyzer reports

For each rule with a benchmark it joins actual usage against the requested resources and prints:

- a per-rule table (actual RSS, requested mem, `mem%`, cores used, wall time) sorted by peak RSS;
- a recommended `mem`/`cpus` per rule — the observed peak times a safety factor (default 1.5),
  rounded up to a bucket (8/16/24/32/48/64 GB…), floored at 8 GB. A safety factor is used because
  an OOM is a hard kill that wastes the whole job, and one benchmark captures only a single run's
  peak (source data grows between runs);
- a **"rules needing an explicit override before lowering the default"** list — rules whose
  recommendation exceeds the proposed new cluster default (`--new-default-mem-gb`, default 16).
  This is the safety gate: lowering the default without giving these rules an explicit `resources:`
  block would silently starve them.

A rule is classified `over` (requested ≥ 2× the recommendation), `at-risk` (actual > 80% of
requested), `ok`, or `no-request-data` (benchmark only, e.g. a rule the efficiency report missed).

## What the babel-1.17 partial run showed

Running the analyzer on a partial `babel-1.17` run (data collection plus the anatomy / disease /
taxon / process / cell compendia; the heavy chemical / gene / protein / conflation phase had not
run yet) found:

- **Memory was massively over-provisioned.** Of 122 rules on the old 64 GB default, 119 peaked
  below 8 GB and 90 below 1 GB. Only `get_uniprotkb_labels` exceeded 32 GB (≈41 GB). Across all
  rules with a known request, ≈7.7 TB of reservation went unused.
- **CPU was over-provisioned.** 226 of 233 rules used ~1 core; only a handful of short DuckDB
  export rules used 2–3 cores. (Earlier readings that suggested 3+ cores came from *failed*
  8-second runs; the benchmark `mean_load` is the trustworthy signal.)
- **Runtime was already handled.** The only long jobs are downloads, which already carry explicit
  `runtime="6h"/"12h"/"24h"` overrides; nothing else approached the 120-minute default.

### Changes made as a result

- Lowered the cluster default in `slurm/config.yaml` from `mem: 64G` / `cpus_per_task: 4` to
  `mem: 16G` / `cpus_per_task: 1`.
- Added explicit `mem` overrides to the only two rules whose peak exceeds 16 GB:
  `get_uniprotkb_labels` (`mem="64G"`, peaks ≈41 GB) and `taxon_compendia` (`mem="32G"`, peaks
  ≈14 GB).
- Left the already-explicit heavy rules (chemical/gene/protein compendia, DuckDB cross-joins,
  conflation, PubMed) untouched — the partial run never exercised them, so we have no new evidence
  about them. See the hotspot table in [`slurm/README.md`](../slurm/README.md).

## Workflow for the next run

1. Run the pipeline; let it write `benchmarks/`, `logs/`, and `reports/slurm/`.
2. If the run stalls, `uv run python -m tools.slurm errors <version> --markdown` to see which rules
   failed (often transient HTTP errors from data sources) and re-run them.
3. After a complete run, `uv run python -m tools.slurm resources <run-dir>` and apply the
   "needs an explicit override" list: add a `resources:` block to those rules, and adjust the
   default in `slurm/config.yaml` if the whole distribution has shifted.
4. Re-run the analyzer to confirm the override list is empty (every rule now fits its allocation).

## Open issues

These are tracked as GitHub issues:

- (a) Build the `tools/slurm` analyzer and fold `babel-errors.py` into it. *(done — this change.)*
- (b) Right-size the SLURM default mem/cpus and add per-rule overrides. *(done — this change.)*
- (c) Fix Hatteras `jobacct_gather`/cgroup accounting so the efficiency report's `MaxRSS`/
  `TotalCPU` populate and can cross-check the benchmark TSVs
  ([#832](https://github.com/NCATSTranslator/Babel/issues/832)).
- (d) Re-run the transient download/id failures blocking the in-progress run (handled manually
  via `tools.slurm errors`, no issue needed).
