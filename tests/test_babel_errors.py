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
def test_extract_error_content_shows_full_log_and_real_exception(tmp_path):
    """The whole log is shown, so a RuleException far from the tail (not a Python Traceback,
    not in the last N lines) is never hidden -- this is the 1870.log failure shape."""
    log = (
        "INFO src.exporters.duckdb_exporters: DuckDB memory headroom: "
        "memory_limit=400G, cgroup hard limit (SLURM mem)=512.0 GiB\n"
        + "\n".join(f"filler {i}" for i in range(40))
        + "\nRuleException:\n"
        "OutOfMemoryException in file duckdb.snakefile, line 163:\n"
        "Out of Memory Error: Failed to allocate block of 8650496 bytes (bad allocation)\n"
        + "\n".join(f"snakemake boilerplate {i}" for i in range(80))
    )
    log_path = tmp_path / "1870.log"
    log_path.write_text(log)

    content = babel_errors.extract_error_content(log_path, fallback_lines=50)

    # The exception (76+ lines from the end, not a Python Traceback) is present in the full log...
    assert "Failed to allocate block of 8650496 bytes" in content
    assert "filler 0" in content  # ...and so is the top of the log.
    # The memory line appears both inline and in the labelled trailer.
    assert "--- DuckDB memory diagnostics ---" in content
    assert "cgroup hard limit (SLURM mem)=512.0 GiB" in content


@pytest.mark.unit
def test_extract_error_content_collapses_progress_bar_spam(tmp_path):
    """DuckDB progress-bar redraw lines are collapsed to a single marker, not dumped verbatim."""
    progress = " 58% ▕██████████████████████                ▏ (~9 seconds remaining)"
    log = (
        "starting\n"
        + "\n".join(progress for _ in range(500))
        + "\nMemory snapshot (complete): process peak RSS=66.7 GiB; cgroup current=120.0 GiB\n"
        "done\n"
    )
    log_path = tmp_path / "p.log"
    log_path.write_text(log)

    content = babel_errors.extract_error_content(log_path, fallback_lines=50)

    assert "[... DuckDB progress-bar output elided ...]" in content
    assert content.count("seconds remaining") == 0
    assert "starting" in content and "done" in content


@pytest.mark.unit
def test_extract_error_content_caps_pathologically_long_log(tmp_path):
    """A very long log is capped to a head + tail with an elision marker so the report stays usable."""
    log = "\n".join(f"line {i}" for i in range(5000))
    log_path = tmp_path / "long.log"
    log_path.write_text(log)

    content = babel_errors.extract_error_content(log_path, fallback_lines=50)

    assert "log lines elided" in content
    assert "line 0" in content  # head kept
    assert "line 4999" in content  # tail kept


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
