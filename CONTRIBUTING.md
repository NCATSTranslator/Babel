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
1. After you have reported a bug, helping to triage, prioritize and group it
   will be very helpful:
   - We triage issues into one of the
     [milestones](https://github.com/NCATSTranslator/Babel/milestones):
     - [Needs investigation](https://github.com/NCATSTranslator/Babel/milestone/12)
       refers to issues that need to be investigated further -- either to figure
       out what is causing the issue or to communicate with the user community
       to understand what should occur.
     - [Immediate](https://github.com/NCATSTranslator/Babel/milestone/35) need
       to be fixed immediately. Issues I'm currently working on will be placed
       here.
     - [Needed soon](https://github.com/NCATSTranslator/Babel/milestone/30)
       refers to issues that should be fixed in the next few months: not
       immediately, but sooner rather than later.
     - [Needed later](https://github.com/NCATSTranslator/Babel/milestone/31)
       refers to issues that should be fixed eventually, but are not needed
       immediately.
   - We prioritize issues with one of the three priority tags:
     [Priority: Low](https://github.com/NCATSTranslator/Babel/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22Priority%3A%20Low%22),
     [Priority: Medium](https://github.com/NCATSTranslator/Babel/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22Priority%3A%20Medium%22),
     [Priority: High](https://github.com/NCATSTranslator/Babel/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22Priority%3A%20High%22).
     The idea is that issues with the highest priority will determine which will
     be investigated/tested first, and which are most likely to move from Needed
     later/Needed soon into Immediate for working on.
   - We estimate effort on tasks using a series of
     ["T-shirt sizes"](https://asana.com/resources/t-shirt-sizing):
     [Size: XS](https://github.com/NCATSTranslator/Babel/issues?q=state%3Aopen%20label%3A%22Size%3A%20XS%22),
     [Size: S](https://github.com/NCATSTranslator/Babel/issues?q=state%3Aopen%20label%3A%22Size%3A%20S%22),
     [Size: M](https://github.com/NCATSTranslator/Babel/issues?q=state%3Aopen%20label%3A%22Size%3A%20M%22),
     [Size: L](https://github.com/NCATSTranslator/Babel/issues?q=state%3Aopen%20label%3A%22Size%3A%20L%22),
     [Size: XL](https://github.com/NCATSTranslator/Babel/issues?q=state%3Aopen%20label%3A%22Size%3A%20XL%22).
     These are to help distinguish between tasks that are easy to complete
     (extra small) and those that will require a lot of thinking, programming
     and testing (extra large).
   - You can group issues in two ways:
     - GitHub lets you chose a "parent" issue for each issue, which is useful
       for issues that are related to each other. We try to build "issues of
       issues" that group together similar issues that might require similar
       fixes (e.g.
       [our issue tracking deprecated identifiers](https://github.com/NCATSTranslator/Babel/issues/93)).
       If you find an issue related to yours, please feel free to add yours as a
       child of the existing issue or vice versa.
     - You can use labels to group similar issues. We don't have a lot of labels
       for you to choose from, but feel free to add any that make sense!

## Contributing source code

Babel is structured around its [Snakemake files](./src/snakefiles), which call
into its [data handlers](./src/datahandlers) and
[compendia creators](./src/createcompendia). The heart of its data are its
concord files, which contain cross-references between different databases. These
are combined into compendium files and synonyms.

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
- [pymarkdownlnt](https://pypi.org/project/pymarkdownlnt/) for Markdown files
  - You can run this locally by running `uv run pymarkdownlnt scan .`.
  - You can use `uv run pymarkdownlnt fix .` to automatically fix some issues.

### Contributing tests

TODO

Tests are written using [pytest](https://pytest.org/) and are present in the
`tests` directory. You can run these tests by running
`PYTHONPATH=. uv run pytest`.

**Note**: not all tests currently pass! We are
[working on that](https://github.com/NCATSTranslator/Babel/issues/602), and if
you can help get them to pass, that would be great!

### Writing a new concord or compendium

TODO

### Adding a new source of identifiers, synonyms or descriptions

TODO

## Want to work on the frontends instead?

Babel has two frontends: the [Node Normalizer] for exposing information about
cliques, and the [Name Resolver], which lets you search by synonyms or names.

-
-
-

[babel issue tracker]: https://github.com/NCATSTranslator/Babel/issues/
[name resolver]: https://github.com/NCATSTranslator/NameResolution
[node normalizer]: https://github.com/NCATSTranslator/NodeNormalization
