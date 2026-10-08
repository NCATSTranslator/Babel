"""Unit tests for src.tools.slurm.errors."""

import pytest

from src.tools.slurm import errors

pytestmark = pytest.mark.unit


# --- errors.print_job_summary ------------------------------------------------


def test_print_job_summary_buckets_completed_failed_and_incomplete(tmp_path, capsys):
    """The summary splits every task into completed / failed / still-running, and an incomplete
    task that was retried lists its prior failure as an indented sub-line."""
    err = tmp_path / "sbatch-test.err"
    err.write_text(
        # done_rule: submitted and finished -> completed.
        "INFO snakemake.logging [2026-06-04T05:00:00+0000]: "
        "Job 1 has been submitted with SLURM jobid 100 (log: /remote/logs/rule_done_rule/100.log).\n"
        "INFO snakemake.logging [2026-06-04T05:05:00+0000]: Finished jobid: 1 (Rule: done_rule)\n"
        # dead_rule: submitted and errored, never retried -> failed.
        "INFO snakemake.logging [2026-06-04T05:00:00+0000]: "
        "Job 2 has been submitted with SLURM jobid 200 (log: /remote/logs/rule_dead_rule/200.log).\n"
        "ERROR snakemake.logging [2026-06-04T05:06:00+0000]: Error in rule dead_rule, jobid: 2\n"
        # retry_rule: errored once, resubmitted, still running -> incomplete with a prior failure.
        "INFO snakemake.logging [2026-06-04T05:00:00+0000]: "
        "Job 3 has been submitted with SLURM jobid 300 (log: /remote/logs/rule_retry_rule/300.log).\n"
        "ERROR snakemake.logging [2026-06-04T05:07:00+0000]: Error in rule retry_rule, jobid: 3\n"
        "INFO snakemake.logging [2026-06-04T05:08:00+0000]: "
        "Job 3 has been submitted with SLURM jobid 301 (log: /remote/logs/rule_retry_rule/301.log).\n"
    )

    errors.print_job_summary(err, tmp_path)
    out = capsys.readouterr().err

    assert "Found 1 incomplete rule(s):" in out
    assert "Rule retry_rule (SLURM jobid 301)" in out
    assert "Prior failure (SLURM jobid 300)" in out
    assert "Found 1 completed rule(s): done_rule" in out
    assert "Found 1 failed job(s) across 1 rule(s): dead_rule" in out
