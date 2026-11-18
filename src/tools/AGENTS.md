# AGENTS.md — src/tools/

Guidance for coding agents working under `src/tools/`. See `docs/tools/README.md` for the
full convention, the tool index, and how to add a new tool — read it before adding one.

**A tool is a thin CLI frontend.** Every tool lives in `src/tools/<tool>/` with a `cli.py`
exposing `main()`, wired up in `[project.scripts]`. Logic that models Babel data — cliques,
compendia, concords, ids — belongs in `src/` (e.g. `src/model/`) beside the code it models, so a
pipeline rule or a second tool can reuse it. A tool that reimplements pipeline functionality is a
bug. `src/tools/clique_diff/cli.py` is the pattern: the diff lives in
`src/model/compendium_diff.py`, the CLI is sixty lines over it.

`slurm` and `memory` are the documented exceptions ("The exceptions" in `docs/tools/README.md`):
`slurm/parse.py` models Snakemake `benchmark:` TSVs and SLURM `.err` logs (see `slurm/AGENTS.md`),
and `memory/estimate_rdf_load_memory.py` measures `pyoxigraph`'s RSS while it loads an RDF dump
(see `docs/tools/Memory.md`; the script is run by path and has no `cli.py`). Neither reads Babel
data, so neither has anything to hoist into `src/`: leave their logic where it is. `memory` has no
`AGENTS.md` of its own, so this paragraph is the note for it.

Bash invoked by path lives in `scripts/`, not here.
