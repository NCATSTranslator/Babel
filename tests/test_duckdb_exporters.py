import os

import duckdb
import pytest

from src.exporters.duckdb_exporters import (
    _metadata_subject_filename,
    export_conflation_to_parquet,
    export_intermediates_to_parquet,
)
from tests.conftest import CONFLATION_FIXTURE_ROWS


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


def _build_intermediate_tree(intermediate_dir):
    """Create a small intermediate tree with a concords dir and an ids dir for the
    export_intermediates_to_parquet tests. Returns the directory path."""
    concords_dir = intermediate_dir / "datacollect" / "concords"
    ids_dir = intermediate_dir / "datacollect" / "ids"
    concords_dir.mkdir(parents=True)
    ids_dir.mkdir(parents=True)

    # A concord file, including a value with an embedded double quote to exercise quote handling.
    (concords_dir / "Anatomy.txt").write_text('UBERON:0000001\teq\tMESH:D000001\nUBERON:0000002\teq\tFOO:"bar"\n')
    # A metadata sidecar describing the concord file above, plus a bare directory metadata file.
    (concords_dir / "metadata-Anatomy.txt.yaml").write_text("xref(UBERON, MESH): 2\n")
    (concords_dir / "metadata.yaml").write_text("source: datacollect\n")
    # An empty concord file, which should be skipped.
    (concords_dir / "empty.txt").write_text("")

    # A two-column ids file (curie + biolink type) and a one-column ids file (curie only).
    (ids_dir / "CHEBI").write_text("CHEBI:1\tbiolink:SmallMolecule\nCHEBI:2\tbiolink:SmallMolecule\n")
    (ids_dir / "PLAIN").write_text("PLAIN:1\nPLAIN:2\n")

    return intermediate_dir


@pytest.mark.unit
def test_export_intermediates_to_parquet(tmp_path):
    intermediate_dir = _build_intermediate_tree(tmp_path / "intermediate")
    duckdb_file = str(tmp_path / "concords.duckdb")
    ids_parquet = str(tmp_path / "Identifiers.parquet")
    concords_parquet = str(tmp_path / "Concord.parquet")
    metadata_parquet = str(tmp_path / "Metadata.parquet")

    export_intermediates_to_parquet(str(intermediate_dir), duckdb_file, ids_parquet, concords_parquet, metadata_parquet)

    # Concords: both rows loaded, and the embedded double quote is preserved literally
    # (quote='' on read_csv).
    concords = duckdb.execute(
        f"SELECT subj, pred, obj FROM read_parquet('{concords_parquet}') ORDER BY subj"
    ).fetchall()
    assert concords == [
        ("UBERON:0000001", "eq", "MESH:D000001"),
        ("UBERON:0000002", "eq", 'FOO:"bar"'),
    ]

    # Identifiers: two-column file keeps its Biolink type, one-column file gets NULL.
    identifiers = duckdb.execute(
        f"SELECT curie, biolink_type FROM read_parquet('{ids_parquet}') ORDER BY curie"
    ).fetchall()
    assert identifiers == [
        ("CHEBI:1", "biolink:SmallMolecule"),
        ("CHEBI:2", "biolink:SmallMolecule"),
        ("PLAIN:1", None),
        ("PLAIN:2", None),
    ]

    # Metadata: the sidecar describing Anatomy.txt resolves its subject filename, and the bare
    # metadata.yaml keeps its own name as the subject.
    metadata = dict(
        duckdb.execute(f"SELECT subject_filename, metadata_json FROM read_parquet('{metadata_parquet}')").fetchall()
    )
    assert metadata["Anatomy.txt"].strip() == "xref(UBERON, MESH): 2"
    assert metadata["metadata.yaml"].strip() == "source: datacollect"


@pytest.mark.unit
def test_export_intermediates_to_parquet_empty_tree(tmp_path):
    # An intermediate directory with no concords/ or ids/ subdirectories must not raise
    # (regression test: a trailing `del concord_path` used to NameError on an empty glob).
    intermediate_dir = tmp_path / "intermediate"
    intermediate_dir.mkdir()
    duckdb_file = str(tmp_path / "concords.duckdb")
    ids_parquet = str(tmp_path / "Identifiers.parquet")
    concords_parquet = str(tmp_path / "Concord.parquet")
    metadata_parquet = str(tmp_path / "Metadata.parquet")

    export_intermediates_to_parquet(str(intermediate_dir), duckdb_file, ids_parquet, concords_parquet, metadata_parquet)

    for parquet_file in (ids_parquet, concords_parquet, metadata_parquet):
        count = duckdb.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_file}')").fetchone()[0]
        assert count == 0


@pytest.mark.unit
def test_export_intermediates_to_parquet_raises_on_existing_duckdb(tmp_path):
    intermediate_dir = _build_intermediate_tree(tmp_path / "intermediate")
    duckdb_file = str(tmp_path / "concords.duckdb")
    open(duckdb_file, "w").close()

    with pytest.raises(RuntimeError, match="Will not overwrite"):
        export_intermediates_to_parquet(
            str(intermediate_dir),
            duckdb_file,
            str(tmp_path / "Identifiers.parquet"),
            str(tmp_path / "Concord.parquet"),
            str(tmp_path / "Metadata.parquet"),
        )


@pytest.mark.unit
def test_export_intermediates_to_parquet_inconsistent_columns(tmp_path):
    intermediate_dir = tmp_path / "intermediate"
    ids_dir = intermediate_dir / "ids"
    ids_dir.mkdir(parents=True)
    # First line has one column, second line has two: this must be rejected.
    (ids_dir / "BAD").write_text("BAD:1\nBAD:2\tbiolink:SmallMolecule\n")

    with pytest.raises(RuntimeError, match="Inconsistent number of columns"):
        export_intermediates_to_parquet(
            str(intermediate_dir),
            str(tmp_path / "concords.duckdb"),
            str(tmp_path / "Identifiers.parquet"),
            str(tmp_path / "Concord.parquet"),
            str(tmp_path / "Metadata.parquet"),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "filename,expected",
    [
        ("metadata-Anatomy.txt.yaml", "Anatomy.txt"),
        ("metadata.yaml", "metadata.yaml"),
        ("Anatomy.txt", None),
        ("CHEBI", None),
    ],
)
def test_metadata_subject_filename(filename, expected):
    assert _metadata_subject_filename(filename) == expected
