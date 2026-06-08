"""Regression tests for the cross-compendium DuckDB report queries.

These exercise the two-pass duplicate-detection rewrite in
``src/reports/duckdb_reports.py``: a spillable ``COUNT(*)`` pass that finds the
duplicate keys, followed by a ``LIST()`` pass restricted to those keys. The
fixtures are deliberately tiny; the point is to confirm the SQL is valid and that
duplicates (and only duplicates) are reported, not to reproduce the scale that
caused the original out-of-memory failures.
"""

import csv
import json

import duckdb
import pytest

import src.reports.duckdb_reports as duckdb_reports


def _write_parquet(con, path, columns, rows):
    """Write ``rows`` to a Parquet file at ``path`` with the given column names."""
    con.execute(f"CREATE OR REPLACE TABLE t({', '.join(f'{c} VARCHAR' for c in columns)})")
    if rows:
        placeholders = ", ".join(["(" + ", ".join(["?"] * len(columns)) + ")"] * len(rows))
        flat = [value for row in rows for value in row]
        con.execute(f"INSERT INTO t VALUES {placeholders}", flat)
    con.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")


@pytest.fixture
def parquet_root(tmp_path):
    """Build a hive-partitioned Parquet tree (filename=<X>/Clique.parquet, Edge.parquet).

    ``filename`` is supplied by the hive partition directory, so it is intentionally
    absent from the Parquet columns.
    """
    con = duckdb.connect()

    # Clique columns consumed by the report queries (filename comes from the partition dir).
    clique_cols = ["clique_leader", "preferred_name", "biolink_type", "clique_identifier_count"]
    foo_dir = tmp_path / "filename=Foo"
    bar_dir = tmp_path / "filename=Bar"
    foo_dir.mkdir()
    bar_dir.mkdir()

    _write_parquet(
        con,
        str(foo_dir / "Clique.parquet"),
        clique_cols,
        [
            ("A", "Water", "biolink:SmallMolecule", "3"),
            ("B", "Caffeine", "biolink:SmallMolecule", "2"),
        ],
    )
    _write_parquet(
        con,
        str(bar_dir / "Clique.parquet"),
        clique_cols,
        [
            # "A" duplicates the leader in Foo; "C" shares the lowercased name "water".
            ("A", "Water", "biolink:ChemicalEntity", "4"),
            ("C", "water", "biolink:Drug", "1"),
        ],
    )

    edge_cols = ["curie", "clique_leader", "conflation", "curie_prefix", "clique_leader_prefix"]
    _write_parquet(
        con,
        str(foo_dir / "Edge.parquet"),
        edge_cols,
        [
            ("CHEBI:1", "A", "None", "CHEBI", "CHEBI"),
            ("MESH:1", "A", "None", "MESH", "CHEBI"),
            # conflation != 'None' rows must be ignored by every report.
            ("DRUGBANK:1", "A", "DrugChemical", "DRUGBANK", "CHEBI"),
        ],
    )
    _write_parquet(
        con,
        str(bar_dir / "Edge.parquet"),
        edge_cols,
        [
            ("CHEBI:1", "A", "None", "CHEBI", "CHEBI"),  # duplicate CURIE across Foo/Bar
            ("MESH:1", "C", "None", "MESH", "NCBIGene"),  # duplicate CURIE in a different clique
        ],
    )
    con.close()

    return str(tmp_path) + "/"


def _read_tsv(path):
    with open(path) as f:
        return list(csv.reader(f, delimiter="\t"))


@pytest.mark.unit
def test_check_for_identically_labeled_cliques(parquet_root, tmp_path):
    out = str(tmp_path / "identically_labeled.tsv")
    duckdb_reports.check_for_identically_labeled_cliques(parquet_root, str(tmp_path / "db.duckdb"), out)

    rows = _read_tsv(out)
    header, data = rows[0], rows[1:]
    assert header == ["preferred_name_lc", "clique_leader_count", "clique_leader"]

    # The report now emits one row per (name, clique_leader) pair. "water" (case-folded) is the
    # only duplicated name: it is shared by clique A (in both Foo and Bar) and clique C (Bar), so
    # three Clique rows match -> three output rows, all with clique_leader_count 3. "caffeine" is
    # unique and must not appear.
    assert {r[0] for r in data} == {"water"}
    assert all(r[1] == "3" for r in data)
    assert sorted(r[2] for r in data) == ["A", "A", "C"]


