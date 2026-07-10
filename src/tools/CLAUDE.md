# CLAUDE.md — src/tools/

Guidance for Claude Code when working under `src/tools/`. See `docs/tools/README.md` for the
full convention, the tool index, and how to add a new tool — read it before adding one.

**A tool is a thin CLI frontend.** Every tool lives in `src/tools/<tool>/` with a `cli.py`
exposing `main()`, wired up in `[project.scripts]`. Logic that models Babel data — cliques,
compendia, concords, ids — belongs in `src/` (e.g. `src/model/`) beside the code it models, so a
pipeline rule or a second tool can reuse it. A tool that reimplements pipeline functionality is a
bug. `src/tools/clique_diff/cli.py` is the pattern: the diff lives in
`src/model/compendium_diff.py`, the CLI is sixty lines over it.

`slurm` and `memory` (see their own `CLAUDE.md`s) are documented exceptions — they model SLURM
and RDF artifacts, not Babel data.

Bash invoked by path lives in `scripts/`, not here.
