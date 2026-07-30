# `babel-slurm-resources` — right-size SLURM resources

Babel runs on the RENCI Hatteras cluster as a Snakemake-on-SLURM pipeline. Each rule reserves
memory, CPUs, and wall time. Over-reserving throttles parallelism (a 191 GB batch node fits only
~3 jobs that each ask for 64 GB); under-reserving causes OOM kills and timeouts. This subcommand
measures what rules actually used on a past run and turns that into recommended, right-sized
`resources:`.

```bash
uv run babel-slurm-resources <run-dir> [--csv PATH] [--safety F] [--floor-gb N] \
    [--new-default-mem-gb N] [--new-default-cpus N] \
    [--snakefile-dir DIR] [--default-runtime-min N]
```

`<run-dir>` is a directory containing `benchmarks/`, `logs/`, and (optionally) `reports/slurm/` —
either `babel_outputs/` itself or a copy archived for analysis, such as `data/babel-1.17/`.

Captured examples of the full report — the analysis behind the current `slurm/config.yaml` defaults
and per-rule overrides — are committed at
[`examples/babel-slurm-resources-2026jul22.md`](examples/babel-slurm-resources-2026jul22.md) (the
most recent pass, and the first with the runtime analysis) and
[`examples/babel-slurm-resources-babel-1.17.md`](examples/babel-slurm-resources-babel-1.17.md).

## The data a run produces

A Snakemake-on-SLURM run leaves three kinds of artifact under `babel_outputs/`:

- `benchmarks/<rule>.tsv` — Snakemake `benchmark:` output, written from *inside* each job. The
  columns include `s` (wall seconds), `max_rss` (peak RAM), `mean_load` (%CPU, where 100 = one
  fully-used core), and `cpu_time`. This is the **authoritative source for actual memory and CPU
  usage**. When a rule has several benchmark rows (from retries or `repeat()`), the reader keeps the
  per-column worst case. Snakemake labels the memory columns "MB" but computes them as bytes
  `/ 1024 / 1024`, so they are really **mebibytes** — see "Units" below.
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

### Units

Everything the tool prints is **decimal GB/MB**, so a recommended `mem` is literally the string to
paste into a `resources:` block: `mem="8G"` reaches SLURM as 8000 MB, and the efficiency report's
`RequestedMem_MB` is decimal too.

The benchmark TSVs are the exception — their "MB" columns are mebibytes — so they are converted on
the way in (`MIB_TO_MB` in `src/tools/slurm/resources.py`). Comparing the two unconverted is a ~4.9%
error, and always in the unsafe direction: a rule looks further from its limit than it is. This is
the same trap as `duckdb_memory_limit_mb()` in `src/snakefiles/util.py`, where Snakemake's
`resources.mem` re-exposes `mem="512G"` as the decimal `"512 GB"` and `mem_mb` as `512000`.

Practical consequence when reading a rule's comment: a benchmark peak of "132G" needs `mem="142G"`
to be at 100% of its limit, not `mem="132G"`.

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

### Runtime fit

A **Runtime fit** section does the same for wall time. The limit comes from the rule's log, then its
snakefile's declared `runtime`, then the cluster default (`--default-runtime-min`, 120 to match
`slurm/config.yaml`). The snakefile is what makes this usable: the efficiency report has no
time-limit column and a run usually retains logs for only a handful of rules, so without
`--snakefile-dir` (defaulting to this repo's `src/snakefiles`) a rule declaring `runtime="24h"`
would look like a catastrophic overrun against the 2-hour default.

Time matters in *both* directions, which is why the recommendation isn't simply generous. Too little
and the job is killed outright; too much and Snakemake's remaining-time estimate becomes useless and
a job that has become pathologically slow no longer stands out. Rules are `at-risk` above 80% of
their limit and `over` when the limit is at least twice what they need.

**`over` only applies to a rule that declares its own `runtime`.** Nearly every rule runs for
seconds against the cluster-wide default, so classifying those would bury the real findings under
hundreds of rows nobody can act on. Whether the *default itself* is too generous is one decision,
reported as a single line naming the slowest rule still on it.

Two traps the 2026jul22 pass hit, both worth checking before trimming anything:

- **A rule whose input shrank is not over-provisioned.** UniProtKB dropped ~41% upstream in
  2026jul22, so `protein_compendia` ran 5.5h/246G there against 7.6h/337G on babel-1.17. Sizing from
  the smaller run alone would have set limits that OOM the next normal release.
- **Network-bound rules vary by an order of magnitude.** `get_ensembl` took 3 minutes on babel-1.17
  and 1.9h on 2026jul22. Their generous runtimes are deliberate; leave them.

Always compare against a second run's benchmarks before trimming — the numbers for a compute-bound
rule are usually stable to within a percent or two (`untyped_chemical_compendia` peaked at 132.0G
and 132.1G across the two runs), so a rule that *isn't* stable is telling you something.

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
4. Work the **Runtime fit** section the same way: give every `at-risk` rule an explicit `runtime`
   (or raise the one it has), and trim the `over` rules that declare their own. Check each against a
   second run's benchmarks first — see the two traps above.
5. Re-run the analyzer to confirm the override list is empty (modulo rules that already carry a
   block) and that no rule is left `at-risk` on either axis — every rule now fits its allocation.
6. On later runs, re-check the *existing* override rules against the "req mem" vs "actual RSS"
   columns and trim any that have grown over-provisioned. There is no CI guard for this (it would
   require committing benchmark data); it's a periodic manual pass on the files a run leaves behind.
   A release is the natural cadence — see the `release-notes` skill.
