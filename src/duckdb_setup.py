"""Open DuckDB connections the way every Babel DuckDB step does, and report their settings when a query fails.

:func:`setup_duckdb` is the one place a DuckDB connection is configured: ``config.yaml``'s ``duckdb_config``
defaults merged with the caller's settings, a per-job spill directory, and connect-time log lines recording every
setting and the memory headroom under the SLURM cgroup. :func:`log_duckdb_settings_on_error` wraps a query so a
failure names the step and the limits in force. The pipeline's exporters (``src/exporters/duckdb_exporters.py``) and
reports (``src/reports/duckdb_reports.py``) use both, and so does ``babel-inchikey-audit``; new DuckDB code should
open its connection here rather than calling ``duckdb.connect()`` itself.
"""

import atexit
import os
import shutil
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


# Spill directories this process created; _remove_spill_directories() deletes them at exit.
_spill_directories = set()


def _spill_directory(temp_base):
    """Create and return this process's DuckDB spill directory under ``temp_base``.

    Multiple report jobs once shared a single NFS temp directory, which produced "stale file handle" / "could not read
    enough bytes" IO errors when one job's temp files raced against another's. So each process gets its own
    subdirectory, ``duckdb-<SLURM_JOB_ID>-<pid>`` on SLURM and ``duckdb-<pid>`` elsewhere: the job ID makes a
    leftover directory traceable to its job log, and the pid keeps two processes in one allocation apart, since the
    directory is deleted at process exit. Every connection a process opens shares the one directory.
    """
    pid = str(os.getpid())
    job_id = os.environ.get("SLURM_JOB_ID")
    spill_directory = os.path.join(temp_base, f"duckdb-{job_id}-{pid}" if job_id else f"duckdb-{pid}")
    os.makedirs(spill_directory, exist_ok=True)
    _spill_directories.add(spill_directory)
    return spill_directory


@atexit.register
def _remove_spill_directories():
    """Delete the spill directories this process created.

    DuckDB deletes its own spill files when a connection closes, but not a ``temp_directory`` it did not create, so
    without this every job leaves a directory behind -- and a job that raised mid-query can leave its spill files in
    it too. A process killed outright (SIGKILL at the SLURM time limit, a SIGABRT from a DuckDB background-thread
    out-of-memory) skips atexit handlers, so its directory remains and must be cleared by hand.
    """
    for spill_directory in list(_spill_directories):
        shutil.rmtree(spill_directory, ignore_errors=True)
        _spill_directories.discard(spill_directory)


def setup_duckdb(duckdb_filename, duckdb_config=None):
    """Open a DuckDB connection configured the way every Babel DuckDB step expects, and log its settings.

    Settings are ``config.yaml``'s ``duckdb_config`` defaults overlaid with ``duckdb_config`` (the caller wins on a
    clash). Two keys in either are Babel's own rather than ``duckdb.connect()`` settings, and are applied with ``SET``
    after connecting:

    - ``temp_directory``: the base directory DuckDB spills into. Precedence is this key, then the
      ``BABEL_DUCKDB_TEMP_DIR`` environment variable, then ``config.yaml``'s ``tmp_directory``. Spills go to a
      subdirectory of that base unique to this process (see :func:`_spill_directory`), which is removed when the
      process exits.
    - ``max_temp_directory_size``: the spill cap. Applied whenever it is given, even if no spill directory resolves;
      when a spill directory resolves and it is not given, it defaults to ``500GB``.

    If anything after ``duckdb.connect()`` fails, the connection is closed before the exception propagates, so the
    database file is not left locked.

    :param duckdb_filename: The database file to open (or ``":memory:"``).
    :param duckdb_config: Per-call settings overriding ``config.yaml``'s ``duckdb_config``; ``None`` for none.
    :return: The open DuckDB connection; usable as a context manager.
    """
    config = get_config()
    complete_duckdb_config = {**config.get("duckdb_config", {}), **(duckdb_config or {})}

    # These two keys are Babel conveniences, not DuckDB connect() settings, so pull them out
    # before handing the rest to duckdb.connect(). They let an individual rule override where
    # DuckDB spills and how large that spill may grow.
    temp_directory_override = complete_duckdb_config.pop("temp_directory", None)
    max_temp_directory_size = complete_duckdb_config.pop("max_temp_directory_size", None)

    db = duckdb.connect(duckdb_filename, config=complete_duckdb_config)
    try:
        # Decide where DuckDB spills larger-than-memory intermediates. Precedence:
        #   1. an explicit per-call `temp_directory` (a rule that wants a specific scratch area),
        #   2. the BABEL_DUCKDB_TEMP_DIR environment variable (set per job at submission time),
        #   3. the global `tmp_directory` from config.yaml.
        # Hatteras has no large node-local disk we can use: /tmp is a ~16 GB rootfs, /dev/shm is
        # RAM (charged against the job's cgroup), and /scratch and /projects are both NFS. So the
        # default stays on the parallel filesystem; see slurm/README.md ("Temporary scratch space").
        temp_base = temp_directory_override or os.environ.get("BABEL_DUCKDB_TEMP_DIR") or config.get("tmp_directory")
        if temp_base:
            temp_directory = _spill_directory(temp_base)
            db.execute(f"SET temp_directory = {sql_str(temp_directory)}")
            max_temp_directory_size = max_temp_directory_size or "500GB"
        if max_temp_directory_size:
            db.execute(f"SET max_temp_directory_size = {sql_str(max_temp_directory_size)}")

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
        logger.info(
            "DuckDB memory headroom: memory_limit=%s, cgroup hard limit (SLURM mem)=%s",
            memory_limit,
            bytes_to_gib(cgroup_memory_hard_limit_bytes()),
        )
    except BaseException:
        # Don't leave the database file locked by a connection the caller never received.
        db.close()
        raise

    return db
