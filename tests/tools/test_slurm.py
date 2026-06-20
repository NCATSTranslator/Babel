"""Unit tests for the tools.slurm run-analysis package."""

import pytest

from tools.slurm import errors, parse

pytestmark = pytest.mark.unit


# --- parse: error-log extraction (errors subcommand) ------------------------


def test_extract_error_content_shows_full_log_and_real_exception(tmp_path):
    """The whole log is shown, so a RuleException far from the tail (not a Python Traceback,
    not in the last N lines) is never hidden -- this is the 1870.log failure shape."""
    log = (
        "INFO src.exporters.duckdb_exporters: DuckDB memory headroom: "
        "memory_limit=400G, cgroup hard limit (SLURM mem)=512.0 GiB\n"
        + "\n".join(f"filler {i}" for i in range(40))
        + "\nRuleException:\n"
        "OutOfMemoryException in file duckdb.snakefile, line 163:\n"
        "Out of Memory Error: Failed to allocate block of 8650496 bytes (bad allocation)\n"
        + "\n".join(f"snakemake boilerplate {i}" for i in range(80))
    )
    log_path = tmp_path / "1870.log"
    log_path.write_text(log)

    content = parse.extract_error_content(log_path, max_lines=1000)

    # The exception (76+ lines from the end, not a Python Traceback) is present in the full log...
    assert "Failed to allocate block of 8650496 bytes" in content
    assert "filler 0" in content  # ...and so is the top of the log.
    # The memory line appears both inline and in the labelled trailer.
    assert "--- DuckDB memory diagnostics ---" in content
    assert "cgroup hard limit (SLURM mem)=512.0 GiB" in content


def test_extract_error_content_collapses_progress_bar_spam(tmp_path):
    """DuckDB progress-bar redraw lines are collapsed to a single marker, not dumped verbatim."""
    progress = " 58% ▕██████████████████████                ▏ (~9 seconds remaining)"
    log = (
        "starting\n"
        + "\n".join(progress for _ in range(500))
        + "\nMemory snapshot (complete): process peak RSS=66.7 GiB; cgroup current=120.0 GiB\n"
        "done\n"
    )
    log_path = tmp_path / "p.log"
    log_path.write_text(log)

    content = parse.extract_error_content(log_path, max_lines=1000)

    assert "[... DuckDB progress-bar output elided ...]" in content
    assert content.count("seconds remaining") == 0
    assert "starting" in content and "done" in content


def test_extract_error_content_caps_pathologically_long_log(tmp_path):
    """A very long log is capped to a head + tail with an elision marker so the report stays usable."""
    log = "\n".join(f"line {i}" for i in range(5000))
    log_path = tmp_path / "long.log"
    log_path.write_text(log)

    content = parse.extract_error_content(log_path, max_lines=1000)

    assert "log lines elided" in content
    assert "line 0" in content  # head kept
    assert "line 4999" in content  # tail kept


def test_collect_memory_diagnostics_dedupes_and_ignores_settings_dump():
    """Diagnostic markers are collected and de-duplicated; the verbose settings dump is ignored."""
    lines = [
        "INFO ...:  - memory_limit: 1.2 TiB",  # verbose dump, must NOT be collected
        "INFO ...: DuckDB memory headroom: memory_limit=700G, cgroup hard limit (SLURM mem)=1500.0 GiB",
        "INFO ...: DuckDB memory headroom: memory_limit=700G, cgroup hard limit (SLURM mem)=1500.0 GiB",  # dup
        "INFO ...: Memory snapshot (complete): process peak RSS=120.0 GiB; cgroup peak=unknown",
    ]

    found = parse._collect_memory_diagnostics(lines)

    assert len(found) == 2
    assert not any("- memory_limit:" in line for line in found)
    assert any("DuckDB memory headroom" in line for line in found)
    assert any("Memory snapshot (complete)" in line for line in found)


# --- parse.parse_job_events: timeline (errors subcommand summary) ------------


def test_parse_job_events_tracks_retries_and_outcomes(tmp_path):
    err = tmp_path / "sbatch-test.err"
    err.write_text(
        "INFO snakemake.logging [2026-06-04T05:00:00+0000]: "
        "Job 5 has been submitted with SLURM jobid 100 (log: /remote/babel_outputs/logs/rule_get_x/100.log).\n"
        "ERROR snakemake.logging [2026-06-04T05:10:00+0000]: Error in rule get_x, jobid: 5\n"
        "INFO snakemake.logging [2026-06-04T05:11:00+0000]: "
        "Job 5 has been submitted with SLURM jobid 101 (log: /remote/babel_outputs/logs/rule_get_x/101.log).\n"
        "INFO snakemake.logging [2026-06-04T05:20:00+0000]: Finished jobid: 5 (Rule: get_x)\n"
    )
    jobs = parse.parse_job_events(err)
    assert len(jobs) == 2  # the retry does not clobber the first attempt
    first, second = sorted(jobs, key=lambda j: j.slurm_jobid)
    assert first.slurm_jobid == 100 and first.failed is True and first.finished_at is not None
    assert second.slurm_jobid == 101 and second.failed is False and second.finished_at is not None
    assert {j.rule_name for j in jobs} == {"get_x"}


# --- errors.print_job_summary: completed / failed / incomplete bucketing -----


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
    assert "Prior failure (SLURM jobid 300)" in out  # the e70afd0a (group, running) restructure
    assert "Found 1 completed rule(s): done_rule" in out
    assert "Found 1 failed job(s) across 1 rule(s): dead_rule" in out
