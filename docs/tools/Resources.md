# `babel-slurm-resources` — right-size SLURM resources

Babel runs on the RENCI Hatteras cluster as a Snakemake-on-SLURM pipeline. Each rule reserves
memory, CPUs, and wall time. Over-reserving throttles parallelism (a 191 GB batch node fits only
~3 jobs that each ask for 64 GB); under-reserving causes OOM kills and timeouts. This subcommand
measures what rules actually used on a past run and turns that into recommended, right-sized
`resources:`.

```bash
uv run babel-slurm-resources <run-dir> [--csv PATH] [--safety F] [--floor-gb N] [--new-default-mem-gb N] [--new-default-cpus N]
```

`<run-dir>` is a directory containing `benchmarks/`, `logs/`, and (optionally) `reports/slurm/` —
either `babel_outputs/` itself or a copy archived for analysis, such as `data/babel-1.17/`.

A captured example of the full report — the analysis behind the current `slurm/config.yaml`
defaults and per-rule overrides — is committed at
[`examples/babel-slurm-resources-babel-1.17.md`](examples/babel-slurm-resources-babel-1.17.md).

## The data a run produces

A Snakemake-on-SLURM run leaves three kinds of artifact under `babel_outputs/`:

- `benchmarks/<rule>.tsv` — Snakemake `benchmark:` output, written from *inside* each job. The
  columns include `s` (wall seconds), `max_rss` (peak RAM, MB), `mean_load` (%CPU, where 100 = one
  fully-used core), and `cpu_time`. This is the **authoritative source for actual memory and CPU
  usage**. When a rule has several benchmark rows (from retries or `repeat()`), the reader keeps the
  per-column worst case.
- `reports/slurm/` — the SLURM executor's efficiency report. The executor appends a **fresh
  `efficiency_report_<uuid>.csv` shard on every Snakemake (re)start**, and each shard covers only
  that invocation's jobs, so a run that restarted several times leaves many shards and the final one
  usually holds just a handful of rules. The reader therefore merges *all* shards (worst case per
  rule); reading only the newest would drop the requested-side data for almost every rule. When
  archiving a run, copy the whole directory, not just the newest file.
- `logs/rule_<name>/<jobid>.log` — per-rule control-node logs: the declared `resources:` line and
  start/end timestamps, used as a fallback for the requested side and for the runtime limit.

### Why the benchmark TSVs, not the efficiency report

The efficiency report is the natural place to look for memory and CPU usage, but on Hatteras its
`MaxRSS` and `TotalCPU` columns come back **empty** — the cluster's `jobacct_gather`/cgroup
accounting isn't capturing per-step usage, so every `CPU Efficiency (%)` and `Memory Usage (%)` is
`0`. The tool therefore uses the efficiency report only for the *requested* side
(`RequestedMem_MB`, `NCPUS`, elapsed wall time) and relies on the `benchmark:` TSVs for actual
usage. Because the recommendations come from the benchmarks, the override list (below) is reliable
even when the requested side is sparse.

## What it reports

For each rule with a benchmark, it joins actual usage against the requested resources and prints:

- a per-rule listing sorted by peak RSS — actual RSS, requested mem, percent of the request used,
  cores used, wall time, and the recommended `mem`/`cpus`;
- a **recommended `mem`** — the observed peak times a safety factor (`--safety`, default 1.5),
  rounded up to a bucket (8/16/24/32/48/64 GB…), floored at `--floor-gb` (default 8). A safety
  factor is used because an OOM is a hard kill that wastes the whole job and one benchmark captures
  only a single run's peak (source data grows between runs);
- a **"rules needing an explicit override before lowering the default"** list — rules whose
  recommendation exceeds the proposed new cluster default (`--new-default-mem-gb`, default 16, and
  `--new-default-cpus`, default 1). This is the safety gate: lowering the cluster-wide default
  without giving these rules an explicit `resources:` block would silently starve them.

  **This list is a superset of the rules you must act on**, and a `ran on default` column splits it:
  **yes** means the rule requested the run's default mem (no explicit `resources:` block) and needs
  a *new* one before the default drops — the actionable subset; **no** means it already carries a
  block (e.g. `protein_compendia` at 512G) and is safe; **?** means there was no requested-side data
  for it (usually a DuckDB rule the efficiency report missed — check that one by hand). The default
  the run used is auto-detected as the modal requested mem and printed in the header, so there's no
  need to know or pass it.

Each rule is classified `over` (requested ≥ 2× the recommendation), `at-risk` (actual > 80% of the
request), `ok`, or `no-request-data` (a benchmark with no matching requested-side row). Pass `--csv`
to also write the full per-rule table for further analysis.

## Workflow

1. Run the pipeline; let it write `benchmarks/`, `logs/`, and `reports/slurm/`.
2. If the run stalls, use [`babel-slurm-errors`](Errors.md) to find which rules failed (often
   transient HTTP errors from data sources) and re-run them.
3. After a complete run, run `babel-slurm-resources <run-dir>` and, for each rule in the override
   list marked `ran on default = yes`, add a `resources:` block. Bias the numbers
   **down**: pick the smallest bucket comfortably above the observed peak (~10-15% headroom is fine)
   rather than the padded `--safety 1.5` recommendation. An OOM is cheap — we track per-rule peak
   RSS, so it's easy to bump the limit and re-run — whereas padding every rule slowly ratchets the
   whole cluster's reservation upward, which is exactly the over-provisioning we lowered the default
   to escape. The known heavy rules and the current defaults are documented in
   [`slurm/README.md`](../../slurm/README.md).
4. Re-run the analyzer to confirm the override list is empty (modulo rules that already carry a
   block) — every rule now fits its allocation.
5. On later runs, re-check the *existing* override rules against the "req mem" vs "actual RSS"
   columns and trim any that have grown over-provisioned. There is no CI guard for this (it would
   require committing benchmark data); it's a periodic manual pass on the files a run leaves behind.
