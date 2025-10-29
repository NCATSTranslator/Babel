# Contributing to Babel

We welcome any contributions to Babel! 

## Creating an issue

The easiest way to contribute is to create an issue in our
[GitHub issue tracker](https://github.com/NCATSTranslator/Babel/issues). A good issue describes a problem that you
encountered in the Babel outputs or spotted in the Babel source code, and includes:
* Steps to reproduce or spot the problem (a link to the source code or some Babel output demonstrating the problem
  would be fantastic!).
* The expected or correct output.

A bad issue is better than no issue at all, so don't be shy about submitting one!

## Running Babel locally

The main README file includes instructions on running Babel locally. Note that some Babel pipelines require
a lot of memory and disk space, and will need to be run in on a high-performance computing system.

## Contributing tests

Tests are written using [pytest](https://pytest.org/) and are present in the `tests` directory. You can run
these tests by running `PYTHONPATH=. uv run pytest`.

**Note**: not all tests currently pass! We are [working on that](https://github.com/NCATSTranslator/Babel/issues/602),
and if you can help get them to pass, that would be great!

## Contributing source code

You can contribute source code by forking this repository, creating a new branch, and then submitting a pull request
to our [GitHub repository](https://github.com/NCATSTranslator/Babel).

Code submitted for review should use [ruff](https://docs.astral.sh/ruff/) to fix any style issues before submission.
You can run ruff by running `uv run ruff check`, and you can use `uv run ruff check --fix` to automatically fix some issues.