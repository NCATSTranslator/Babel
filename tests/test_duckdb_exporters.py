import os

import duckdb
import pytest

from src.exporters.duckdb_exporters import export_conflation_to_parquet, log_duckdb_settings_on_error
from tests.conftest import CONFLATION_FIXTURE_ROWS


@pytest.mark.unit
def test_log_duckdb_settings_on_error_reraises_and_logs(caplog):
    """On failure the helper should log the operation name and effective settings, then re-raise."""
    con = duckdb.connect()
    con.execute("SET threads=3")
    with caplog.at_level("ERROR"):
        with pytest.raises(duckdb.Error):
            with log_duckdb_settings_on_error(con, "my-test-operation"):
                con.execute("SELECT * FROM a_table_that_does_not_exist")

    assert "my-test-operation" in caplog.text
    assert "effective settings" in caplog.text
    # A couple of the diagnostic settings should be reported back.
    assert "memory_limit=" in caplog.text
    assert "threads=3" in caplog.text


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
