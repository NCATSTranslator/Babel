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
| `check_for_identically_labeled_cliques` | `duckdb.snakefile` | 1500G | — | Two-pass: GROUP BY hash(LOWER(preferred_name)) + streaming-join pair output; memory_limit 1000G, 1 thread |
| `check_for_duplicate_curies` | `duckdb.snakefile` | 1500G | — | GROUP BY curie over all edges; memory_limit 1400G, 2 threads |
| `check_for_duplicate_clique_leaders` | `duckdb.snakefile` | 512G | — | Two-pass over the smaller Clique table; memory_limit 400G, 4 threads |
| `generate_curie_report` | `duckdb.snakefile` | 1500G | — | approx_count_distinct() over all edges, biolink_type read from the denormalized Edge column (no join); memory_limit 1000G, 1 thread |
| `generate_clique_leader_report` | `duckdb.snakefile` | 1500G | — | approx_count_distinct() over all edges; memory_limit 1000G, 1 thread |
| `chembl_labels_and_smiles` | `datacollect.snakefile` | 128G | — | RDF parse |
| `chemical_unichem_concordia` | `chemical.snakefile` | 128G | — | UniChem merge |
| `generate_pubmed_concords` | `publications.snakefile` | 128G | 24h | Full PubMed parse |
| `generate_pubmed_compendia` | `publications.snakefile` | 128G | — | PubMed compendium build |
| `geneprotein_conflated_synonyms` | `geneprotein.snakefile` | 512G | 6h | Conflated synonym merge |

## Temporary Scratch Space

The DuckDB rules (`export_*_to_duckdb` and the cross-compendium report rules in
`duckdb.snakefile`) spill larger-than-memory intermediates to a temp directory. By default that
is `tmp_directory` from `config.yaml` (`babel_downloads/tmp`, on the parallel filesystem).
`setup_duckdb()` gives each job its own `duckdb-$SLURM_JOB_ID` subdirectory there, so concurrent
jobs never share spill files — sharing one directory previously caused `stale file handle` and
`could not read enough bytes` IO errors when several report jobs ran at once.

Hatteras has no large node-local disk suitable for spilling:

- `/tmp` is the node-local rootfs SLURM advertises (`TmpFS=/tmp`), but it is only ~16 GB and
  there is no per-job isolation (`JobContainerType` is unset), so it fills almost immediately.
- `/dev/shm` is node-local but RAM-backed; its pages count against the job's cgroup memory limit
  (`ConstrainRAMSpace=yes`), so spilling there is effectively spilling to RAM and can trigger an
  OOM-kill.
- `/scratch` and `/projects` are both NFS, so they don't avoid the networked-filesystem class of
  error, though `/scratch` is a separate, less-contended server (50 TB free).

The cross-compendium report rules used to be sized to run entirely in RAM, because their
aggregations (a grouped `COUNT(DISTINCT)`, or a `LIST(... ORDER BY ...)`) could not spill and would
OOM rather than overflow to disk. Even on a full largemem node (`memory_limit` ≈ 1400G) several of
them still exceeded the physical ceiling of the largemem partition (~1.46 TiB) — and not always at
DuckDB's *tracked* limit: the killers were untracked allocations (string heaps, hash-join build
sides) that overshot the cgroup hard limit by hundreds of GiB before any spill kicked in, producing
a hard SIGKILL with no DuckDB error. Adding memory was exhausted, so they were rewritten so peak
memory is small by construction:

- `generate_curie_report` / `generate_clique_leader_report` use `approx_count_distinct()` (a
  fixed-size HyperLogLog sketch per group, ~2% error) instead of an exact `COUNT(DISTINCT)`. The
  exact totals (`COUNT`) stay exact; only the distinct counts are approximate, which is fine for a
  summary report.
- `generate_curie_report` also reads `biolink_type` straight off the Edge table (it is denormalized
  there at export time) instead of joining the full Edge table (~1.5B rows) against the Clique table
  (~200M rows). That large-vs-large join was the only one of its kind in the report suite and was
  the specific allocation that OOM-killed the rule; every other report either has no join or joins a
  huge table to a tiny one.
- `check_for_identically_labeled_cliques` finds duplicate names by grouping on a fixed-size
  `hash(LOWER(preferred_name))` rather than the name itself: there are ~200M cliques and
  `preferred_name` is often a long label, so grouping on the raw string built a ~200M-entry
  long-string heap that DuckDB does not fully track and that overshot the cgroup. It then emits the
  duplicate `(name, clique_leader)` pairs via a streaming hash join (small build side, no aggregate,
  no sort). The output is unsorted; each row carries the per-name count so a consumer can group/sort
  it cheaply.

All three run single-threaded with `memory_limit` set well below `mem` (1000G vs 1500G) so DuckDB
has a large headroom under the cgroup hard limit.

To override the spill location for a run — for example to point spills at a larger or less-contended
filesystem — set `BABEL_DUCKDB_TEMP_DIR` in the job environment; an individual rule can also pass
`temp_directory` / `max_temp_directory_size` in its `duckdb_config`. Do not point the
500 GB-spilling `export_*` rules at `/tmp` or `/dev/shm`.

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

- **Cross-compendium DuckDB report sizing**: `check_for_identically_labeled_cliques`,
  `generate_curie_report`, and `generate_clique_leader_report` were rewritten to keep peak memory
  small (`approx_count_distinct()` sketches; a hashed-key + streaming-join duplicate dump; a
  denormalized `biolink_type` column that removes the report's Edge-to-Clique join) and run
  single-threaded, but they still default to a full largemem node (1500G, `memory_limit` 1000G) out
  of caution. Once a full run confirms their real peak RSS, they can likely drop to a much smaller
  `mem`, freeing the largemem partition. `check_for_duplicate_*` use a two-pass spillable
  `COUNT(*)`-then-`LIST()`-over-confirmed-duplicates query; `check_for_duplicate_clique_leaders`
  already runs at 512G. Note: because `generate_curie_report` now reads `biolink_type` from the Edge
  parquet,
  `export_compendia_to_duckdb` must have been re-run after that column was added — the report cannot
  run against older Edge parquets that predate it.

- **Per-rule resource tuning**: After collecting benchmark data from a full run, add explicit
  `resources:` to every rule based on observed `max_rss + 30% headroom`. This will greatly reduce
  wasted SLURM allocations across the ~100+ rules currently defaulting to 64G/4-CPU.

- **`--local-cores N` flag**: Use this to limit the number of CPUs consumed by local rules
  when running on a shared login node.

- **Log accumulation**: Consider setting `slurm-delete-logfiles-older-than` to a nonzero value
  once log volume has been studied across multiple runs.