@pytest.mark.unit
def test_check_for_duplicate_curies(parquet_root, tmp_path):
    out = str(tmp_path / "duplicate_curies.tsv")
    duckdb_reports.check_for_duplicate_curies(parquet_root, str(tmp_path / "db.duckdb"), out)

    rows = _read_tsv(out)
    header, data = rows[0], rows[1:]
    by_curie = {r[0]: dict(zip(header, r)) for r in data}

    # Both CHEBI:1 and MESH:1 appear in two cliques; the conflated DRUGBANK:1 row is ignored.
    assert set(by_curie) == {"CHEBI:1", "MESH:1"}
    assert by_curie["CHEBI:1"]["clique_leader_count"] == "2"
    assert by_curie["MESH:1"]["clique_leader_count"] == "2"
    assert "DRUGBANK:1" not in by_curie


@pytest.mark.unit
def test_check_for_duplicate_clique_leaders(parquet_root, tmp_path):
    out = str(tmp_path / "duplicate_clique_leaders.tsv")
    duckdb_reports.check_for_duplicate_clique_leaders(parquet_root, str(tmp_path / "db.duckdb"), out)

    rows = _read_tsv(out)
    header, data = rows[0], rows[1:]
    by_leader = {r[0]: dict(zip(header, r)) for r in data}

    # Only "A" leads a clique in both Foo and Bar.
    assert set(by_leader) == {"A"}
    row = by_leader["A"]
    assert row["clique_leader_count"] == "2"
    # The two-pass rewrite restores these columns; both files' values must be present.
    assert "biolink:ChemicalEntity" in row["biolink_types"]
    assert "biolink:SmallMolecule" in row["biolink_types"]
    assert "Foo" in row["filenames"] and "Bar" in row["filenames"]


@pytest.mark.unit
def test_generate_curie_report_totals(parquet_root, tmp_path):
    """The spillable SELECT DISTINCT + COUNT(*) rewrite must reproduce the COUNT(DISTINCT) math.

    Over the conflation='None' edges, CHEBI:1 appears once (in clique A, twice across files) and
    MESH:1 appears in cliques A and C, so the per-prefix totals are exact and easy to check.
    """
    out = str(tmp_path / "curie_report.json")
    duckdb_reports.generate_curie_report(parquet_root, str(tmp_path / "db.duckdb"), out)

    with open(out) as f:
        report = json.load(f)

    # curie_count counts every edge; *_distinct_count de-duplicates curie / clique_leader.
    assert report["CHEBI"]["_totals"] == {
        "curie_count": 2,
        "curie_distinct_count": 1,
        "clique_distinct_count": 1,
    }
    assert report["MESH"]["_totals"] == {
        "curie_count": 2,
        "curie_distinct_count": 1,
        "clique_distinct_count": 2,
    }


@pytest.mark.unit
def test_generate_clique_leaders_report_totals(parquet_root, tmp_path):
    """The per-filename totals must match a direct COUNT(DISTINCT) over the fixture edges."""
    out = str(tmp_path / "clique_leaders.json")
    duckdb_reports.generate_clique_leaders_report(parquet_root, str(tmp_path / "db.duckdb"), out)

    with open(out) as f:
        report = json.load(f)

    # Foo's two None-edges sit in one clique (A); Bar's two span cliques A and C.
    assert report["Foo"]["_totals"] == {
        "distinct_clique_count": 1,
        "distinct_curie_count": 2,
        "curie_count": 2,
    }
    assert report["Bar"]["_totals"] == {
        "distinct_clique_count": 2,
        "distinct_curie_count": 2,
        "curie_count": 2,
    }
