# CLAUDE.md — src/tools/slurm/

`babel-slurm-errors` and `babel-slurm-resources` analyze a (possibly partial) Snakemake-on-SLURM
run. Full reference: [`docs/tools/Errors.md`](../../../docs/tools/Errors.md) and
[`docs/tools/Resources.md`](../../../docs/tools/Resources.md).

Both subcommands share `parse.py`. The one gotcha worth knowing before touching either: on
Hatteras, `sacct`'s `MaxRSS`/`TotalCPU` come back empty, so the Snakemake `benchmark:` TSVs are
the authoritative source for actual memory/CPU usage — never trust the SLURM efficiency report's
usage columns. `reports/slurm/slurm_efficiency_reports/` is a *directory* that accumulates one
`efficiency_report_<uuid>.csv` shard per Snakemake restart (each covering only that invocation's
jobs); `parse.py` merges them all, so copy the whole directory when archiving a run.

This tool is a documented exception to the "thin CLI frontend" rule in `src/tools/CLAUDE.md`:
`parse.py` models Snakemake `benchmark:` TSVs and SLURM `.err` logs, not Babel data, so it has
nothing to hoist into `src/` and no pipeline rule will ever import it.
