"""Unit tests for src/utils/duckdb_setup.py: how Babel opens a DuckDB connection and reports its settings on failure."""

import os

import duckdb
import pytest

from src.utils.duckdb_setup import connect_duckdb, log_duckdb_settings_on_error

# CONNECT_DUCKDB


@pytest.fixture
def babel_config(monkeypatch, tmp_path):
    """Replace config.yaml with a small, known config for connect_duckdb(), so a test neither depends on what
    config.yaml's duckdb_config holds nor spills into the checkout's relative tmp_directory."""
    config = {
        "duckdb_config": {"threads": 3, "preserve_insertion_order": False},
        "tmp_directory": str(tmp_path / "tmp"),
    }
    monkeypatch.setattr("src.utils.duckdb_setup.get_config", lambda: config)
    monkeypatch.delenv("BABEL_DUCKDB_TEMP_DIR", raising=False)
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    return config


def _settings(db):
    return dict(db.execute("SELECT name, value FROM duckdb_settings()").fetchall())


@pytest.mark.unit
def test_connect_duckdb_applies_caller_settings_and_spills_per_connection(babel_config, tmp_path):
    """Caller settings should reach the connection, and spills should go to a subdirectory of the requested
    temp_directory made for this connection, even when its path holds a single quote."""
    temp = tmp_path / "gaurav's-builds"
    with connect_duckdb(str(tmp_path / "x.duckdb"), {"threads": 2, "temp_directory": str(temp)}) as db:
        settings = _settings(db)

        assert settings["threads"] == "2"
        assert os.path.dirname(settings["temp_directory"]) == str(temp)
        assert os.path.basename(settings["temp_directory"]).startswith(f"duckdb-{os.getpid()}-")
        assert os.path.isdir(settings["temp_directory"])


@pytest.mark.unit
def test_connect_duckdb_names_the_spill_directory_for_the_slurm_job(babel_config, monkeypatch, tmp_path):
    """On SLURM the spill directory's name should start with the job ID, to trace a leftover directory to its job
    log, and the pid."""
    monkeypatch.setenv("SLURM_JOB_ID", "12345")
    with connect_duckdb(str(tmp_path / "x.duckdb")) as db:
        name = os.path.basename(_settings(db)["temp_directory"])

    assert name.startswith(f"duckdb-12345-{os.getpid()}-")


@pytest.mark.unit
def test_connect_duckdb_gives_each_connection_its_own_spill_directory(babel_config, tmp_path):
    """Two connections open at once in one process should not share a spill directory, since each deletes its own
    on close."""
    with connect_duckdb(str(tmp_path / "a.duckdb")) as a, connect_duckdb(str(tmp_path / "b.duckdb")) as b:
        assert _settings(a)["temp_directory"] != _settings(b)["temp_directory"]


@pytest.mark.unit
def test_connect_duckdb_merges_the_config_yaml_defaults(babel_config, tmp_path):
    """config.yaml's duckdb_config defaults should apply where the caller does not override them."""
    with connect_duckdb(str(tmp_path / "x.duckdb"), {"threads": 1}) as db:
        settings = _settings(db)

    assert settings["threads"] == "1"  # the caller wins
    assert settings["preserve_insertion_order"] == "false"  # the config.yaml default survives
    assert settings["temp_directory"].startswith(babel_config["tmp_directory"])


@pytest.mark.unit
def test_connect_duckdb_accepts_the_real_config_yaml(monkeypatch, tmp_path):
    """Every key in the real config.yaml's duckdb_config should be a setting duckdb.connect() accepts."""
    monkeypatch.setenv("BABEL_DUCKDB_TEMP_DIR", str(tmp_path / "tmp"))
    with connect_duckdb(str(tmp_path / "x.duckdb")):
        pass


@pytest.mark.unit
def test_connect_duckdb_applies_max_temp_directory_size_without_a_spill_directory(babel_config, tmp_path):
    """A caller's spill cap must not be dropped when no temp directory resolves."""
    babel_config["tmp_directory"] = ""
    with connect_duckdb(str(tmp_path / "x.duckdb"), {"max_temp_directory_size": "2TB"}) as db:
        assert _settings(db)["max_temp_directory_size"] == "1.8 TiB"


@pytest.mark.unit
def test_connect_duckdb_closes_and_cleans_up_when_the_block_exits(babel_config, tmp_path):
    """Leaving the block should close the connection and delete its spill directory, leftover files included."""
    with connect_duckdb(str(tmp_path / "x.duckdb")) as db:
        spill_directory = _settings(db)["temp_directory"]
        with open(os.path.join(spill_directory, "leftover.tmp"), "w") as f:
            f.write("spilled")

    assert not os.path.exists(spill_directory)
    with pytest.raises(duckdb.ConnectionException):
        db.execute("SELECT 1")


@pytest.mark.unit
def test_connect_duckdb_closes_and_cleans_up_when_the_block_raises(babel_config, tmp_path):
    """An exception in the block should still close the connection, so the database file can be reopened, and
    delete the spill directory, and then propagate unchanged."""
    path = str(tmp_path / "x.duckdb")
    with pytest.raises(RuntimeError, match="query failed") as excinfo:
        with connect_duckdb(path) as db:
            spill_directory = _settings(db)["temp_directory"]
            raise RuntimeError("query failed")

    # Holding `excinfo` keeps the traceback, and so the generator's frame, alive, as a caller handling the error
    # would; with the connection still open, a connection with a different configuration would be refused.
    duckdb.connect(path, read_only=True).close()
    assert not os.path.exists(spill_directory)
    assert excinfo.value is not None


@pytest.mark.unit
def test_connect_duckdb_closes_the_connection_when_setup_fails(babel_config, tmp_path):
    """A failure after connecting but before the block runs must close the connection and remove the spill
    directory."""
    path = str(tmp_path / "x.duckdb")
    with pytest.raises(duckdb.Error) as excinfo:
        with connect_duckdb(path, {"max_temp_directory_size": "not a size"}):
            pytest.fail("the block should not run when setup fails")

    # With the failed connection still open, a connection with a different configuration would be refused. Holding
    # `excinfo` keeps the traceback -- and so connect_duckdb()'s frame and its connection -- alive, as a caller
    # handling the error would; without it, garbage collection closes the leaked connection and the test can't see
    # the leak.
    duckdb.connect(path, read_only=True).close()
    assert "Memory must have a number" in str(excinfo.value)
    assert os.listdir(babel_config["tmp_directory"]) == []


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


@pytest.mark.unit
def test_log_duckdb_settings_on_error_logs_a_python_memory_error(caplog):
    """An out-of-memory failure raised as Python's MemoryError should be logged like a DuckDB error."""
    con = duckdb.connect()
    with caplog.at_level("INFO"):
        with pytest.raises(MemoryError):
            with log_duckdb_settings_on_error(con, "big-fetch"):
                raise MemoryError()

    assert "DuckDB operation failed during big-fetch (MemoryError" in caplog.text
