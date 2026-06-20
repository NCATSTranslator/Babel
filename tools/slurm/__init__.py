"""SLURM run-analysis tooling for Babel.

Two complementary views of a (possibly partial) Snakemake-on-SLURM run:

- ``errors``    — aggregate failing-rule logs into one copy-pasteable report.
- ``resources`` — compare *actual* resource usage (Snakemake ``benchmark:`` TSVs)
  against *requested* resources (the SLURM efficiency report / per-rule logs) and
  recommend right-sized ``mem`` / ``cpus`` / ``runtime`` per rule.

Why two requested-side sources? On the RENCI Hatteras cluster the built-in SLURM
efficiency report's ``MaxRSS`` and ``TotalCPU`` columns come back empty (the
``jobacct_gather``/cgroup accounting isn't capturing them), so its memory/CPU
*usage* numbers are unusable. The Snakemake ``benchmark:`` TSVs are therefore the
authoritative source for actual usage; the efficiency report is used only for the
*requested* mem/cpus and elapsed wall time. See ``docs/Performance.md``.

Run with::

    uv run python -m tools.slurm resources data/babel-1.17
    uv run python -m tools.slurm errors 1.17-try-2 --markdown
"""
