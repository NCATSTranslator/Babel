"""Dispatch the ``errors`` and ``resources`` subcommands.

Prefer the installed entry points (``babel-slurm-errors`` /
``babel-slurm-resources``) when the package is installed via ``uv sync``.
The ``python -m`` form is useful when running directly from a clone.
"""

from __future__ import annotations

import argparse

from . import errors, resources


def main() -> None:
    parser = argparse.ArgumentParser(prog="src.tools.slurm", description="Analyze a Babel Snakemake-on-SLURM run.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    errors.add_subparser(subparsers)
    resources.add_subparser(subparsers)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
