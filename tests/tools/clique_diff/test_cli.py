"""Unit tests for the ``babel-clique-diff`` CLI (src/tools/clique_diff/cli.py).

Only the CLI layer — argument handling and the files it writes. The diff itself lives in
``src/model/compendium_diff.py`` and is tested in ``tests/model/test_compendium_diff.py``.
"""

import csv
import json

import pytest

from src.tools.clique_diff.cli import main


def _write_jsonl(path, cliques):
    """Write compendium records as JSONL. Each record's leader is its first CURIE."""
    path.write_text(
        "".join(
            json.dumps({"type": "biolink:Disease", "identifiers": [{"i": c, "l": f"label of {c}"} for c in curies]})
            + "\n"
            for curies in cliques
        )
    )


@pytest.mark.unit
def test_cli_writes_self_describing_summary(tmp_path):
    """main() should wrap the per-compendium summary in an ``about`` block carrying the
    baseline labels, note, and compared files, so the JSON explains its own provenance.
    """
    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    _write_jsonl(bdir / "Disease.txt", [["MONDO:1", "MEDDRA:9"]])
    _write_jsonl(adir / "Disease.txt", [["MONDO:1", "MEDDRA:9"]])
    out_json = tmp_path / "summary.json"
    main(
        [
            "--before",
            str(bdir),
            "--after",
            str(adir),
            "--files",
            "Disease.txt",
            "--out-csv",
            str(tmp_path / "diff.csv"),
            "--out-json",
            str(out_json),
            "--before-label",
            "main (no MP)",
            "--after-label",
            "branch",
            "--note",
            "isolates X",
        ]
    )
    out = json.loads(out_json.read_text())
    assert out["about"] == {
        "before": "main (no MP)",
        "after": "branch",
        "note": "isolates X",
        "files": ["Disease.txt"],
    }
    assert "Disease.txt" in out["compendia"]


@pytest.mark.unit
def test_cli_writes_sorted_csv_with_declared_columns(tmp_path):
    """The change CSV should carry exactly CSV_COLUMNS as its header, one row per
    (changed before-clique, destination) group, sorted deterministically so the file is
    byte-stable when committed.
    """
    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    # Two before-cliques change: MONDO:2 loses a member, MONDO:1 gains a new leader.
    _write_jsonl(bdir / "Disease.txt", [["MONDO:1", "MEDDRA:9"], ["MONDO:2", "UMLS:7"]])
    _write_jsonl(adir / "Disease.txt", [["MEDDRA:9", "MONDO:1"], ["MONDO:2"]])
    out_csv = tmp_path / "diff.csv"
    main(["--before", str(bdir), "--after", str(adir), "--files", "Disease.txt", "--out-csv", str(out_csv)])

    rows = list(csv.DictReader(out_csv.read_text().splitlines()))
    assert rows[0].keys() >= {"compendium", "before_leader", "destination_kind"}
    kinds = {r["before_leader"]: r["destination_kind"] for r in rows if r["destination_kind"] != "kept"}
    assert kinds == {"MONDO:1": "leader_changed", "MONDO:2": "dropped"}
    # Sorted by (compendium, before_leader, destination).
    assert [r["before_leader"] for r in rows] == sorted(r["before_leader"] for r in rows)
    assert "\r" not in out_csv.read_text()  # LF line endings regardless of platform
