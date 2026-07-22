"""Tests for the helpers shared across the Snakemake files (src/snakefiles/util.py).

Offline / unit-only: covers the DuckDB memory-limit helper and the unstable gating that opts the
manual compendium into the aggregators.
"""

import pytest

from src.snakefiles.util import (
    duckdb_memory_limit_mb,
    get_all_compendia,
    get_all_synonyms,
    unstable_enabled,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "mem_mb,expected",
    [
        # Snakemake parses a rule's mem= with decimal suffixes, so mem="128G" reaches us as
        # mem_mb=128000, not 131072. These are the values the pipeline actually passes in.
        (128000, 96000),  # mem="128G" * 0.75
        (512000, 384000),  # mem="512G" * 0.75
        (1001, 750),  # a non-round allocation truncates rather than rounding up
    ],
)
def test_duckdb_memory_limit_mb(mem_mb, expected):
    """Should take resources.mem_mb (a plain int) and return `fraction` of it in MB, truncated.

    Not resources.mem: Snakemake stores every sized resource as mem_mb internally and re-exposes
    `mem` through humanfriendly formatting for display, so our "512G" rule setting comes back as
    the string "512 GB". mem_mb sidesteps that round-trip entirely.
    """
    assert duckdb_memory_limit_mb(mem_mb) == expected


def _full_config(unstable: object) -> dict[str, object]:
    """A config with every key the aggregators read; only manual_outputs carries a filename."""
    keys = [
        "anatomy_outputs",
        "chemical_outputs",
        "disease_outputs",
        "gene_outputs",
        "genefamily_outputs",
        "process_outputs",
        "protein_outputs",
        "taxon_outputs",
        "cell_line_outputs",
        "umls_outputs",
        "macromolecularcomplex_outputs",
        "publication_outputs",
        "drugchemicalconflated_synonym_outputs",
        "geneproteinconflated_synonym_outputs",
    ]
    cfg: dict[str, object] = {key: [] for key in keys}
    cfg["manual_outputs"] = ["Manual.txt"]
    cfg["unstable"] = unstable
    return cfg


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("  true  ", True),
        (False, False),
        ("false", False),
        ("False", False),
        ("no", False),
        (None, False),
        (1, False),  # only an actual bool True or the string "true" opts in
    ],
)
def test_unstable_enabled(value: object, expected: bool) -> None:
    assert unstable_enabled({"unstable": value}) is expected


@pytest.mark.unit
def test_unstable_enabled_defaults_false_when_absent() -> None:
    assert unstable_enabled({}) is False


@pytest.mark.unit
def test_get_all_compendia_excludes_manual_when_stable() -> None:
    cfg = _full_config(False)
    assert get_all_compendia(cfg) == []
    assert "Manual.txt" not in get_all_synonyms(cfg)


@pytest.mark.unit
def test_get_all_compendia_includes_manual_when_unstable() -> None:
    cfg = _full_config(True)
    assert get_all_compendia(cfg) == ["Manual.txt"]
    assert "Manual.txt" in get_all_synonyms(cfg)
