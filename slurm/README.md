# Running Babel on SLURM

This directory contains the Snakemake profile for running Babel on SLURM clusters (tested on the
RENCI Hatteras cluster).

## Quick Start

Snakemake
[recommends](https://snakemake.github.io/snakemake-plugin-catalog/plugins/executor/slurm.html#should-i-run-snakemake-on-the-login-node-of-my-cluster)
running the primary Snakemake process on the login node of your Slurm cluster. I've found that
running it in a low-memory low-CPU node (by running `sbatch run-babel-on-slurm.sh` to run
[run-babel-on-slurm.sh](./run-babel-on-slurm.sh)) works fine, and ensures that you don't get
complaints from your cluster manager about long-running login node processes.

```bash
# Activate the environment
uv sync

# Run the full pipeline on SLURM (up to 50 parallel jobs)
uv run snakemake --profile slurm

# Run a single semantic type
uv run snakemake --profile slurm anatomy
uv run snakemake --profile slurm chemical
```

## Profile Overview (`slurm/config.yaml`)

| Setting | Value | Notes |
|---------|-------|-------|
| `executor` | `slurm` | Uses Snakemake's built-in SLURM executor |
| `jobs` | 50 | Max parallel SLURM jobs |
| `default-resources.mem` | 64G | Per-job default RAM |
| `default-resources.cpus_per_task` | 4 | Per-job default CPUs |
| `default-resources.runtime` | 120 min | Per-job default wall time |
| `python.executable` | `/usr/bin/time -v python` | Captures memory/time to job stderr |
| `slurm-efficiency-report` | True | Writes per-job efficiency CSV |

Download-only rules (e.g. `get_EFO`, `get_mesh`, `get_rhea`, `get_pubchem`, `download_umls`)
override the defaults with `mem="8G", cpus_per_task=1` since they are I/O-bound. Large downloads
(UniProtKB idmapping/trembl, UMLS) also set `runtime="6h"`.

## Benchmark Data

Every non-trivial rule writes a benchmark TSV file to:

```text
babel_outputs/benchmarks/<rule_name>.tsv
```

For wildcard rules (e.g. one job per compendium), files are named:

```text
babel_outputs/benchmarks/export_compendia_to_duckdb_<filename>.tsv
babel_outputs/benchmarks/generate_kgx_<filename>.tsv
babel_outputs/benchmarks/generate_sapbert_training_data_<filename>.tsv
babel_outputs/benchmarks/generate_content_report_for_compendium_<compendium_basename>.tsv
babel_outputs/benchmarks/export_synonyms_to_duckdb_<filename>.tsv
babel_outputs/benchmarks/uncompress_synonym_file_<synonym_file>.tsv
```

### Benchmark TSV Fields

| Column | Description |
|--------|-------------|
| `s` | Wall-clock time in seconds |
| `h:m:s` | Wall-clock time formatted as hours:minutes:seconds |
| `max_rss` | Maximum resident set size (MB) — peak RAM usage |
| `max_vms` | Maximum virtual memory size (MB) |
| `max_uss` | Maximum unique set size (MB) |
| `max_pss` | Maximum proportional set size (MB) |
| `io_in` | MB read from disk |
| `io_out` | MB written to disk |
| `mean_load` | Average CPU load (100 = 1 full core) |
| `cpu_time` | Total CPU time in seconds |

`max_rss` is the most useful column for right-sizing SLURM memory allocations. Add ~20–30%
headroom over `max_rss` when setting `mem:` for a rule.

## SLURM Efficiency CSV

In addition to per-rule benchmarks, the SLURM executor writes a cumulative CSV at:

```text
babel_outputs/reports/slurm/slurm_efficiency_report.csv
```

This captures SLURM-level efficiency metrics (CPU efficiency, memory efficiency) per job,
complementing the Snakemake benchmark TSVs. The two sources measure slightly different things:

- **Benchmark TSVs** — measured by Snakemake inside the job; independent of SLURM accounting
- **Efficiency CSV** — reported by SLURM's `sacct`; includes job-scheduling overhead

## Known Resource Hotspots

These rules have hard-coded `resources:` overrides and should not be reduced without new benchmarks:

| Rule | File | `mem` | `runtime` | Notes |
|------|------|-------|-----------|-------|
| `protein_compendia` | `protein.snakefile` | 512G | 12h | Largest protein join |
| `chemical_compendia` | `chemical.snakefile` | 512G | 6h | Full chemical graph |
| `untyped_chemical_compendia` | `chemical.snakefile` | 512G | — | Pre-typing step |
| `gene_compendia` | `gene.snakefile` | 256G | 6h | Gene graph |
| `export_compendia_to_duckdb` | `duckdb.snakefile` | 512G | 6h | Per-compendium DuckDB export |
| `check_for_identically_labeled_cliques` | `duckdb.snakefile` | 1500G | — | Cross-compendium join |
| `check_for_duplicate_curies` | `duckdb.snakefile` | 1500G | — | Cross-compendium join |
| `check_for_duplicate_clique_leaders` | `duckdb.snakefile` | 1500G | — | Cross-compendium join |
| `chembl_labels_and_smiles` | `datacollect.snakefile` | 128G | — | RDF parse |
| `chemical_unichem_concordia` | `chemical.snakefile` | 128G | — | UniChem merge |
| `generate_pubmed_concords` | `publications.snakefile` | 128G | 24h | Full PubMed parse |
| `generate_pubmed_compendia` | `publications.snakefile` | 128G | — | PubMed compendium build |
| `geneprotein_conflated_synonyms` | `geneprotein.snakefile` | 512G | 6h | Conflated synonym merge |

## Localrules (Run on Head Node, No SLURM Slot)

The following rules are declared `localrules` and run on the head/login node without consuming a
SLURM allocation. They are trivial done-marker rules or cleanup rules:

| Rule | File |
|------|------|
| `all` | `Snakefile` |
| `all_outputs` | `Snakefile` |
| `clean_compendia` | `Snakefile` |
| `clean_downloads` | `Snakefile` |
| `export_all_to_kgx` | `exports.snakefile` |
| `export_all_to_sapbert_training` | `exports.snakefile` |
| `export_all_compendia_to_duckdb` | `duckdb.snakefile` |
| `export_all_synonyms_to_duckdb` | `duckdb.snakefile` |
| `export_all_to_duckdb` | `duckdb.snakefile` |
| `all_duckdb_reports` | `duckdb.snakefile` |
| `all_reports` | `reports.snakefile` |
| `geneprotein` | `geneprotein.snakefile` |
| `drugchemical` | `drugchemical.snakefile` |
| `publications` | `publications.snakefile` |
| `get_mesh_synonyms` | `datacollect.snakefile` |

## Out-of-Scope Improvements (Future Work)

The following improvements are tracked here for visibility but not yet implemented:

- **`uv run snakemake` vs `conda activate babel`**: The SLURM job scripts (`slurm/job`,
  `slurm/run-babel-on-slurm.sh`) still reference the old conda environment and hardcoded paths.
  Migrate to `uv run` for consistency with the development workflow.

- **`run_babel_one_node.job` cleanup**: This job script references a hardcoded conda env
  path and should be updated to use `uv run`.

- **1500G DuckDB rules**: `check_for_identically_labeled_cliques`, `check_for_duplicate_curies`,
  and `check_for_duplicate_clique_leaders` load the full cross-compendium Parquet dataset into
  memory. These may be rewritable with streaming DuckDB queries to reduce peak RSS.

- **Per-rule resource tuning**: After collecting benchmark data from a full run, add explicit
  `resources:` to every rule based on observed `max_rss + 30% headroom`. This will greatly reduce
  wasted SLURM allocations across the ~100+ rules currently defaulting to 64G/4-CPU.

- **`--local-cores N` flag**: Use this to limit the number of CPUs consumed by local rules
  when running on a shared login node.

- **Log accumulation**: Consider setting `slurm-delete-logfiles-older-than` to a nonzero value
  once log volume has been studied across multiple runs.
