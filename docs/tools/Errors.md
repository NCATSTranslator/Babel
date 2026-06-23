# `tools.slurm errors` — aggregate failing-rule logs

When a Babel run on SLURM stalls or fails, the failure is usually spread across the main Snakemake
control-node log and one per-rule log per failing job. This subcommand gathers all of that into a
single report so you can paste it somewhere (a code review tool, an issue, a chat) and decide which
rules to re-run.

```bash
uv run babel-slurm-errors <version> [--logs-dir DIR] [--markdown] [--traceback-only] [--lines N]
```

`<version>` is the tag in the `sbatch-<version>.err` control-node log (e.g. `1.17-try-2`); omit it
to auto-detect the newest `sbatch-*.err` in the logs directory. `--logs-dir` defaults to
`babel_outputs/logs`.

## What it reads and writes

It reads the main `sbatch-<version>.err` log, follows each `Error in rule X` to that rule's
per-rule `*.log`, and produces two outputs on two streams:

- **stdout — the error report.** One section per distinct failure. Rules whose logs are
  byte-for-byte identical are grouped together, so a recurring transient failure (an HTTP 503 from a
  data source hitting many rules) shows up once rather than dozens of times. With `--markdown` each
  section is a fenced code block (handy for pasting into a review tool or chat); otherwise sections
  are separated by `===` banners. `slurm/run-babel-on-slurm.sh` redirects this stream to
  `babel_outputs/logs/error-report-<version>.md`.
- **stderr — the job summary.** A roll-up of every job attempt parsed from the control-node log,
  split into three buckets: still-running rules (with elapsed time versus the declared timeout and
  the time remaining), completed rules, and truly-failed jobs (those with no active retry). A rule
  that failed and was retried is listed under its still-running attempt with the prior failure as an
  indented sub-line. Because this is on stderr, it stays visible in the terminal (or the sbatch
  `.err` log) even when stdout is redirected to a file.

## Design notes

A few behaviors exist because of the specific failure shapes this pipeline produces:

- **The whole rule log is shown, not a tail or a Python traceback.** Snakemake's `RuleException` and
  `OutOfMemoryException` blocks are neither Python `Traceback`s nor reliably near the end of the
  log, so a tail/traceback heuristic would routinely hide the real error. A pathologically long log
  is capped to a head + tail with an elision marker (`--lines N`, default 1000) so the report stays
  usable.
- **DuckDB progress-bar spam is collapsed.** DuckDB redraws an in-place progress bar with a carriage
  return, and Snakemake captures every redraw, so one logical "line" can be hundreds of KB of
  repeated bar frames. Runs of those are collapsed to a single marker.
- **DuckDB memory diagnostics are surfaced.** The connect-time memory-headroom line sits near the
  top of a log and the multi-threaded out-of-memory path can abort without a traceback, so any
  DuckDB memory-diagnostic lines are echoed in a labelled trailer at the end of the section where
  they are easy to find.

`--traceback-only` restricts the report to rules whose logs contain a Python traceback, which is
occasionally useful when you only care about code bugs rather than transient infrastructure errors.
