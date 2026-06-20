"""Unit tests for the tools.slurm run-analysis package."""

import os

import pytest

from tools.slurm import errors, parse, resources

pytestmark = pytest.mark.unit


# --- parse.read_benchmarks ---------------------------------------------------


def _write_benchmark(path, rows):
    header = "s\th:m:s\tmax_rss\tmax_vms\tmax_uss\tmax_pss\tio_in\tio_out\tmean_load\tcpu_time"
    lines = [header] + ["\t".join(str(c) for c in r) for r in rows]
    path.write_text("\n".join(lines) + "\n")


def test_read_benchmarks_takes_worst_case_across_rows(tmp_path):
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    # two attempts; reader should keep the per-column maximum
    _write_benchmark(
        bdir / "my_rule.tsv",
        [
            [10.0, "0:00:10", 100.0, 200.0, 90.0, 95.0, 1.0, 2.0, 95.0, 9.0],
            [20.0, "0:00:20", 300.0, 400.0, 280.0, 290.0, 3.0, 4.0, 190.0, 38.0],
        ],
    )
    benches = parse.read_benchmarks(bdir)
    assert set(benches) == {"my_rule"}
    b = benches["my_rule"]
    assert b.seconds == 20.0
    assert b.max_rss_mb == 300.0
    assert b.mean_load == 190.0
    assert b.cores_used == pytest.approx(1.9)


def test_read_benchmarks_tolerates_missing_cells(tmp_path):
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    _write_benchmark(bdir / "r.tsv", [[5.0, "0:00:05", 50.0, 60.0, 40.0, 45.0, "-", "NA", 90.0, 4.0]])
    b = parse.read_benchmarks(bdir)["r"]
    assert b.io_in == 0.0 and b.io_out == 0.0


# --- parse.read_efficiency_report --------------------------------------------


def test_read_efficiency_report_from_directory_and_strips_rule_prefix(tmp_path):
    # SLURM writes the report as a *directory* of efficiency_report_*.csv files.
    rep = tmp_path / "reports" / "slurm" / "slurm_efficiency_reports"
    rep.mkdir(parents=True)
    (rep / "efficiency_report_abc.csv").write_text(
        ",JobID,JobName,RuleName,Elapsed,TotalCPU,NNodes,NCPUS,MaxRSS,ReqMem,"
        "Elapsed_sec,TotalCPU_sec,MaxRSS_MB,RequestedMem_MB,MainJobID,CPU Efficiency (%),Memory Usage (%)\n"
        "3,427.0,python,rule_taxon_compendia,00:05:00,00:00:00,1,4,,,300.0,NA,,64000.0,427,0.0,0.0\n"
    )
    eff = parse.read_efficiency_report(tmp_path / "reports" / "slurm")
    assert "taxon_compendia" in eff
    row = eff["taxon_compendia"]
    assert row.requested_mem_mb == 64000.0
    assert row.ncpus == 4
    # accounting gap: MaxRSS / TotalCPU come back empty -> 0
    assert row.max_rss_mb == 0.0
    assert row.total_cpu_sec == 0.0


# --- parse.read_rule_logs ----------------------------------------------------


def test_read_rule_logs_parses_resources_and_failure(tmp_path):
    logs = tmp_path / "logs"
    rdir = logs / "rule_anatomy_ncit_ids"
    rdir.mkdir(parents=True)
    (rdir / "451.log").write_text(
        "[Thu Jun  4 05:15:08 2026]\n"
        "rule anatomy_ncit_ids:\n"
        "    resources: tmpdir=<TBD>, disk_mb=50000, mem_mb=64000, mem=64 GB, runtime=120, cpus_per_task=4\n"
        "RuleException:\n"
        "HTTP Error 503: Service Temporarily Unavailable\n"
        "[Thu Jun  4 05:15:26 2026]\n"
    )
    out = parse.read_rule_logs(logs)
    assert "anatomy_ncit_ids" in out
    log = out["anatomy_ncit_ids"]
    assert (log.mem_mb, log.runtime_min, log.cpus) == (64000, 120, 4)
    assert log.failed is True
    assert log.start is not None and log.end is not None and log.end > log.start


# --- resources recommendation logic ------------------------------------------


