# Developer tools

The `tools/` directory holds developer and operations tooling that supports building and
debugging Babel but is not part of the compendium pipeline itself. Each is run with `uv run` so it
picks up the project's pinned environment.

## `tools/slurm` — analyze a SLURM run

`tools/slurm` analyzes a (possibly partial) Snakemake-on-SLURM run. It exposes two commands
installed by `uv sync`, which share a single parsing layer (`tools/slurm/parse.py`):

```bash
uv run babel-slurm-errors <version> --markdown     # failure triage during a run
uv run babel-slurm-resources <run-dir>             # capacity tuning between runs
```

- **`errors`** aggregates the logs of failing rules from a stalled or failed run into one
  copy-pasteable report, and prints a completed / failed / still-running job summary, so you can
  see which rules to re-run. It is the successor to the former `tools/babel-errors.py` script and
  is invoked automatically by [`slurm/run-babel-on-slurm.sh`](../slurm/run-babel-on-slurm.sh) when
  a run exits non-zero. See [tools/Errors.md](tools/Errors.md).
- **`resources`** joins each rule's *actual* usage (Snakemake `benchmark:` TSVs) against its
  *requested* resources and recommends right-sized `mem`/`cpus`, flagging the rules that would need
  an explicit override before the cluster-wide default can be lowered. See
  [tools/Resources.md](tools/Resources.md).

The two answer different questions — failure triage versus capacity planning — so they are kept as
separate subcommands, but they live in one package because both parse the same run artifacts.

## `tools/memory` — estimate RDF load memory

`tools/memory/estimate_rdf_load_memory.py` streams an RDF dump into an in-memory
`pyoxigraph.Store`, samples RSS, and extrapolates the full-load peak, so you can size a rule's
`mem=` resource or a test's `min_memory_gb` guard from a machine far smaller than the eventual
requirement. See [../tools/memory/README.md](../tools/memory/README.md).
