# Developing Babel

This document describes the current development workflow for Babel and ideas for improving it.

## Current Development Process

Developing a change to Babel is significantly more complicated than developing most software,
because the pipeline operates on very large data files that take hours to download, gigabytes of
disk space to store, and hundreds of gigabytes of RAM to process. This creates a feedback loop
that is slow by necessity.

### Typical workflow

1. **Build prerequisites.** Before writing any code, you need the input files for the Snakemake
   step you plan to modify. There are two ways to get these:
   - Run the upstream Snakemake rules yourself (which may themselves require large downloads).
   - Copy intermediate files from the last successful full run, e.g. from the SLURM cluster.

2. **Write code.** Implement the change locally, iterating against whatever prerequisite files are
   available.

3. **Run the relevant target.** For example, if you changed how anatomy compendia are built:

   ```bash
   uv run snakemake --cores 1 anatomy
   ```

   This produces compendia and synonym files for the anatomy semantic type, but does _not_ trigger
   the pipeline-wide reports, which require _all_ compendia, synonym, and conflation files.

4. **Review your own output.** Because reports are not available, you must inspect the output files
   manually — checking JSONL structure, spot-checking a few cliques, and reviewing completeness
   reports. There is no automated feedback at this stage.

5. **Merge.** The change goes in without confirmation that it behaves correctly in the context of
   the full pipeline.

6. **Wait for SLURM.** The next time someone runs the full pipeline on the SLURM cluster, you
   find out whether your change worked. If it did not, the turnaround for a fix is another full
   run.

### Why this is hard

- **Download cost.** Many data sources (UMLS, UniChem, PubChem, UniProt TrEMBL) are multi-gigabyte
  downloads that take hours. You cannot easily re-download them per experiment.
- **Memory cost.** The chemical and protein compendia steps require 512 GB of RAM, which is not
  available on a laptop or a typical workstation.
- **Cross-type report dependencies.** The `all_reports` target in `reports.snakefile` requires
  every compendium, synonym, and conflation file to exist before it will run. Building one semantic
  type's compendium in isolation does not satisfy these dependencies.
- **No unit-testable seams.** The core compendium-building logic (`createcompendia/`) reads and
  writes large files. There is no easy way to run it against a small, synthetic dataset without
  manually constructing the full file layout.
- **Opaque intermediate state.** Snakemake tracks what has been built via file existence and
  timestamps. There is no summary of what prerequisites are present and what is missing.

---

## Ideas for Improvement

The suggestions below range from small scripts you could add this week to multi-month architectural
changes. All are worth considering.

### Small, practical improvements

#### 1. Per-compendium assessment script (`src/scripts/assess_compendium.py`)

A standalone CLI script that takes a compendium JSONL file as input and prints a human-readable
summary: number of cliques, clique size distribution, identifier prefix breakdown, large-clique
examples, and any structural validation errors. This mirrors what the pipeline's `assess` rules do
today, but can be run against _any_ compendium file, including one built from a partial dataset,
without needing the full pipeline to have run.

```bash
uv run assess-compendium babel_outputs/compendia/AnatomicalEntity.txt
```

#### 2. Compendium diff script (`src/scripts/diff_compendia.py`)

A CLI script that compares two compendium files and reports:

- Cliques that appear in one but not the other.
- Cliques whose membership changed (identifiers added or removed).
- Cliques whose preferred identifier (clique leader) changed.
- Summary statistics: total cliques gained/lost, total identifiers gained/lost.

This would immediately tell you whether a code change had the intended effect when you copy a
before/after snapshot.

```bash
uv run diff-compendia old/AnatomicalEntity.txt new/AnatomicalEntity.txt
```

#### 3. CURIE lookup script (`src/scripts/lookup_curie.py`)

A CLI script that searches all compendium files in a directory for a given CURIE and prints the
full clique it belongs to. Useful for spot-checking whether a specific identifier was correctly
merged.

```bash
uv run lookup-curie MESH:D014867 --compendia-dir babel_outputs/compendia/
```

#### 4. Concord inspector script (`src/scripts/inspect_concord.py`)

A CLI script that reads one or more concord files (the `CURIE1 \t relation \t CURIE2` files in
`intermediate/*/concords/`) and shows statistics: which prefixes appear, how many cross-references
exist per prefix pair, and examples of entries. This makes it easier to verify that a concord
generation step is working before building the full compendium.

```bash
uv run inspect-concord babel_outputs/intermediate/chemicals/concords/CHEBI
```

#### 5. Snakemake dependency checker (`src/scripts/check_prerequisites.py`)

A script that reads `config.yaml` and checks which intermediate and download files are present on
disk, printing a table of what is available versus missing. This would tell you immediately which
prerequisites you need to copy before you can run a particular target.

```bash
uv run check-prerequisites --target anatomy
```

#### 6. Per-type report targets in `reports.snakefile`

