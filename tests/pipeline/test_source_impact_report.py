"""Pipeline-marked test for the source-impact report CLI.

Uses the existing ``emapa_pipeline_outputs`` fixture from ``tests/pipeline/conftest.py``
to ensure EMAPA's intermediate ids and concord files are populated, then drives
``src.cli.source_impact_report.main`` in synthetic mode and asserts the rendered report
covers the four required sections with sensible counts.
"""

import os

import pytest

from src.cli.source_impact_report import main as run_cli


@pytest.mark.pipeline
def test_source_impact_report_runs_for_emapa(emapa_pipeline_outputs, tmp_path):
    ids_path = emapa_pipeline_outputs["anatomy"]
    intermediate_root = os.path.dirname(os.path.dirname(os.path.dirname(ids_path)))

    output_path = tmp_path / "EMAPA-impact-report.md"

    exit_code = run_cli(
        [
            "--source",
            "EMAPA",
            "--mode",
            "synthetic",
            "--intermediate-root",
            intermediate_root,
            "--output",
            str(output_path),
            "--format",
            "md",
        ]
    )

    assert exit_code == 0, "CLI should exit 0 for EMAPA in synthetic mode"
    assert output_path.exists(), f"expected report at {output_path}"

    report = output_path.read_text()
    assert "# Source impact report: EMAPA" in report
    assert "## 1. Identifiers added" in report
    assert "## 2. Biolink types" in report
    assert "## 3. Cross-references added" in report
    assert "## 4. Clique impact" in report
    assert "EMAPA: " in report
    assert "biolink:AnatomicalEntity" in report
    assert "Comparison mode: synthetic" in report

    # The four full detail files land in the report's <output-stem>/ subdirectory.
    details = output_path.parent / output_path.stem
    for fname in (
        "new-cliques.csv",
        "modified-cliques.csv",
        "modified-cliques.json",
        "new-xrefs.tsv",
    ):
        path = details / fname
        assert path.exists(), f"expected detail file {path}"
        assert path.stat().st_size > 0, f"detail file {path} should be non-empty"
    # The markdown links into that subdirectory by its relative name.
    assert f"{output_path.stem}/new-cliques.csv" in report
