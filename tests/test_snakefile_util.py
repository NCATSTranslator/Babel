"""Tests for the helpers shared across the Snakemake files (src/snakefiles/util.py)."""

import pytest

from src.snakefiles.util import duckdb_memory_limit_mb, get_shared_synonym_audit_filenames


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


@pytest.mark.unit
def test_get_shared_synonym_audit_filenames():
    """Should expand an audit group's config output lists into extensionless synonym file names."""
    config = {
        "shared_synonym_audit_groups": {"disease": ["disease_outputs"], "both": ["disease_outputs", "other_outputs"]},
        "disease_outputs": ["Disease.txt", "PhenotypicFeature.txt"],
        "other_outputs": ["DrugChemicalConflated.txt"],
    }
    assert get_shared_synonym_audit_filenames(config, "disease") == ["Disease", "PhenotypicFeature"]
    assert get_shared_synonym_audit_filenames(config, "both") == [
        "Disease",
        "PhenotypicFeature",
        "DrugChemicalConflated",
    ]


@pytest.mark.unit
def test_shared_synonym_audit_groups_in_config():
    """Should cover disease, pre- and post-conflation chemicals, each resolving to files the build writes."""
    from src.util import get_config

    config = get_config()
    assert set(config["shared_synonym_audit_groups"]) == {"disease", "chemical", "drugchemicalconflated"}
    assert get_shared_synonym_audit_filenames(config, "drugchemicalconflated") == ["DrugChemicalConflated"]
    assert "Drug" in get_shared_synonym_audit_filenames(config, "chemical")
    assert "Disease" in get_shared_synonym_audit_filenames(config, "disease")
