import os

import duckdb
import pytest

from src.exporters.duckdb_exporters import (
    _bytes_to_gib,
    _parse_cgroup_memory_value,
    _parse_proc_cgroup,
    export_conflation_to_parquet,
    log_duckdb_settings_on_error,
    log_memory_snapshot,
    process_peak_rss_bytes,
)
from tests.conftest import CONFLATION_FIXTURE_ROWS


@pytest.mark.unit
def test_log_duckdb_settings_on_error_reraises_and_logs(caplog):
    """On failure the helper should log the operation name and effective settings, then re-raise."""
    con = duckdb.connect()
    con.execute("SET threads=3")
    with caplog.at_level("INFO"):
        with pytest.raises(duckdb.Error):
            with log_duckdb_settings_on_error(con, "my-test-operation"):
                con.execute("SELECT * FROM a_table_that_does_not_exist")

    assert "my-test-operation" in caplog.text
    assert "effective settings" in caplog.text
    # A couple of the diagnostic settings should be reported back.
    assert "memory_limit=" in caplog.text
    assert "threads=3" in caplog.text
    # The on-error path also emits a memory snapshot for the failed operation.
    assert "Memory snapshot (at failure of my-test-operation)" in caplog.text


@pytest.mark.unit
def test_bytes_to_gib_formats_and_handles_none():
    assert _bytes_to_gib(None) == "unknown"
    assert _bytes_to_gib(0) == "0.0 GiB"
    assert _bytes_to_gib(1024**3) == "1.0 GiB"
    assert _bytes_to_gib(int(1.5 * 1024**3)) == "1.5 GiB"


@pytest.mark.unit
def test_parse_proc_cgroup_resolves_slurm_job_cgroup():
    """The SLURM job cgroup is resolved from /proc/self/cgroup for both cgroup v1 and v2."""
    # cgroup v1: a memory-controller line points under /sys/fs/cgroup/memory.
    v1 = "12:cpuset:/\n7:memory:/slurm/uid_1000/job_1870/step_0\n3:cpu,cpuacct:/slurm\n"
    assert _parse_proc_cgroup(v1) == ["/sys/fs/cgroup/memory/slurm/uid_1000/job_1870/step_0"]

    # cgroup v2: the unified 0:: line points directly under /sys/fs/cgroup.
    v2 = "0::/system.slice/slurmstepd.scope/job_1870/step_0\n"
    assert _parse_proc_cgroup(v2) == ["/sys/fs/cgroup/system.slice/slurmstepd.scope/job_1870/step_0"]

    # No memory controller / malformed lines -> empty, no exception.
    assert _parse_proc_cgroup("9:cpuset:/\ngarbage\n") == []


@pytest.mark.unit
def test_parse_cgroup_memory_value_parses_and_rejects_sentinels():
    """A plain integer is parsed; 'max', empty, and the cgroup-v1 unlimited sentinel become None."""
    assert _parse_cgroup_memory_value("1610612736\n") == 1610612736
    assert _parse_cgroup_memory_value("max\n") is None
    assert _parse_cgroup_memory_value("") is None
    assert _parse_cgroup_memory_value(f"{1 << 63}\n") is None
    assert _parse_cgroup_memory_value("not-a-number") is None


@pytest.mark.unit
def test_process_peak_rss_bytes_is_positive():
    assert process_peak_rss_bytes() > 0


@pytest.mark.unit
def test_log_memory_snapshot_never_raises_with_db_none(caplog):
    """The snapshot must be best-effort: db=None and missing cgroup files must not raise."""
    with caplog.at_level("INFO"):
        log_memory_snapshot(None, "snapshot-test")
    assert "Memory snapshot (snapshot-test)" in caplog.text
    assert "process peak RSS=" in caplog.text


@pytest.mark.unit
def test_log_duckdb_settings_on_error_passes_through_on_success():
    """When the wrapped block succeeds the helper must not interfere with the result."""
    con = duckdb.connect()
    with log_duckdb_settings_on_error(con, "ok-operation"):
        result = con.execute("SELECT 42").fetchone()
    assert result == (42,)


@pytest.mark.unit
def test_export_conflation_to_parquet(geneprotein_conflation_file, tmp_path):
    duckdb_file = str(tmp_path / "conflation.duckdb")
    parquet_file = str(tmp_path / "Conflation.parquet")

    export_conflation_to_parquet(geneprotein_conflation_file, "GeneProtein", duckdb_file, parquet_file)

    assert os.path.exists(parquet_file)

    rows = duckdb.execute(f"SELECT * FROM read_parquet('{parquet_file}') ORDER BY curie").fetchall()

    # Build expected rows from the fixture definition so the test stays in sync.
    expected = sorted(
        [("GeneProtein", group[0], curie, curie.split(":")[0]) for group in CONFLATION_FIXTURE_ROWS for curie in group],
        key=lambda r: r[2],
    )
    assert rows == expected


@pytest.mark.unit
def test_export_conflation_to_parquet_raises_on_existing_duckdb(geneprotein_conflation_file, tmp_path):
    duckdb_file = str(tmp_path / "conflation.duckdb")
    parquet_file = str(tmp_path / "Conflation.parquet")

    # Create the duckdb file so the guard triggers.
    open(duckdb_file, "w").close()

    with pytest.raises(RuntimeError, match="Will not overwrite"):
        export_conflation_to_parquet(geneprotein_conflation_file, "GeneProtein", duckdb_file, parquet_file)


@pytest.mark.unit
def test_export_conflation_conflation_type_stored(geneprotein_conflation_file, tmp_path):
    duckdb_file = str(tmp_path / "conflation.duckdb")
    parquet_file = str(tmp_path / "Conflation.parquet")

    export_conflation_to_parquet(geneprotein_conflation_file, "DrugChemical", duckdb_file, parquet_file)

    types = duckdb.execute(f"SELECT DISTINCT conflation_type FROM read_parquet('{parquet_file}')").fetchall()
    assert types == [("DrugChemical",)]


@pytest.mark.unit
def test_export_conflation_leader_is_first_curie(geneprotein_conflation_file, tmp_path):
    duckdb_file = str(tmp_path / "conflation.duckdb")
    parquet_file = str(tmp_path / "Conflation.parquet")

    export_conflation_to_parquet(geneprotein_conflation_file, "GeneProtein", duckdb_file, parquet_file)

    leaders = set(duckdb.execute(f"SELECT DISTINCT conflation_leader FROM read_parquet('{parquet_file}')").fetchall())
    expected_leaders = {(group[0],) for group in CONFLATION_FIXTURE_ROWS}
    assert leaders == expected_leaders


@pytest.mark.unit
def test_export_conflation_curie_prefix(geneprotein_conflation_file, tmp_path):
    duckdb_file = str(tmp_path / "conflation.duckdb")
    parquet_file = str(tmp_path / "Conflation.parquet")

    export_conflation_to_parquet(geneprotein_conflation_file, "GeneProtein", duckdb_file, parquet_file)

    mismatched = duckdb.execute(
        f"SELECT curie, curie_prefix FROM read_parquet('{parquet_file}') "
        "WHERE split_part(curie, ':', 1) != curie_prefix"
    ).fetchall()
    assert mismatched == [], f"curie_prefix mismatch: {mismatched}"
