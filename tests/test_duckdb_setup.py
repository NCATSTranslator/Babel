"""Unit tests for src/duckdb_setup.py: how Babel opens a DuckDB connection and reports its settings on failure."""

import os

import duckdb
import pytest

from src.duckdb_setup import log_duckdb_settings_on_error, setup_duckdb

# SETUP_DUCKDB


@pytest.mark.unit
def test_setup_duckdb_applies_caller_settings_and_spills_per_job(tmp_path):
    """Caller settings should reach the connection, and spills should go to a per-job subdirectory of the requested
    temp_directory, even when its path holds a single quote."""
    temp = tmp_path / "gaurav's-builds"
    db = setup_duckdb(str(tmp_path / "x.duckdb"), {"threads": 2, "temp_directory": str(temp)})
    settings = dict(db.execute("SELECT name, value FROM duckdb_settings()").fetchall())

    assert settings["threads"] == "2"
    assert settings["temp_directory"] == str(temp / f"duckdb-{os.environ.get('SLURM_JOB_ID') or os.getpid()}")
    assert os.path.isdir(settings["temp_directory"])


@pytest.mark.unit
def test_setup_duckdb_merges_the_config_yaml_defaults(tmp_path):
    """config.yaml's duckdb_config defaults should apply when the caller does not override them."""
    from src.util import get_config

    db = setup_duckdb(str(tmp_path / "x.duckdb"), {"threads": 1})
    settings = dict(db.execute("SELECT name, value FROM duckdb_settings()").fetchall())

    for name, value in get_config()["duckdb_config"].items():
        assert settings[name].lower() == str(value).lower(), name


# LOG_DUCKDB_SETTINGS_ON_ERROR


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
def test_log_duckdb_settings_on_error_passes_through_on_success():
    """When the wrapped block succeeds the helper must not interfere with the result."""
    con = duckdb.connect()
    with log_duckdb_settings_on_error(con, "ok-operation"):
        result = con.execute("SELECT 42").fetchone()
    assert result == (42,)
