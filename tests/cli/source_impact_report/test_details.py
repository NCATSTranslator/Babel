"""Unit tests for the source-impact detail files (CSV/JSON/TSV).

Drives the real ``src.cli.source_impact_report.main`` over a synthetic intermediate root
(offline, so ``unit``-marked) and asserts the four detail files written into the report's
``<output-stem>/`` subdirectory are correct, complete, and deterministic.

The synthetic source ``NEWSOURCE`` is arranged against an ``EXISTING`` Babel set to yield:
two pure-new singleton cliques, one expanded clique (a structurally-new member), and one
merged clique — so every detail file has content to assert on.
"""

import csv
import json

import pytest

from src.cli.source_impact_report import main


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def synthetic_intermediate(tmp_path):
    anatomy = tmp_path / "intermediate" / "anatomy"
    _write(
        anatomy / "ids" / "EXISTING",
        "UBERON:0001\tbiolink:AnatomicalEntity\n"
        "UBERON:0002\tbiolink:AnatomicalEntity\n"
        "GO:0000003\tbiolink:CellularComponent\n"
        "UBERON:0010\tbiolink:AnatomicalEntity\n",
    )
    _write(
        anatomy / "ids" / "NEWSOURCE",
        "NEWSRC:1\tbiolink:AnatomicalEntity\n"
        "NEWSRC:2\tbiolink:AnatomicalEntity\n"
        "NEWSRC:3\tbiolink:AnatomicalEntity\n"
        "NEWSRC:4\tbiolink:GrossAnatomicalStructure\n",
    )
    _write(
        anatomy / "concords" / "NEWSOURCE",
        "NEWSRC:2\txref\tUBERON:0001\nNEWSRC:3\txref\tUBERON:0002\nNEWSRC:3\txref\tGO:0000003\n",
    )
    return {"intermediate_root": tmp_path / "intermediate", "source": "NEWSOURCE"}


def _run(synthetic_intermediate, output, extra=()):
    return main(
        [
            "--source",
            synthetic_intermediate["source"],
            "--mode",
            "synthetic",
            "--intermediate-root",
            str(synthetic_intermediate["intermediate_root"]),
            "--output",
            str(output),
            "--format",
            "md",
            "--no-biolink-lookup",  # keep the test fully offline
            *extra,
        ]
    )


def _read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


@pytest.mark.unit
def test_detail_files_written_with_expected_content(synthetic_intermediate, tmp_path):
    output = tmp_path / "impact-report.md"
    assert _run(synthetic_intermediate, output) == 0

    details = tmp_path / "impact-report"
    assert details.is_dir()

    # new-cliques.csv — the two pure-new singletons (NEWSRC:1, NEWSRC:4).
    new_cliques = _read_csv(details / "new-cliques.csv")
    ids = {r["preferred_id"] for r in new_cliques}
    assert ids == {"NEWSRC:1", "NEWSRC:4"}
    assert all(r["member_count"] == "1" for r in new_cliques)

    # modified-cliques.csv — one row per added/promoted identifier. The expanded clique
    # gains NEWSRC:2 and the merge is bridged by NEWSRC:3, both structurally new.
    modified = _read_csv(details / "modified-cliques.csv")
    added = {r["added_id"] for r in modified if r["added_kind"] == "added"}
    assert added == {"NEWSRC:2", "NEWSRC:3"}
    change_kinds = {r["added_id"]: r["change_kind"] for r in modified}
    assert change_kinds["NEWSRC:2"] == "expanded"
    assert change_kinds["NEWSRC:3"] == "merged"

    # modified-cliques.json — full structure for the expanded + merged clique.
    entries = json.loads((details / "modified-cliques.json").read_text())
    assert {e["change_kind"] for e in entries} == {"expanded", "merged"}
    merged_entry = next(e for e in entries if e["change_kind"] == "merged")
    assert sorted(merged_entry["before_clique_leaders"]) == ["GO:0000003", "UBERON:0002"]
    assert "NEWSRC:3" in merged_entry["added_source_curies"]

    # new-xrefs.tsv — the three rows from NEWSOURCE's own concord, all "added".
    with (details / "new-xrefs.tsv").open() as f:
        xrefs = list(csv.DictReader(f, delimiter="\t"))
    assert len(xrefs) == 3
    assert all(r["asserted_by"] == "NEWSOURCE" for r in xrefs)
    assert all(r["status"] == "added" for r in xrefs)


@pytest.mark.unit
def test_detail_files_are_deterministic(synthetic_intermediate, tmp_path):
    out_a = tmp_path / "a" / "impact-report.md"
    out_b = tmp_path / "b" / "impact-report.md"
    assert _run(synthetic_intermediate, out_a) == 0
    assert _run(synthetic_intermediate, out_b) == 0
    for fname in ("new-cliques.csv", "modified-cliques.csv", "modified-cliques.json", "new-xrefs.tsv"):
        a = (tmp_path / "a" / "impact-report" / fname).read_bytes()
        b = (tmp_path / "b" / "impact-report" / fname).read_bytes()
        assert a == b, f"{fname} differs between runs — output is not deterministic"


@pytest.mark.unit
def test_no_detail_files_flag_skips_subdirectory(synthetic_intermediate, tmp_path):
    output = tmp_path / "impact-report.md"
    assert _run(synthetic_intermediate, output, extra=("--no-detail-files",)) == 0
    assert output.exists()
    assert not (tmp_path / "impact-report").exists()
