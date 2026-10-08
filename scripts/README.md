# Operator scripts

Bash scripts you invoke by path to *operate* a Babel run: launch a build, stage its inputs,
publish its outputs, or tidy a release branch.

## What lives here, and what doesn't

A script belongs in `scripts/` when it is invoked by path (`bash scripts/babel-build.sh`) rather
than imported, installed, or tested. Nothing here is part of the `babel-pipeline` Python package.

Anything written in Python belongs in `src/tools/` instead, as a thin CLI over
`src/` library code, installed as a console script and covered by the test suite. See
[`docs/tools/README.md`](../docs/tools/README.md) for that convention and an index of the tools.
The short version: `scripts/` *runs* Babel, `src/tools/` *analyses* what Babel produced.

## Contents

- `babel-build.sh` — configure and invoke `snakemake` with a set of useful defaults (cores, dry
  run, keep-going, rerun-incomplete). Edit the exports at the top, then
  `bash scripts/babel-build.sh [target]`. Documented in
  [`docs/RunningBabel.md`](../docs/RunningBabel.md).
- `copy-babel-private.sh` — rsync the private input data from a remote host into
  `input_data/private/` before a build. Set `USERNAME`/`HOSTNAME` at the top first.
- `rsync-to-server.sh` — rsync `babel_outputs/` to another server after a build, excluding the
  large DuckDB databases. Takes the destination as its one argument.
- `commit-split/` — verify that a release branch's commits were split into themed PRs completely
  and losslessly. See [`commit-split/README.md`](commit-split/README.md) and the "Releasing a new
  Babel version" section of [`docs/RunningBabel.md`](../docs/RunningBabel.md).

`slurm/run-babel-on-slurm.sh` is the cluster-side sibling of `babel-build.sh`. It lives in
[`../slurm/`](../slurm/) alongside the SLURM job files and cluster config it depends on.
