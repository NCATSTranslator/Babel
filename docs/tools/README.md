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
    --before-label "main (no MP)" --after-label "mp-hp-disjoint" \
    --note "isolates PR #886" \
    --out-csv diff.csv --out-json summary.json
```

`--before-label`/`--after-label`/`--note` are optional but recommended: they are recorded in the
summary's `about` block so the artifact is self-describing (a reader never has to guess which build
was before vs after, or what the diff isolates). Labels default to the directory paths.

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

### What is (and isn't) diffed

Per compendium line, the tool reads exactly two fields: the clique's **leader** (the
preferred identifier, `identifiers[0].i`) and its **membership** (the full set of
`identifiers[*].i` CURIEs). A clique is unchanged only if *both* are identical between
builds; if either changed, every before-clique member is classified into one row per
`destination_kind`:

- `kept` — same leader, and the member is still under it.
- `leader_changed` — the whole clique's membership is byte-identical, but its preferred
  identifier was reassigned to a different member (e.g. a Biolink `id_prefixes` priority
  change, or `NodeFactory` tie-breaking, picked a new leader).
- `regrouped` — the member moved to a different clique within the same compared compendium
  file (a real split/merge).
- `moved` — the CURIE still exists in the after build, but under a different compendium
  file (e.g. `Disease.txt` → `PhenotypicFeature.txt`) — it was retyped to a different
  Biolink type.
- `dropped` — the CURIE is absent from every compared after compendium.

Everything else in a compendium record — `type` (Biolink type), `identifiers[*].l`
(labels), `identifiers[*].d`/`t` (descriptions/taxa), `preferred_name`, `ic`, and
`clique_identifier_count` — is **not compared**. In particular:

- A clique's Biolink `type` is not diffed directly. A type change is only visible
  indirectly, as `moved`, and only when the before- and after-type's compendium files are
  both passed to `--files` — a type change between two files neither of which was passed
  is invisible to this tool.
- Label, description, and taxon changes on an otherwise-unchanged clique are invisible;
  such a clique is reported as fully unchanged (no row at all).

Labels and Biolink types are not part of change detection, but they *are* emitted as
read-only annotation columns to make the CSV legible without a separate lookup:
`before_leader_label` and `before_leader_type` (the before-build label and type of the
clique leader), `destination_type` (the Biolink type the grouped members ended up as in the
after build — the after-clique's type for real destinations, the `|`-joined distinct types
of the members for `moved`, empty for `dropped`), and `example_members`, which lists up to
five members as `CURIE "label"` using before-build labels.

### Summary JSON

`--out-json` writes a self-describing summary, `{"about": …, "compendia": …}`. `about` carries
the two build labels, the `note`, and the compared `files`. `compendia` maps each filename to its
counts: a nested `clique_count` (`before`/`after`/`diff`/`diff_percent`) plus
`changed_before_cliques`, `dropped_member_count` (the headline regression signal),
`moved_member_count`, `regrouped_member_count`, and `leader_changed_count`.

One subtlety worth internalizing: a clique that exists **only** in the after build — no before
counterpart, e.g. a wholly new MP-only clique — is *not* a change row, because the tool iterates
before-cliques. Such additions surface **only** as a positive `clique_count.diff`. That is why a
build that adds thousands of new cliques can still show very few change rows; to see the additions
themselves, read the count delta (or use `source-impact-report`, whose whole job is the "added"
view). See `docs/sources/MP/disjointness.md` for a worked example of this exact reconciliation.
