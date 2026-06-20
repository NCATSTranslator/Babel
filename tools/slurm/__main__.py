"""Dispatch the ``errors`` subcommand.

uv run python -m tools.slurm errors 1.17-try-2 --markdown
"""

from __future__ import annotations

import argparse

from . import errors


def main() -> None:
    parser = argparse.ArgumentParser(prog="tools.slurm", description="Analyze a Babel Snakemake-on-SLURM run.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    errors.add_subparser(subparsers)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
