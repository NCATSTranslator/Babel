"""Unit test for the babel-inchikey-audit CLI wrapper.

The analysis is tested in tests/model/test_glom_edges.py and tests/model/test_inchikey_audit.py; this covers the
argument handling and the files the CLI writes, over the same miniature ofatumumab build.
"""

import csv
import tempfile

import duckdb
import pytest

from src.tools.inchikey_audit.cli import main
from tests.model.chemical_build_fixture import write_build, write_structure_file
from tests.model.test_inchikey_audit import (
    DIMETHYL_ETHER_INCHI,
    DIMETHYL_ETHER_KEY,
    OFATUMUMAB_CONCORDS,
    OFATUMUMAB_LABELS,
)


def read(path):
    with open(path) as f:
        return list(csv.DictReader(f, delimiter="\t"))


@pytest.mark.unit
def test_cli_writes_components_boundary_refused_and_summary(tmp_path):
    """The CLI should write all four outputs, with the ofatumumab component and its one bad edge in them."""
    members = sorted({c for _, s, o in OFATUMUMAB_CONCORDS for c in (s, o)} | {"RXCUI:712566"})
    build = write_build(
        tmp_path / "build", OFATUMUMAB_CONCORDS, {"CHEBI:28887": ("SmallMolecule", members)}, OFATUMUMAB_LABELS
    )
    structures = write_structure_file(
        tmp_path / "structure.tsv.gz", [("1", DIMETHYL_ETHER_INCHI, DIMETHYL_ETHER_KEY.split(":", 1)[1])]
    )
    out = tmp_path / "out"

    assert main(["--build", str(build), "--structure-file", str(structures), "--out", str(out), "--threads", "1"]) == 0

    components = read(out / "components.tsv")
    assert [(c["clique_leader"], c["tier"], c["verdict"]) for c in components] == [
        ("CHEBI:28887", "A", "likely misattached")
    ]
    boundary = read(out / "boundary_edges.tsv")
    assert [(b["subj"], b["subj_label"], b["obj"], b["obj_label"]) for b in boundary] == [
        ("DrugCentral:4951", "ofatumumab", "PUBCHEM.COMPOUND:8254", "Dimethyl Ether")
    ]
    assert read(out / "refused_edges.tsv") == []
    summary = {(r["kind"], r["category"]): int(r["n"]) for r in read(out / "summary.tsv")}
    assert summary[("glom edge", "applied")] == len(OFATUMUMAB_CONCORDS)
    assert summary[("component tier A", "likely misattached")] == 1


@pytest.mark.unit
def test_cli_refuses_the_repos_badxrefs_file(tmp_path):
    """--badxrefs takes the pairs a build applied; the repo's input_data file may list pairs added since, which would
    hide edges the build applied, so the CLI should refuse it before reading the build."""
    from src.createcompendia.chemicals import CHEMICAL_BAD_XREFS

    with pytest.raises(ValueError, match="applied_badxrefs.txt"):
        main(["--build", str(tmp_path), "--badxrefs", CHEMICAL_BAD_XREFS, "--out", str(tmp_path / "out")])


# SCRATCH AND --keep-duckdb


def _ofatumumab_args(tmp_path, out):
    """CLI arguments for the miniature ofatumumab build, writing to ``out``."""
    members = sorted({c for _, s, o in OFATUMUMAB_CONCORDS for c in (s, o)} | {"RXCUI:712566"})
    build = write_build(
        tmp_path / "build", OFATUMUMAB_CONCORDS, {"CHEBI:28887": ("SmallMolecule", members)}, OFATUMUMAB_LABELS
    )
    structures = write_structure_file(
        tmp_path / "structure.tsv.gz", [("1", DIMETHYL_ETHER_INCHI, DIMETHYL_ETHER_KEY.split(":", 1)[1])]
    )
    return ["--build", str(build), "--structure-file", str(structures), "--out", str(out), "--threads", "1"]


@pytest.mark.unit
def test_cli_writes_only_its_four_tsvs_and_deletes_its_scratch(tmp_path, monkeypatch):
    """A fresh nested --out should be created and hold only the four TSVs; the DuckDB file, its spill and the
    intermediate TSVs should go in a temporary directory that is gone once the run ends."""
    scratch_root = tmp_path / "tmp"
    scratch_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch_root))
    out = tmp_path / "fresh" / "out"

    assert main(_ofatumumab_args(tmp_path, out)) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "boundary_edges.tsv",
        "components.tsv",
        "refused_edges.tsv",
        "summary.tsv",
    ]
    assert list(scratch_root.iterdir()) == []


@pytest.mark.unit
def test_cli_keep_duckdb_keeps_a_queryable_database(tmp_path):
    """--keep-duckdb should leave a DuckDB file holding the per-edge verdicts and the audit tables."""
    kept = tmp_path / "data" / "inchikey_audit" / "fixture.duckdb"

    assert main(_ofatumumab_args(tmp_path, tmp_path / "out") + ["--keep-duckdb", str(kept)]) == 0
    con = duckdb.connect(str(kept), read_only=True)
    assert con.sql("SELECT count(*) FROM glom_edge").fetchone()[0] == len(OFATUMUMAB_CONCORDS)
    assert con.sql("SELECT tier, verdict FROM audit_component").fetchall() == [("A", "likely misattached")]


@pytest.mark.unit
def test_cli_keep_duckdb_refuses_an_existing_file(tmp_path):
    """--keep-duckdb naming an existing file should fail before any work, rather than overwrite a kept audit."""
    kept = tmp_path / "kept.duckdb"
    kept.write_text("an earlier audit")

    with pytest.raises(ValueError, match="already exists"):
        main(["--build", str(tmp_path), "--out", str(tmp_path / "out"), "--keep-duckdb", str(kept)])
    assert kept.read_text() == "an earlier audit"


@pytest.mark.unit
def test_cli_deletes_its_scratch_when_the_run_fails(tmp_path, monkeypatch):
    """A run that fails partway (here, a --build with no parquet files) should still leave no scratch behind."""
    scratch_root = tmp_path / "tmp"
    scratch_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch_root))

    with pytest.raises(duckdb.Error):
        main(["--build", str(tmp_path / "no-such-build"), "--out", str(tmp_path / "out"), "--threads", "1"])
    assert list(scratch_root.iterdir()) == []