Currently `all_reports` requires all compendia. Adding per-type report targets (e.g.,
`anatomy_report`, `chemical_report`) that only require the files for that semantic type would let
you run a meaningful report in isolation. The per-compendium content report rules already exist
(`generate_content_report_for_compendium_*`); they just need to be wired into per-type aggregate
rules.

#### 7. Structured logging for compendium building

The compendium-building Python code (`createcompendia/`) currently logs to a mix of `print` and
Python logging. Adding structured JSON log output (e.g., counts of identifiers processed, concords
merged, cliques formed at each stage) would make it possible to write a script that summarizes
pipeline behavior from logs alone, without inspecting output files.

---

### Medium-effort improvements

#### 8. Mini-dataset fixtures for each data source

Each data handler in `src/datahandlers/` reads a specific file format. For each handler, create a
small, representative fixture file (a few hundred rows) checked into `tests/fixtures/`. Then write
a test that runs the handler against the fixture and checks the resulting `labels`, `synonyms`, and
`ids` files. This would let you run a fast integration test for a data handler without downloading
anything.

This builds naturally on the existing test infrastructure in `tests/`.

#### 9. Development config with smaller targets (`config.dev.yaml`)

A second `config.yaml` variant that points to smaller fixture datasets and has reduced prefix
lists. Running `uv run snakemake --configfile config.dev.yaml --cores 4` would exercise the full
pipeline structure (all rules, all file handoffs) against toy data, completing in minutes rather
than hours. The output would be structurally valid but not biologically complete.

#### 10. Standalone compendium builder script

A script that accepts a list of concord files and id files as command-line arguments and runs
just the union-find merge (`make_cliques.py`) to produce a compendium file, without any Snakemake
involvement. This decouples the algorithmic core from the orchestration layer, making it easy to
experiment with clique-merging logic on captured intermediate files.

```bash
uv run build-cliques \
    --ids intermediate/chemicals/ids/* \
    --concords intermediate/chemicals/concords/* \
    --output my_test_compendium.jsonl
```

#### 11. Remote intermediate file cache

A script (or Snakemake rule) that syncs a canonical set of intermediate files from object storage
(S3, GCS, or a shared NFS path) to your local machine. This means developers don't have to run
data collection steps themselves — they pull the outputs of the last successful full run. Combined
with a clear versioning scheme (tied to the data source versions in `config.yaml`), this could
eliminate most of the prerequisite-gathering step.

#### 12. Compendium regression test suite

After each full pipeline run, serialize summary statistics for every compendium (total cliques,
cliques per prefix, median clique size, etc.) as a JSON file and commit it to the repository.
On subsequent runs, compare against this baseline and fail if any metric changes by more than a
configurable threshold. This would catch regressions automatically and provide the feedback loop
that is currently missing.

---

### Large, sweeping changes

#### 13. Isolate semantic types into independent sub-pipelines

Currently the reports depend on all semantic types together, creating a hard global dependency.
If each semantic type were a self-contained sub-pipeline — with its own report, its own
completeness check, and its own done-marker — developers could run and validate a single type
end-to-end without touching any other type. This would require refactoring the report rules but
would not change the pipeline logic.

#### 14. Unit-testable Python API for compendium building

The compendium-building code in `createcompendia/` directly reads and writes files. Refactoring it
so that each function accepts Python data structures (lists of ID tuples, concord triples) and
returns clique structures — with file I/O as a separate layer — would make every step independently
unit-testable. Snakemake rules would remain as thin wrappers that read inputs from disk, call the
Python API, and write outputs to disk.

This is the highest-value architectural change for long-term maintainability.

#### 15. Streaming / chunked processing with DuckDB

Several steps require hundreds of gigabytes of RAM because they load entire files into memory.
`TSVSQLiteLoader` already attempts to mitigate this with an in-memory SQLite database. A further
step would be to use DuckDB (already present in the pipeline for exports) as the primary
intermediate store throughout compendium building — storing ids, concords, and partial cliques in
DuckDB tables on disk, and performing joins and aggregations inside DuckDB rather than in Python
memory. This would reduce RAM requirements substantially and make more steps runnable on
development hardware.

#### 16. Containerized development environment with prebuilt downloads

A Docker image (separate from the production image) that includes a curated, compressed snapshot
of all download data — not full production datasets, but representative subsets sufficient to
exercise every code path. A developer could `docker pull` this image, mount their source code, and
run the full pipeline against it in a few hours on a workstation. This is the closest thing to a
reproducible, low-friction development environment for a pipeline of this scale.

#### 17. Per-data-source version pinning and change detection

Currently, when an upstream data source changes (e.g. a new UMLS release), it is not always clear
which parts of the pipeline are affected. Adding an explicit version manifest — a file that records
the version/checksum of each downloaded resource — would allow a script to compare against the
previous manifest and report exactly which downstream compendia need to be rebuilt. This would
make release preparation more predictable and reduce unnecessary re-runs.
