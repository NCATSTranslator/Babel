"""Unit tests for the source-impact detail files (CSV/JSON/TSV).

Drives the real ``src.tools.source_impact_report.cli.main`` over a synthetic intermediate root
(offline, so ``unit``-marked) and asserts the four detail files written into the report's
``<output-stem>/`` subdirectory are correct, complete, and deterministic.

The synthetic source ``NEWSOURCE`` is arranged against an ``EXISTING`` Babel set to yield:
two pure-new singleton cliques, one expanded clique (a structurally-new member), and one
merged clique — so every detail file has content to assert on.

Test groups
-----------
- Content correctness: detail files contain the expected rows and values.
- Determinism: two runs over the same inputs produce byte-identical output.
- CLI flags: ``--no-detail-files`` skips the subdirectory entirely.
"""

import csv
import json

import pytest

from src.tools.source_impact_report.cli import main


def _write(path, text):
    """Create parent directories as needed and write *text* to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def synthetic_intermediate(tmp_path):
    """Populate a minimal two-source anatomy intermediate tree under *tmp_path*.

    EXISTING contributes four ids; NEWSOURCE contributes four ids and three concord rows
    that join NEWSRC:2 into an existing clique (expanded), and NEWSRC:3 into two existing
    cliques simultaneously (merged), leaving NEWSRC:1 and NEWSRC:4 as pure-new singletons.
    """
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
    """Invoke ``main`` in synthetic mode against *synthetic_intermediate* and return the exit code."""
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
    """Read a CSV file at *path* and return its rows as a list of dicts."""
    with path.open() as f:
        return list(csv.DictReader(f))


@pytest.mark.unit
def test_detail_files_written_with_expected_content(synthetic_intermediate, tmp_path):
    """All four detail files are created and contain the rows expected from the synthetic fixture.

    Checks new-cliques.csv (two pure-new singletons), modified-cliques.csv (one expanded, one
    merged row), modified-cliques.json (full structure including before_clique_leaders), and
    new-xrefs.tsv (three rows from NEWSOURCE's own concord, all status=added).
    """
    output = tmp_path / "impact-report.md"
    assert _run(synthetic_intermediate, output) == 0

    details = tmp_path / "impact-report"
    assert details.is_dir()

    # new-cliques.csv — the two pure-new singletons (NEWSRC:1, NEWSRC:4).
    new_cliques = _read_csv(details / "new-cliques.csv")
    ids = {r["preferred_id"] for r in new_cliques}
    assert ids == {"NEWSRC:1", "NEWSRC:4"}
    assert all(r["member_count"] == "1" for r in new_cliques)

    # modified-cliques.csv — one row per added/preexisting identifier. The expanded clique
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
    """Two runs over the same intermediate tree produce byte-identical detail files."""
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
    """Passing ``--no-detail-files`` writes the report markdown but skips the detail subdirectory."""
    output = tmp_path / "impact-report.md"
    assert _run(synthetic_intermediate, output, extra=("--no-detail-files",)) == 0
    assert output.exists()
    assert not (tmp_path / "impact-report").exists()
