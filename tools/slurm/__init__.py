"""SLURM run-analysis tooling for Babel.

A view of a (possibly partial) Snakemake-on-SLURM run:

- ``errors`` — aggregate failing-rule logs into one copy-pasteable report.

The parsing lives in :mod:`tools.slurm.parse`; the subcommands are presentation + CLI.

Run with::

    uv run python -m tools.slurm errors 1.17-try-2 --markdown
"""
