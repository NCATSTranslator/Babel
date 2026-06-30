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

- **`errors`** aggregates the logs of failing rules into one copy-pasteable report and prints a
  completed / failed / still-running job summary. Run it on a loop during an active cluster job to
  catch failures early and feed them to a coding agent while the rest of the DAG keeps running; it
  is also invoked automatically by
  [`slurm/run-babel-on-slurm.sh`](../../slurm/run-babel-on-slurm.sh) when a run exits non-zero. It
  is the successor to the former `tools/babel-errors.py` script. See
  [Errors.md](Errors.md).
- **`resources`** joins each rule's *actual* usage (Snakemake `benchmark:` TSVs) against its
  *requested* resources and recommends right-sized `mem`/`cpus`, flagging the rules that would need
  an explicit override before the cluster-wide default can be lowered. See
  [Resources.md](Resources.md).

The two answer different questions — failure triage versus capacity planning — so they are kept as
separate subcommands, but they live in one package because both parse the same run artifacts.

## `tools/memory` — estimate RDF load memory

`tools/memory/estimate_rdf_load_memory.py` streams an RDF dump into an in-memory
`pyoxigraph.Store`, samples RSS, and extrapolates the full-load peak, so you can size a rule's
`mem=` resource or a test's `min_memory_gb` guard from a machine far smaller than the eventual
requirement. See [../../tools/memory/README.md](../../tools/memory/README.md).

## `tools/clique_diff` — diff the cliques of two builds

`tools/clique_diff` compares the finished JSONL compendia of two Babel builds and reports
which cliques split, merged, or lost members, and — most usefully — which CURIEs were
*dropped* from the output entirely.

```bash
uv run babel-clique-diff \
    --before <baseline-compendia-dir> --after <comparison-compendia-dir> \
    --files Disease.txt PhenotypicFeature.txt \
    --out-csv diff.csv --out-json summary.json
```

It is distinct from `source-impact-report`: that answers "what does adding *source X* do?"
by re-glomming intermediate ids/concords with vs. without one source; this answers "how did
the cliques change between *build A* and *build B*?" given the same inputs but different code,
config, or upstream data. Because it works on finished compendia rather than glom state, it
can compare a local build against a published `stars.renci.org` build without re-running
glom, which makes it a fit for validating any glom-logic change (close-match handling,
`unique_prefixes`, overuse filtering) or as a release regression check. Commit a worked
example's output alongside the change that motivated it, under
`docs/sources/<SOURCE>/<change>/` or `docs/pipelines/<pipeline>/<change>/` (always the small
`clique-diff.summary.json`, plus the per-row `clique-diff.csv` when reasonably sized).
