"""Tests for tools/babel-errors.py (loaded via importlib because of the hyphen in its name)."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "babel_errors", Path(__file__).resolve().parent.parent / "tools" / "babel-errors.py"
)
babel_errors = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(babel_errors)


@pytest.mark.unit
def test_extract_error_content_surfaces_connect_time_headroom(tmp_path):
    """A connect-time headroom line near the top of a traceback-less SIGABRT log is surfaced."""
    log = (
        "INFO src.exporters.duckdb_exporters: DuckDB connected with the following settings:\n"
        "INFO src.exporters.duckdb_exporters:  - memory_limit: 1.2 TiB\n"
        "INFO src.exporters.duckdb_exporters: DuckDB memory headroom: "
        "memory_limit=1000G, cgroup hard limit (SLURM mem)=1500.0 GiB\n"
        + "\n".join(f"filler {i}" for i in range(200))
        + "\nterminate called after throwing an instance of 'duckdb::OutOfMemoryException'\n"
        "  what():  Failed to allocate block of 16384 bytes (bad allocation)\n"
        "srun: error: largemem-5-2: task 0: Aborted (core dumped)\n"
    )
    log_path = tmp_path / "1862.log"
    log_path.write_text(log)

    content = babel_errors.extract_error_content(log_path, fallback_lines=50)

    # The SIGABRT tail is kept...
    assert "Aborted (core dumped)" in content
    # ...and the headroom line, 200+ lines above the tail, is pulled into the diagnostics section.
    assert "--- DuckDB memory diagnostics (from elsewhere in log) ---" in content
    assert "cgroup hard limit (SLURM mem)=1500.0 GiB" in content


@pytest.mark.unit
def test_extract_error_content_no_duplicate_diagnostics_section(tmp_path):
    """When a marker line already sits inside the extracted tail, no extra section is appended."""
    log = "\n".join(f"filler {i}" for i in range(10)) + (
        "\nMemory snapshot (at failure of pass 1): process peak RSS=900.0 GiB; "
        "cgroup peak=1500.0 GiB; DuckDB tracked=400.0 GiB; untracked=1100.0 GiB\n"
        "Out of Memory Error: Failed to allocate block (bad allocation)\n"
    )
    log_path = tmp_path / "x.log"
    log_path.write_text(log)

    content = babel_errors.extract_error_content(log_path, fallback_lines=50)

    assert "Memory snapshot (at failure of pass 1)" in content
    assert "--- DuckDB memory diagnostics" not in content


@pytest.mark.unit
def test_collect_memory_diagnostics_dedupes_and_ignores_settings_dump(tmp_path):
    """Diagnostic markers are collected and de-duplicated; the verbose settings dump is ignored."""
    lines = [
        "INFO ...:  - memory_limit: 1.2 TiB",  # verbose dump, must NOT be collected
        "INFO ...: DuckDB memory headroom: memory_limit=700G, cgroup hard limit (SLURM mem)=1500.0 GiB",
        "INFO ...: DuckDB memory headroom: memory_limit=700G, cgroup hard limit (SLURM mem)=1500.0 GiB",  # dup
        "INFO ...: Memory snapshot (complete): process peak RSS=120.0 GiB; cgroup peak=unknown",
    ]

    found = babel_errors._collect_memory_diagnostics(lines)

    assert len(found) == 2
    assert not any("- memory_limit:" in line for line in found)
    assert any("DuckDB memory headroom" in line for line in found)
    assert any("Memory snapshot (complete)" in line for line in found)
