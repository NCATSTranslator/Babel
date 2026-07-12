"""Tests for the helpers shared across the Snakemake files (src/snakefiles/util.py)."""

import pytest

from src.snakefiles.util import duckdb_memory_limit_mb


@pytest.mark.unit
@pytest.mark.parametrize(
    "mem,expected",
    [
        ("128G", 98304),  # 128 * 1024 * 0.75
        ("512G", 393216),
    ],
)
def test_duckdb_memory_limit_mb(mem, expected):
    assert duckdb_memory_limit_mb(mem) == expected


@pytest.mark.unit
def test_duckdb_memory_limit_mb_rejects_non_gigabyte_allocation():
    """A `mem` we can't parse must fail loudly rather than silently handing DuckDB a wrong limit
    (and letting it overshoot the job's cgroup allocation)."""
    with pytest.raises(ValueError, match="whole gigabytes"):
        duckdb_memory_limit_mb("128000M")
