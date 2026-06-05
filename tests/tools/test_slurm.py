"""Unit tests for the tools.slurm run-analysis package."""

import pytest

from tools.slurm import parse, resources

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
    rep = tmp_path / "reports" / "slurm" / "slurm_efficiency_report.csv"
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
    rep = tmp_path / "reports" / "slurm" / "slurm_efficiency_report.csv"
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