def test_recommend_mem_rounds_up_to_bucket_with_floor():
    # 0.5 GB * 1.5 = 0.75 GB, floored to the 8 GB minimum
    assert resources.recommend_mem_mb(512, safety=1.5, floor_mb=8192) == 8192
    # 14 GB * 1.5 = 21 GB -> next bucket is 24 GB
    assert resources.recommend_mem_mb(14 * 1024, safety=1.5, floor_mb=8192) == 24 * 1024
    # 41 GB * 1.5 = 61.5 GB -> next bucket is 64 GB
    assert resources.recommend_mem_mb(41 * 1024, safety=1.5, floor_mb=8192) == 64 * 1024


def test_recommend_cpus_rounds_up():
    assert resources.recommend_cpus(0.95) == 1
    assert resources.recommend_cpus(1.0) == 1
    assert resources.recommend_cpus(2.3) == 3


def _make_run(tmp_path, rule, rss_mb, mean_load, requested_mem_mb):
    bdir = tmp_path / "benchmarks"
    bdir.mkdir(exist_ok=True)
    _write_benchmark(bdir / f"{rule}.tsv", [[100.0, "0:01:40", rss_mb, rss_mb, rss_mb, rss_mb, 1, 1, mean_load, 90.0]])
    rep = tmp_path / "reports" / "slurm" / "slurm_efficiency_reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "efficiency_report_x.csv").write_text(
        ",RuleName,NCPUS,Elapsed_sec,TotalCPU_sec,MaxRSS_MB,RequestedMem_MB\n"
        f"0,rule_{rule},4,100.0,0.0,,{requested_mem_mb}\n"
    )
    (tmp_path / "logs").mkdir(exist_ok=True)


def test_analyze_flags_rule_needing_override(tmp_path):
    # 41 GB peak on a 16 GB proposed default -> must be flagged for an explicit override.
    _make_run(tmp_path, "get_uniprotkb_labels", rss_mb=41 * 1024, mean_load=70.0, requested_mem_mb=64000)
    recs = resources.analyze(tmp_path, new_default_mem_mb=16 * 1024, new_default_cpus=1)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.rule == "get_uniprotkb_labels"
    assert rec.rec_mem_mb == 64 * 1024
    assert rec.needs_override is True


def test_analyze_classifies_over_provisioned_and_fits_default(tmp_path):
    # 0.2 GB peak with a 64 GB request -> heavily over-provisioned, no override needed.
    _make_run(tmp_path, "tiny_rule", rss_mb=200.0, mean_load=98.0, requested_mem_mb=64000)
    rec = resources.analyze(tmp_path, new_default_mem_mb=16 * 1024, new_default_cpus=1)[0]
    assert rec.classification == "over"
    assert rec.needs_override is False
    assert rec.rec_mem_mb == 8 * 1024


def test_analyze_handles_missing_efficiency_report(tmp_path):
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    _write_benchmark(bdir / "lonely.tsv", [[5.0, "0:00:05", 100.0, 100.0, 100.0, 100.0, 1, 1, 90.0, 4.0]])
    (tmp_path / "logs").mkdir()
    recs = resources.analyze(tmp_path)
    assert recs[0].classification == "no-request-data"
    assert recs[0].requested_mem_mb is None


# --- parse.read_efficiency_report: multi-shard aggregation -------------------


def test_read_efficiency_report_merges_all_shards_worst_case(tmp_path):
    # A real run leaves one efficiency_report_<uuid>.csv per Snakemake (re)start; each shard only
    # covers that invocation's jobs. Reading just the newest (as an earlier version did) would drop
    # almost every rule -- so all shards must be merged.
    rep = tmp_path / "reports" / "slurm" / "slurm_efficiency_reports"
    rep.mkdir(parents=True)
    header = ",RuleName,NCPUS,Elapsed_sec,TotalCPU_sec,MaxRSS_MB,RequestedMem_MB\n"
    # Older, larger shard with two rules.
    (rep / "efficiency_report_aaa.csv").write_text(
        header + "0,rule_alpha,1,100.0,0.0,,16000\n0,rule_beta,2,200.0,0.0,,32000\n"
    )
    # Newest shard re-ran only alpha, with a larger reservation.
    newest = rep / "efficiency_report_zzz.csv"
    newest.write_text(header + "0,rule_alpha,4,150.0,0.0,,64000\n")
    os.utime(newest, (10**10, 10**10))  # make it unambiguously newest

    eff = parse.read_efficiency_report(tmp_path / "reports" / "slurm")
    # beta survives even though it is absent from the newest shard.
    assert set(eff) == {"alpha", "beta"}
    assert eff["beta"].requested_mem_mb == 32000
    # alpha keeps the worst-case (largest) reservation across shards.
    assert eff["alpha"].requested_mem_mb == 64000
    assert eff["alpha"].ncpus == 4


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
