"""Tests for the helpers shared across the Snakemake files (src/snakefiles/util.py)."""

import pytest

from src.snakefiles.util import duckdb_memory_limit_mb


@pytest.mark.unit
@pytest.mark.parametrize(
    "mem_mb,expected",
    [
        (131072, 98304),  # 128G in MB * 0.75
        (524288, 393216),  # 512G in MB * 0.75
    ],
)
def test_duckdb_memory_limit_mb(mem_mb, expected):
    """Should take resources.mem_mb (a plain int) and return `fraction` of it in MB.

    Not resources.mem: Snakemake round-trips that through humanfriendly.format_size() for display
    (e.g. our "512G" rule setting comes back as "512 GB"), which mem_mb sidesteps entirely.
    """
    assert duckdb_memory_limit_mb(mem_mb) == expected
