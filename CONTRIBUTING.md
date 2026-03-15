# Contributing to Babel

Babel is open-source software and all contributions are very welcome!

## Reporting bugs

Reporting when you see something wrong with Babel is very helpful, whether you
spot it in the Babel output files or through one of the frontends. Following
these guidelines will help you submit the most useful bug reports and will help
us triage and prioritize them correctly.

1. Most issues should be added to the [Babel issue tracker]: anything to do with
   the content of Babel tools should be reported here, such as anything to do
   with cliques whose identifiers, Biolink type, preferred label, other labels,
   synonyms or descriptions are incorrect. *If you're not sure about which
   repository your issue should go to, please add it to Babel and we'll sort it
   out at our end.*
1. If the issue is specific to the [Node Normalizer] application, such as
   invalid output, an unexpected error message, mishandling input, or something
   that should be changed in the application, please add them to the
   [Node Normalizer issue tracker](https://github.com/NCATSTranslator/NodeNormalization/issues/).
1. Is the issue related to the [Name Resolver] application, such as invalid
   output, an unexpected error message, mishandling input, or search results not
   being ranked correctly? If so, please add them to the
   [Name Resolver issue tracker](https://github.com/NCATSTranslator/NameResolution/issues/).
1. If you've identified several sets of identifiers that need fixing, a
   spreadsheet (preferably TSV/CSV) file or table would also be helpful. We
   would also appreciate if you can include what you expect the tool to return.
   Any other details you can provide, especially anything that will be help us
   replicate the issue, will be very helpful.
1. For guidance on how to assign priority, impact and size fields, group related
   issues, and track when your issue is likely to be addressed, see
   [docs/Triage.md](./docs/Triage.md).

## Contributing source code

For an overview of how Babel's source code is organized — including the two-phase pipeline,
the role of concord files, and the key patterns used throughout the codebase — see
[docs/Architecture.md](./docs/Architecture.md).

For a detailed guide to the development workflow — including how to obtain prerequisites, build
individual compendia, and ideas for making the pipeline easier to work with — see
[docs/Development.md](./docs/Development.md).

We use three linters to check the style of submitted code in GitHub pull
requests -- don't worry if this is difficult to do at your end, as it is easy to
fix in a pull request:

- [ruff](https://docs.astral.sh/ruff/) for Python code
  - You can run this locally by running `uv run ruff check`.
  - You can use `uv run ruff check --fix` to automatically fix some issues.
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

**Note**: not all tests currently pass! We are
[working on that](https://github.com/NCATSTranslator/Babel/issues/602), and if
you can help get them to pass, that would be great!

### Writing a new concord, compendium, or data source

See [docs/Architecture.md](./docs/Architecture.md) for an overview of where new code goes,
and [docs/Development.md](./docs/Development.md) for the development workflow.

## Want to work on the frontends instead?

Babel has two frontends: the [Node Normalizer] for exposing information about
cliques, and the [Name Resolver], which lets you search by synonyms or names.

[babel issue tracker]: https://github.com/NCATSTranslator/Babel/issues/
[name resolver]: https://github.com/NCATSTranslator/NameResolution
[node normalizer]: https://github.com/NCATSTranslator/NodeNormalization
