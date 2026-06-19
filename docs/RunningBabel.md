# Running Babel

## Configuration

The [`../kubernetes`](../kubernetes) directory contains Kubernetes manifest files
that can be used to set up a Pod to run Babel in. They'll give you an idea of the disk
space and memory requirements needed to run this pipeline.

Before running, read through `config.yaml` and make sure that the settings look correct.
You will need to update the version numbers of some databases that need to be downloaded,
or change the download and output directories.

A UMLS API key is required in order to download UMLS and RxNorm databases. You will need
to set the `UMLS_API_KEY` environmental variable to a UMLS API key, which you can obtain
by creating a profile on the [UMLS Terminology Services website](https://uts.nlm.nih.gov/uts).

## Building Compendia

To run Babel, you will need to
[install `uv`](https://docs.astral.sh/uv/getting-started/installation/). `uv` manages the Python
environment and installs dependencies for you.

Compendia building is managed by snakemake. To build, for example, the anatomy related compendia,
run

```uv run snakemake --cores 1 anatomy```

Currently, the following targets build compendia and synonym files:

* anatomy
* cell_line
* chemical
* disease
* gene
* genefamily
* leftover_umls
* protein
* macromolecular_complex
* taxon
* process
* publications

And these two build conflations:

* geneprotein
* drugchemical

Each target builds one or more compendia corresponding to a biolink model category. For instance,
the anatomy target builds compendia for `biolink:AnatomicalEntity`, `biolink:Cell`,
`biolink:CellularComponent`, and `biolink:GrossAnatomicalStructure`.

You can also just run:

```uv run snakemake --cores 1```

without a target to create all the files that are produced as part of Babel, including all reports
and alternate exports.

If you have multiple CPUs available, you can increase the number of `--cores` to run multiple steps
in parallel.

## Build Process

When running on the RENCI Hatteras cluster via SLURM, see [Performance.md](Performance.md) for how
per-rule memory/CPU/runtime limits are measured (Snakemake `benchmark:` TSVs) and right-sized with
`tools/slurm`, and how to find which failed rules to re-run when a run stalls.

### Analyzing a SLURM run with `tools.slurm`

`tools.slurm` is a small package that analyzes a (possibly partial) Snakemake-on-SLURM run. It has
two subcommands that share one parsing layer (`tools/slurm/parse.py`), and is run as a Python
module:

```bash
# Recommend right-sized mem/cpus from a run's benchmark + efficiency data:
uv run python -m tools.slurm resources <run-dir>
uv run python -m tools.slurm resources <run-dir> --csv /tmp/resources.csv --new-default-mem-gb 16

# Aggregate failing-rule logs (and a completed/failed/running job summary) when a run stalls:
uv run python -m tools.slurm errors <version> --markdown
```

`<run-dir>` is a directory containing `benchmarks/`, `logs/`, and (optionally) `reports/slurm/` —
either `babel_outputs/` itself or a copy such as `data/babel-1.17/babel_outputs`. `<version>` is
the tag in the `sbatch-<version>.err` control-node log (omit it to auto-detect the newest).

The two subcommands answer different questions — `resources` is for capacity tuning between runs,
`errors` is for failure triage during a run — so they are kept as separate subcommands rather than
merged, but they live in one package because both parse the same run artifacts. `errors` replaces
the former `tools/babel-errors.py` script. See [Performance.md](Performance.md) for the full
resource-tuning workflow and what each report column means.

The information contained here is not required to create the compendia, but may be useful to
understand. The build process is divided into two parts:

1. Pulling data from external sources and parsing it independent of use.
2. Extracting and combining entities for specific types from these downloaded data sets.

This distinction is made because a single data set, such as MeSH or UMLS may contain entities of
many different types and may be used by many downstream targets.

### Pulling Data

The datacollection snakemake file coordinates pulling data from external sources into a local
filesystem. Each data source has a module in `src/datahandlers`. Data goes into the
`babel_downloads` directory, in subdirectories named by the curie prefix for that data set. If the
directory is misnamed and does not match the prefix, then labels will not be added to the
identifiers in the final compendium.

Once data is assembled, we attempt to create two extra files for each data source: `labels` and
`synonyms`. `labels` is a two-column tab-delimited file. The first column is a CURIE identifier from
the data source, and the second column is the label from that data set. Each entity should only
appear once in the `labels` file. The `labels` file for a data set does not subset the data for a
specific purpose, but contains all labels for any entity in that data set.

`synonyms` contains other lexical names for the entity and is a 3-column tab-delimited file, with
the second column indicating the type of synonym (exact, related, xref, etc.)

### Creating compendia

The individual details of creating a compendium vary, but all follow the same essential pattern.

First, we extract the identifiers that will be used in the compendia from each data source that will
contribute, and place them into a directory. For instance, in the build of the chemical compendium,
these ids are placed into `babel_outputs/intermediate/chemicals/ids`. Each file is a two-column file
containing curie identifiers in column 1, and the Biolink type for that entity in column 2.

Second, we create pairwise concords across vocabularies. These are placed in e.g.
`babel_outputs/intermediate/chemicals/concords`. Each concord is a three-column file of the format:

`<curie1> <relation> <curie2>`

While the relation is currently unused, future versions of Babel may use the relation in building
cliques.

Third, the compendia is built by bringing together the ids and concords, pulling in the categories
from the id files, and the labels from the label files.

Fourth, the compendia is assessed to make sure that all the ids in the id files made into one of the
possibly multiple compendia. The compendia are further assessed to locate large cliques and display
the level of vocabulary merging.

## Building with Docker

You can build this repository by running the following Docker command:

```text
$ docker build .
```

It is also set up with a GitHub Action that will automatically generate and publish
Docker images to <https://github.com/NCATSTranslator/Babel/pkgs/container/babel>.

## Running with Docker

You can also run Babel with [Docker](https://www.docker.com/). There are
two directories you need to bind or mount from outside the container:

```text
$ docker run -it --rm --mount type=bind,source=...,target=/home/runner/babel/babel_downloads --entrypoint /bin/bash ggvaidya/babel
```

The download directory (`babel/babel_downloads`) is used to store data files downloaded during Babel
assembly.

The script `scripts/babel-build.sh` can be used to run `snakemake` with a few useful settings
(although just running `uv run snakemake --cores 5` should work just fine.)

## Running with Kubernetes

The `kubernetes/` directory has example Kubernetes scripts for deploying Babel to a Kubernetes
cluster. You need to create three resources:

* `kubernetes/babel-downloads.k8s.yaml` creates a Persistent Volume Claim (PVC) for downloading
  input resources from the internet.
* `kubernetes/babel-outputs.k8s.yaml` creates a PVC for storing the output files generated by Babel.
  This includes compendia, synonym files, reports and intermediate files.
* `kubernetes/babel.k8s.yaml` creates a pod running the latest Docker image from ggvaidya/babel.
  Rather than running the data generation automatically, you are expected to SSH into this pod and
  start the build process by:
    1. Edit the script `scripts/babel-build.sh` to clear the `DRY_RUN` property so that it doesn't,
       i.e.:

       ```shell
       export DRY_RUN=
       ```

    2. Creating a [screen](https://www.gnu.org/software/screen/) to run the program in. You can
       start a Screen by running:

       ```shell
       $ screen
       ```

    3. Starting the Babel build process by running:

       ```shell
       $ bash scripts/babel-build.sh
       ```

       Ideally, this should produce the entire Babel output in a single run. You can also add
       `--rerun-incomplete` if you need to restart a partially completed job.

       To help with debugging, the Babel image includes .git information. You can switch branches,
       or fetch new branches from GitHub by running `git fetch origin-https`.

    4. Press `Ctrl+A D` to "detach" the screen. You can reconnect to a detached screen by running
       `screen -r`. You can also see a list of all running screens by running `screen -l`.

    5. Once the generation completes, all output files should be in the `babel_outputs` directory.

## Releasing a new Babel version

A full production run happens on an HPC system over many hours, and it almost always
surfaces problems that aren't visible from a local dry run: wrong memory settings,
download endpoints that have moved or started blocking us, format changes upstream, and
latent bugs that only fire at full scale. The practical way to keep a run moving is to
fix these directly on the release branch (for example `babel-1.17`) rather than stopping
to open a separate PR for each one. By the time the run is healthy, the release branch
holds a long, date-interleaved mix of trivial tweaks and substantial changes.

Before that branch is merged, it is worth separating the two kinds of change.
The scripts in [`../tools/commit-split`](../tools/commit-split) help verify the
split is complete and lossless; see that directory's `README.md`.

### Which commits stay on the release branch

A commit can stay on the release branch if its entire effect fits in a single
release-note line, for example "updated the ENSEMBL dataset skip list", "bumped the
Biolink Model version", or "raised a rule's memory limit". These are the expected
running-a-build adjustments and reviewing them inline with the release is fine.

Everything else should move to its own branch off `main` and be reviewed as a normal
PR, so the change is documented, gets a real review, and earns its own release-note
entry. Related commits move together as one PR even if they were made days apart: all
the download-robustness work is one PR, all the DuckDB memory tuning is another, and so
on. Documentation and formatting commits travel with the code they describe rather than
staying behind on the release branch.

### Splitting the branch

1. **Classify by theme, not by date.** The commits interleave chronologically but group
   cleanly by the files they touch. List `git rev-list --no-merges main..<release-branch>`
   with each commit's changed files and bucket them (download robustness, a specific
   source's ingest, export/reporting, tooling, and so on).
2. **Make a backup ref** (`git branch <release-branch>-backup <release-branch>`) before
   anything that will later rewrite the release branch.
3. **Build one branch per theme off `main`** with `git cherry-pick`, replaying each
   bucket's commits in chronological order. Enable `git rerere` so a conflict you resolve
   once (typically in shared files like `config.yaml`, `datacollect.snakefile`, or
   `CLAUDE.md`) is replayed automatically if you have to rebuild the branch.
4. **Watch for entangled and coupled commits.** Two themes that edit the same file in
   alternating commits may need one branch *stacked on* the other (cherry-pick the second
   theme on top of the first) rather than both off `main` — that reconstructs the original
   context and avoids fighting conflicts. Also watch for a "workaround then fix" pair
   split across buckets: for example a commit that raises a memory limit as a stopgap and
   a later commit that removes the stopgap after fixing the root cause must live in the
   same PR, or the net effect on the release branch changes.
5. **Verify each branch independently** with the full CI gate — `uv run ruff check`,
   `uv run ruff format --check`, `uv run snakefmt --check --compact-diff .`,
   `uv run rumdl check .`, and `uv run pytest -m unit` — plus the cluster's own tests. A
   branch that carries a behavior change but no test gets a small regression test added.
6. **Prove nothing was lost.** Compare `git patch-id --stable` for every commit in
   `main..<release-branch>` against the patch-ids present across all theme branches: every
   moved commit should appear in exactly one branch, and every stay-behind commit should
   appear in none. Commits you deliberately adapted while resolving a conflict will differ;
   confirm those by diffing the applied change against the original so only context, not
   added or removed lines, has changed.
7. **Reintegrate.** Once the theme PRs are merged into `main`, merge or rebase `main` into
   the release branch. The commits that were split out arrive via `main` and drop out of
   the release branch's own diff, leaving only the stay-behind commits there.
