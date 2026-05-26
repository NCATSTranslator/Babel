"""Unit test for the source-impact report CLI, end to end on synthetic data.

A fixture lays down two anatomy datasets in a temporary intermediate root:

- ``EXISTING`` — stands in for the current Babel set (four singleton cliques).
- ``NEWSOURCE`` — the source under evaluation, with concord rows chosen so that adding
  it produces a meaningful mix of clique changes against ``EXISTING``: two pure-new
  cliques, one expanded clique, and one merged clique.

The test drives the real ``src.cli.source_impact_report.main`` in synthetic mode — the
same entrypoint the EMAPA pipeline test exercises — but because the intermediate files
are synthetic the whole run is offline and fast, so this is a ``unit`` test rather than
a ``pipeline`` one.
"""

import json

import pytest

from src.cli.source_impact_report import main


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def synthetic_intermediate(tmp_path):
    """Build an intermediate root holding the current-Babel set and the source to add.

    Returns the intermediate-root path, an (empty) compendia-root path, and the name of
    the source under evaluation.
    """
    root = tmp_path / "intermediate"
    anatomy = root / "anatomy"

    # Dataset 1 — the current Babel set: four anatomy identifiers, no cross-references,
    # so each is its own singleton clique before NEWSOURCE is added.
    _write(
        anatomy / "ids" / "EXISTING",
        "UBERON:0001\tbiolink:AnatomicalEntity\n"
        "UBERON:0002\tbiolink:AnatomicalEntity\n"
        "GO:0000003\tbiolink:CellularComponent\n"
        "UBERON:0010\tbiolink:AnatomicalEntity\n",
    )

    # Dataset 2 — the source being added. NEWSRC:1 and NEWSRC:4 have no overlap with
    # EXISTING (pure-new); NEWSRC:2 cross-references into the UBERON:0001 clique
    # (expands it); NEWSRC:3 cross-references both UBERON:0002 and GO:0000003, bridging
    # two previously separate cliques (a merge).
    _write(
        anatomy / "ids" / "NEWSOURCE",
        "NEWSRC:1\tbiolink:AnatomicalEntity\n"
        "NEWSRC:2\tbiolink:AnatomicalEntity\n"
        "NEWSRC:3\tbiolink:AnatomicalEntity\n"
        "NEWSRC:4\tbiolink:GrossAnatomicalStructure\n",
    )
    _write(
        anatomy / "concords" / "NEWSOURCE",
        "NEWSRC:2\txref\tUBERON:0001\n"
        "NEWSRC:3\txref\tUBERON:0002\n"
        "NEWSRC:3\txref\tGO:0000003\n",
    )

    return {
        "intermediate_root": root,
        "compendia_root": tmp_path / "compendia",
        "source": "NEWSOURCE",
    }


@pytest.mark.unit
def test_cli_synthetic_report_covers_all_sections(synthetic_intermediate, tmp_path):
    output = tmp_path / "NEWSOURCE-impact-report.md"

    exit_code = main(
        [
            "--source", synthetic_intermediate["source"],
            "--mode", "synthetic",
            "--intermediate-root", str(synthetic_intermediate["intermediate_root"]),
            "--compendia-root", str(synthetic_intermediate["compendia_root"]),
            "--output", str(output),
            "--format", "md",
        ]
    )

    assert exit_code == 0, "CLI should exit 0 for a discoverable source in synthetic mode"
    report = output.read_text()

    # Header and the four documented sections.
    assert "# Source impact report: NEWSOURCE" in report
    assert "## 1. Identifiers added" in report
    assert "## 2. Biolink types" in report
    assert "## 3. Cross-references added" in report
    assert "## 4. Clique impact" in report
    assert "Comparison mode: synthetic" in report

    # Section 1: 4 identifiers under one prefix, one semantic type.
    assert "- NEWSRC: 4" in report
    assert "- anatomy: 4" in report

    # Section 2: both declared biolink types are counted.
    assert "biolink:AnatomicalEntity: 3" in report
    assert "biolink:GrossAnatomicalStructure: 1" in report

    # Section 3: 3 concord rows, partner prefixes UBERON x2 / GO x1.
    assert "3 cross-reference rows" in report
    assert "UBERON: 2" in report
    assert "GO: 1" in report

    # Section 4: the overlap with EXISTING yields 2 pure-new, 1 expanded, 1 merged.
    assert "2 new cliques composed only of NEWSOURCE identifiers" in report
    assert "1 existing cliques contain NEWSOURCE identifiers" in report
    assert "1 existing cliques will be merged" in report

    # Markdown hygiene: the report is committed to docs/, so it must satisfy the repo
    # markdown linter — every list item preceded by a blank line or another list item
    # (MD032), and no trailing blank lines (MD012).
    report_lines = report.split("\n")
    for i, line in enumerate(report_lines[1:], start=1):
        if line.lstrip().startswith("- "):
            prev = report_lines[i - 1]
            assert not prev.strip() or prev.lstrip().startswith("- "), (
                f"list item not preceded by a blank line or list item: {line!r}"
            )
    assert report == report.rstrip("\n") + "\n", "report must end with exactly one newline"


@pytest.mark.unit
def test_cli_synthetic_report_json_diff_counts(synthetic_intermediate, tmp_path):
    output = tmp_path / "NEWSOURCE-impact-report.json"

    exit_code = main(
        [
            "--source", synthetic_intermediate["source"],
            "--mode", "synthetic",
            "--intermediate-root", str(synthetic_intermediate["intermediate_root"]),
            "--compendia-root", str(synthetic_intermediate["compendia_root"]),
            "--output", str(output),
            "--format", "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output.read_text())

    assert payload["source"] == "NEWSOURCE"
    assert payload["total_identifier_count"] == 4
    assert payload["total_concord_row_count"] == 3
    assert payload["semantic_types"] == ["anatomy"]

    anatomy_diff = payload["clique_diffs"]["anatomy"]
    assert anatomy_diff["pure_new_clique_count"] == 2
    assert anatomy_diff["expanded_clique_count"] == 1
    assert anatomy_diff["merged_clique_count"] == 1
