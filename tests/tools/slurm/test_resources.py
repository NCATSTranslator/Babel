"""Unit tests for src.tools.slurm.resources."""

import pytest

from src.tools.slurm import resources

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


def test_analyze_marks_ran_on_default(tmp_path):
    """A rule requesting the modal (default) mem should be flagged ran_on_default=True; a rule with
    its own explicit request False; a rule with no requested-side data None."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    # Three rules ran on the 64000 MB default, one carries an explicit 500000 MB block, one has no
    # efficiency-report row at all.
    peaks = {
        "on_default_a": (30 * 1024, 64000),
        "on_default_b": (20 * 1024, 64000),
        "on_default_c": (2 * 1024, 64000),
        "has_block": (400 * 1024, 500000),
        "no_data": (25 * 1024, None),
    }
    rows = []
    for rule, (rss, _req) in peaks.items():
        _write_benchmark(bdir / f"{rule}.tsv", [[100.0, "0:01:40", rss, rss, rss, rss, 1, 1, 90.0, 90.0]])
    rep = tmp_path / "reports" / "slurm" / "slurm_efficiency_reports"
    rep.mkdir(parents=True)
    for i, (rule, (_rss, req)) in enumerate(peaks.items()):
        if req is not None:
            rows.append(f"{i},rule_{rule},4,100.0,0.0,,{req}")
    (rep / "efficiency_report_x.csv").write_text(
        ",RuleName,NCPUS,Elapsed_sec,TotalCPU_sec,MaxRSS_MB,RequestedMem_MB\n" + "\n".join(rows) + "\n"
    )
    (tmp_path / "logs").mkdir()

    recs = {r.rule: r for r in resources.analyze(tmp_path, new_default_mem_mb=16 * 1024, new_default_cpus=1)}
    assert resources.detect_run_default_mem_mb(list(recs.values())) == 64000
    assert recs["on_default_a"].ran_on_default is True
    assert recs["on_default_b"].ran_on_default is True
    assert recs["has_block"].ran_on_default is False
    assert recs["no_data"].ran_on_default is None


def test_analyze_handles_missing_efficiency_report(tmp_path):
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    _write_benchmark(bdir / "lonely.tsv", [[5.0, "0:00:05", 100.0, 100.0, 100.0, 100.0, 1, 1, 90.0, 4.0]])
    (tmp_path / "logs").mkdir()
    recs = resources.analyze(tmp_path)
    assert recs[0].classification == "no-request-data"
    assert recs[0].requested_mem_mb is None


# --- runtime fit -------------------------------------------------------------


def test_recommend_runtime_rounds_up_to_bucket():
    # 100 min * 1.5 = 150 min -> next bucket is 180 (3h)
    assert resources.recommend_runtime_min(100 * 60, safety=1.5) == 180
    # 20h * 1.5 = 30h -> next bucket is 36h
    assert resources.recommend_runtime_min(20 * 3600, safety=1.5) == 2160
    # Above the largest bucket, round up to a whole hour.
    assert resources.recommend_runtime_min(60 * 3600, safety=1.5) == 5400


def test_rule_for_benchmark_maps_wildcard_stems_to_their_rule():
    names = ["export_compendia_to_duckdb", "export_compendia_to_duckdb_extra", "chemical"]
    # An exact match wins over any prefix match.
    assert resources.rule_for_benchmark("chemical", names) == "chemical"
    # A wildcard instance resolves to its rule...
    assert resources.rule_for_benchmark("export_compendia_to_duckdb_SmallMolecule", names) == (
        "export_compendia_to_duckdb"
    )
    # ...and the longest matching rule name wins, so a longer sibling rule isn't shadowed.
    assert resources.rule_for_benchmark("export_compendia_to_duckdb_extra_Foo", names) == (
        "export_compendia_to_duckdb_extra"
    )
    # An unknown stem is left alone rather than mis-attributed.
    assert resources.rule_for_benchmark("something_else", names) == "something_else"


def _write_snakefile(tmp_path, body):
    snakefiles = tmp_path / "snakefiles"
    snakefiles.mkdir(exist_ok=True)
    (snakefiles / "test.snakefile").write_text(body)
    return snakefiles


def test_analyze_flags_a_rule_close_to_its_declared_runtime(tmp_path):
    """20h against a declared 24h limit is at-risk; one slow run is a timeout."""
    _make_run(tmp_path, "generate_pubmed_concords", rss_mb=1000.0, mean_load=98.0, requested_mem_mb=128000)
    _write_benchmark(
        tmp_path / "benchmarks" / "generate_pubmed_concords.tsv",
        [[20 * 3600, "20:00:00", 1000.0, 1000.0, 1000.0, 1000.0, 1, 1, 98.0, 90.0]],
    )
    snakefiles = _write_snakefile(
        tmp_path,
        'rule generate_pubmed_concords:\n    resources:\n        runtime="24h",\n        mem="128G",\n    run:\n        x()\n',
    )
    rec = resources.analyze(tmp_path, snakefile_dir=snakefiles)[0]
    assert rec.runtime_limit_min == 1440
    assert rec.time_classification == "at-risk"
    assert rec.rec_runtime_min == 2160  # 20h * 1.5 -> 36h
    assert rec.declared_runtime is True


def test_analyze_only_calls_a_declared_runtime_over_provisioned(tmp_path):
    """A rule on the cluster default is never 'over': that is one decision about the default,
    not a finding about each of ~250 rules that run for seconds."""
    _make_run(tmp_path, "quick_rule", rss_mb=100.0, mean_load=98.0, requested_mem_mb=16000)
    snakefiles = _write_snakefile(tmp_path, "rule quick_rule:\n    run:\n        x()\n")
    rec = resources.analyze(tmp_path, snakefile_dir=snakefiles, default_runtime_min=120)[0]
    assert rec.runtime_limit_min == 120  # inherited from the cluster default
    assert rec.declared_runtime is False
    assert rec.time_classification == "ok"

    # The same rule, now declaring a 6h limit for a 100-second job, IS trimmable.
    snakefiles = _write_snakefile(
        tmp_path, 'rule quick_rule:\n    resources:\n        runtime="6h",\n    run:\n        x()\n'
    )
    rec = resources.analyze(tmp_path, snakefile_dir=snakefiles)[0]
    assert rec.runtime_limit_min == 360
    assert rec.time_classification == "over"
