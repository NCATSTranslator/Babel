"""Open DuckDB connections the way every Babel DuckDB step does, and report their settings when a query fails.

:func:`setup_duckdb` is the one place a DuckDB connection is configured: ``config.yaml``'s ``duckdb_config``
defaults merged with the caller's settings, a per-job spill directory, and connect-time log lines recording every
setting and the memory headroom under the SLURM cgroup. :func:`log_duckdb_settings_on_error` wraps a query so a
failure names the step and the limits in force. The pipeline's exporters (``src/exporters/duckdb_exporters.py``) and
reports (``src/reports/duckdb_reports.py``) use both, and so does ``babel-inchikey-audit``; new DuckDB code should
open its connection here rather than calling ``duckdb.connect()`` itself.
"""

import os
from contextlib import contextmanager

import duckdb

from src.memory import bytes_to_gib, cgroup_memory_hard_limit_bytes, log_memory_snapshot
from src.util import get_config, get_logger, sql_str

logger = get_logger(__name__)


# The DuckDB settings most relevant to diagnosing an out-of-memory or spill failure. Kept short
# so the on-error log line stays readable; the full set is dumped by setup_duckdb() at connect.
_DUCKDB_DIAGNOSTIC_SETTINGS = (
    "memory_limit",
    "max_memory",
    "threads",
    "temp_directory",
    "max_temp_directory_size",
    "preserve_insertion_order",
)


@contextmanager
def log_duckdb_settings_on_error(db, operation):
    """Log the effective DuckDB memory/spill settings if the wrapped call raises.

    DuckDB's OutOfMemory and IO errors don't say which limits were in force or which step hit
    them, which makes the bare Snakemake traceback hard to act on. Wrapping a query in this
    context manager emits one ERROR line naming the `operation` and the relevant settings before
    re-raising the original exception unchanged.

    It also catches Python's ``MemoryError``: an out-of-memory failure can surface there instead of as a
    ``duckdb.Error``, for instance while ``fetchall()`` pulls a large result into Python, and that is exactly the
    failure this record exists for.
    """
    try:
        yield
    except (duckdb.Error, MemoryError) as exc:
        try:
            placeholders = ", ".join("?" for _ in _DUCKDB_DIAGNOSTIC_SETTINGS)
            rows = db.execute(
                f"SELECT name, value FROM duckdb_settings() WHERE name IN ({placeholders})",
                list(_DUCKDB_DIAGNOSTIC_SETTINGS),
            ).fetchall()
            settings = ", ".join(f"{name}={value}" for name, value in sorted(rows))
        except Exception:  # diagnostics must never mask the real error
            settings = "<could not read duckdb_settings()>"
        logger.error(
            "DuckDB operation failed during %s (%s: %s); effective settings: %s",
            operation,
            type(exc).__name__,
            exc,
            settings,
        )
        # Peak/tracked/untracked memory at the point of failure -- the single most useful thing
        # for distinguishing "needs more headroom" from "untracked allocation / query rewrite".
        log_memory_snapshot(db, f"at failure of {operation}")
        raise


def setup_duckdb(duckdb_filename, duckdb_config=None):
    """
    Set up a DuckDB instance using the settings in the config.

    :return: The DuckDB instance to be used.
    """
    if not duckdb_config:
        duckdb_config = {}

    # We want to use (1) the global duckdb_config, then (2) the duckdb_config passed to this function.
    complete_duckdb_config = {**get_config().get("duckdb_config", {}), **duckdb_config}

    # These two keys are Babel conveniences, not DuckDB connect() settings, so pull them out
    # before handing the rest to duckdb.connect(). They let an individual rule override where
    # DuckDB spills and how large that spill may grow.
    temp_directory_override = complete_duckdb_config.pop("temp_directory", None)
    max_temp_directory_size = complete_duckdb_config.pop("max_temp_directory_size", None)

    db = duckdb.connect(duckdb_filename, config=complete_duckdb_config)

    # Apply some Babel-wide settings to DuckDB.
    config = get_config()

    # Decide where DuckDB spills larger-than-memory intermediates. Precedence:
    #   1. an explicit per-call `temp_directory` (a rule that wants a specific scratch area),
    #   2. the BABEL_DUCKDB_TEMP_DIR environment variable (set per job at submission time),
    #   3. the global `tmp_directory` from config.yaml.
    # Hatteras has no large node-local disk we can use: /tmp is a ~16 GB rootfs, /dev/shm is
    # RAM (charged against the job's cgroup), and /scratch and /projects are both NFS. So the
    # default stays on the parallel filesystem; see slurm/README.md ("Temporary scratch space").
    temp_directory = temp_directory_override or os.environ.get("BABEL_DUCKDB_TEMP_DIR") or config.get("tmp_directory")
    if temp_directory:
        # Give every job its own spill subdirectory. Multiple report jobs previously shared a
        # single NFS temp directory, which produced "stale file handle" / "could not read
        # enough bytes" IO errors when one job's temp files raced against another's; per-job
        # isolation removes that contention regardless of which filesystem is used.
        job_id = os.environ.get("SLURM_JOB_ID") or str(os.getpid())
        temp_directory = os.path.join(temp_directory, f"duckdb-{job_id}")
        os.makedirs(temp_directory, exist_ok=True)
        db.execute(f"SET temp_directory = {sql_str(temp_directory)}")
        db.execute(f"SET max_temp_directory_size = {sql_str(max_temp_directory_size or '500GB')}")

    # We need to set local settings after the connection has been opened.
    db.execute("SET enable_progress_bar=true")

    # Display all the settings.
    settings = db.sql("SELECT * FROM duckdb_settings()")
    logger.info("DuckDB connected with the following settings:")
    for row in settings.fetchall():
        logger.info(f" - {row[0]}: {row[1]}")

    # Log the memory_limit vs the cgroup hard limit (the SLURM mem= allocation) at connect time.
    # When threads > 1, a background-thread OOM aborts the process with SIGABRT and no Python
    # exception, so log_duckdb_settings_on_error never runs -- this connect-time line is then the
    # only record of how much headroom DuckDB had under the cgroup. A small or negative headroom
    # here means an untracked allocation can overshoot the cgroup before DuckDB's soft limit
    # triggers a spill; lower memory_limit (and/or drop to a single thread) to widen it.
    try:
        memory_limit_row = db.execute("SELECT value FROM duckdb_settings() WHERE name = 'memory_limit'").fetchone()
        memory_limit = memory_limit_row[0] if memory_limit_row else "unknown"
    except Exception:
        memory_limit = "unknown"
    cgroup_limit = cgroup_memory_hard_limit_bytes()
    logger.info(
        "DuckDB memory headroom: memory_limit=%s, cgroup hard limit (SLURM mem)=%s",
        memory_limit,
        bytes_to_gib(cgroup_limit),
    )

    return db
