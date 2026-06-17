# Contributing to Babel

Babel is open-source software and all contributions are very welcome!

## Reporting bugs

Reporting when you see something wrong with Babel is very helpful, whether you
spot it in the Babel output files or through one of the frontends. See
[docs/NewIssue.md](./docs/NewIssue.md) for full guidance on where to file,
what to include, and how to fill in the project fields.

In brief: file clique content issues in the [Babel issue tracker]; issues
specific to the [Node Normalizer] or [Name Resolver] applications go in their
respective issue trackers. If you are unsure, file in Babel and we will sort it
out.

## Contributing source code

For an overview of how Babel's source code is organized — including the two-phase pipeline,
the role of concord files, and the key patterns used throughout the codebase — see
[docs/Architecture.md](./docs/Architecture.md).

For a detailed guide to the development workflow — including how to obtain prerequisites, build
individual compendia, and ideas for making the pipeline easier to work with — see
[docs/Development.md](./docs/Development.md).

We use several linters and formatters to check the style of submitted code in GitHub pull
requests -- don't worry if this is difficult to do at your end, as it is easy to
fix in a pull request:

- [ruff](https://docs.astral.sh/ruff/) for Python code
  - You can run `uv run ruff check` to lint and `uv run ruff format --check` to check formatting.
  - You can use `uv run ruff check --fix` and `uv run ruff format` to automatically fix issues.
- [snakefmt](https://github.com/snakemake/snakefmt) for Snakemake files
  - You can run this locally by running
    `uv run snakefmt --check --compact-diff .`.
  - You can use `uv run snakefmt .` to automatically fix some issues.
- [rumdl](https://rumdl.dev/) for Markdown files
  - You can run this locally by running `uv run rumdl check .`.
  - You can use `uv run rumdl fmt .` to automatically fix some issues.

### Contributing tests

Tests are written using [pytest](https://pytest.org/) and are present in the
`tests` directory. You can run these tests by running
`PYTHONPATH=. uv run pytest`.

For the full test taxonomy — marks (`unit`, `network`, `slow`, `pipeline`),
where to add a new test, and how to run specific subsets — see
[tests/README.md](./tests/README.md). For the testing strategy (what to
automate, recommended cadence, GitHub Actions vs HPC self-hosted runner
trade-offs), see [docs/Testing.md](./docs/Testing.md).

### Writing a new concord, compendium, or data source

See [docs/Architecture.md](./docs/Architecture.md) for an overview of where new code goes,
and [docs/Development.md](./docs/Development.md) for the development workflow.

## Want to work on the frontends instead?

Babel has two frontends: the [Node Normalizer] for exposing information about
cliques, and the [Name Resolver], which lets you search by synonyms or names.
Both of these could use help with issues that are specific to them! Please check
their GitHub repositories to see what improvements they need.

[babel issue tracker]: https://github.com/NCATSTranslator/Babel/issues/
[name resolver]: https://github.com/NCATSTranslator/NameResolution
[node normalizer]: https://github.com/NCATSTranslator/NodeNormalization
