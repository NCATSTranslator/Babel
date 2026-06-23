"""Unit tests for tools.slurm.resources."""

import pytest

from tools.slurm import resources

pytestmark = pytest.mark.unit


def _write_benchmark(path, rows):
    header = "s\th:m:s\tmax_rss\tmax_vms\tmax_uss\tmax_pss\tio_in\tio_out\tmean_load\tcpu_time"
    lines = [header] + ["\t".join(str(c) for c in r) for r in rows]
    path.write_text("\n".join(lines) + "\n")


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
