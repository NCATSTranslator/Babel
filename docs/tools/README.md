# Developer tools

Tooling that helps you build, debug, and analyse Babel but is not part of the compendium
pipeline. Each tool lives in `src/tools/<tool>/` and is installed as a console script by
`uv sync`, so it picks up the project's pinned environment.

## The tools

| Tool | Command | What it answers |
|------|---------|-----------------|
| [Source impact report](SourceImpactReport.md) | `uv run source-impact-report --source <SOURCE>` | "What does adding *this data source* do to the cliques?" |
| [Clique diff](CliqueDiff.md) | `uv run babel-clique-diff --before <dir> --after <dir> …` | "How did the cliques change between *build A* and *build B*?" |
| [SLURM errors](Errors.md) | `uv run babel-slurm-errors <version>` | "Which rules failed in this cluster run, and why?" |
| [SLURM resources](Resources.md) | `uv run babel-slurm-resources <run-dir>` | "How much `mem`/`cpus` should each rule actually request?" |
| [RDF load memory](Memory.md) | `uv run python src/tools/memory/estimate_rdf_load_memory.py FILE` | "How much RAM will bulk-loading this RDF dump need?" |

The two clique tools are easy to confuse. `source-impact-report` re-gloms the intermediate
ids/concords **with and without one source**, over the same code. `babel-clique-diff` compares
**two finished builds** whose inputs are the same but whose code, config, or upstream data
differ — so it is the only one that can see cliques that *split, shrank, or disappeared*, and
the only option for a change that isn't "add a source" at all. See
[CliqueDiff.md](CliqueDiff.md).

Bash scripts that *operate* a build rather than analyse one — launching snakemake, staging
inputs, publishing outputs — live in [`scripts/`](../../scripts/README.md) instead.

## Writing a new tool

**A tool is a thin CLI frontend.** It parses arguments, reads and writes files, and prints. That
is all.

**Logic that models Babel data — cliques, compendia, concords, ids — belongs in `src/`,** beside
the code it models, never in the tool. A tool that reimplements pipeline functionality is a bug:
the reimplementation drifts from the pipeline it is supposed to describe, and the next tool that
needs the same logic writes a third copy. `babel-clique-diff` is the worked example. Its diff
lives in `src/model/compendium_diff.py`; `src/tools/clique_diff/cli.py` is sixty lines of
argparse and CSV writing over it.

So a new tool is:

1. `src/tools/<tool>/cli.py` — `main(argv=None)`, plus an `__init__.py` explaining what the tool
   is and where its logic lives.
2. Whatever library code it needs, added to `src/` (`src/model/` for data structures,
   `src/reports/` for renderers) and importable by anything else.
3. An entry in `[project.scripts]` in `pyproject.toml`, pointing at `src.tools.<tool>.cli:main`.
4. A `unit` test of the CLI in `tests/tools/<tool>/`, and tests of the library code beside it
   (e.g. `tests/model/`). Everything under `src/` is covered by `--cov=src` automatically.
5. A page in this directory, and a row in the table above.

### The exceptions

`slurm` and `memory` are self-contained: `slurm/parse.py` models Snakemake `benchmark:` TSVs and
SLURM `.err` files, and the memory estimator models `pyoxigraph`'s RSS. Neither reads Babel data,
so neither has anything to hoist into `src/` and no pipeline rule will ever import them. Leave
them alone.

They may not stay exceptions forever. Once output reading/writing
([#759](https://github.com/NCATSTranslator/Babel/issues/759)) and intermediate reading/writing
([#736](https://github.com/NCATSTranslator/Babel/issues/736)) are centralized, they may have
something to reuse — though probably not.

Tools-or-core is a judgement call, made per tool as the need arises, not a law. Once the code
exists it is easy to move; the rule above is the default, not a gate.
