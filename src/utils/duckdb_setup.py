"""Open DuckDB connections the way every Babel DuckDB step does, and report their settings when a query fails.

:func:`connect_duckdb` is the one place a DuckDB connection is configured: ``config.yaml``'s ``duckdb_config``
defaults merged with the caller's settings, a spill directory of its own, and connect-time log lines recording every
setting and the memory headroom under the SLURM cgroup. It is a context manager, so the connection is closed and its
spill directory removed when the ``with`` block exits. :func:`log_duckdb_settings_on_error` wraps a query so a
failure names the step and the limits in force. The pipeline's exporters (``src/exporters/duckdb_exporters.py``) and
reports (``src/reports/duckdb_reports.py``) use both, and so does ``babel-inchikey-audit``; new DuckDB code should
open its connection here rather than calling ``duckdb.connect()`` itself.
"""

import os
import secrets
import shutil
import sys
from contextlib import contextmanager

import duckdb

from src.util import get_config, get_logger, sql_str
from src.utils.memory import bytes_to_gib, cgroup_memory_hard_limit_bytes, log_memory_snapshot

logger = get_logger(__name__)


# The DuckDB settings most relevant to diagnosing an out-of-memory or spill failure. Kept short
# so the on-error log line stays readable; the full set is dumped by connect_duckdb() at connect.
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


def _make_spill_directory(temp_base):
    """Create and return a new DuckDB spill directory under ``temp_base``, unique to one connection.

    Multiple report jobs once shared a single NFS temp directory, which produced "stale file handle" / "could not read
    enough bytes" IO errors when one job's temp files raced against another's. So every connection gets its own
    subdirectory, ``duckdb-<SLURM_JOB_ID>-<pid>-<random>`` on SLURM and ``duckdb-<pid>-<random>`` elsewhere: the job
    ID makes a leftover directory traceable to its job log, and the random suffix keeps two connections apart even in
    one process, since :func:`connect_duckdb` deletes the directory when its connection closes.

    The directory is made with ``os.mkdir()``, so its permissions follow the umask, rather than with
    ``tempfile.mkdtemp()``, which makes it ``0700``: on the shared project filesystem, the maintainer clearing a
    leftover directory is not always the user whose job made it.
    """
    os.makedirs(temp_base, exist_ok=True)
    job_id = os.environ.get("SLURM_JOB_ID")
    prefix = f"duckdb-{job_id}-{os.getpid()}-" if job_id else f"duckdb-{os.getpid()}-"
    while True:
        path = os.path.join(temp_base, prefix + secrets.token_hex(4))
        try:
            os.mkdir(path)
        except FileExistsError:  # vanishingly rare with a pid in the name, but don't fail the job over it
            continue
        return path


@contextmanager
def connect_duckdb(duckdb_filename, duckdb_config=None):
    """Open a DuckDB connection configured the way every Babel DuckDB step expects, log its settings, and close it
    when the block exits. Use it as ``with connect_duckdb(...) as db:``.

    Settings are ``config.yaml``'s ``duckdb_config`` defaults overlaid with ``duckdb_config`` (the caller wins on a
    clash). Two keys in either are Babel's own rather than ``duckdb.connect()`` settings, and are applied with ``SET``
    after connecting:

    - ``temp_directory``: the base directory DuckDB spills into. Precedence is this key, then the
      ``BABEL_DUCKDB_TEMP_DIR`` environment variable, then ``config.yaml``'s ``tmp_directory``. Spills go to a new
      subdirectory of that base for this connection alone (see :func:`_make_spill_directory`).
    - ``max_temp_directory_size``: the spill cap. Applied whenever it is given, even if no spill directory resolves;
      when a spill directory resolves and it is not given, it defaults to ``500GB``.

    When the block exits -- normally, on an exception, or because setting up the connection failed -- the connection
    is closed and its spill directory deleted, spill files included. Closing writes a checkpoint and can itself fail;
    after a clean block that failure is raised, but after a failed block it is only logged, so the error that ended
    the block is the one the caller sees (:func:`_close_and_remove_spill_directory`). DuckDB deletes its own spill
    files on close but never a ``temp_directory`` it did not create, which is why this is a context manager rather
    than a function returning a connection: a bare connection can close itself, but nothing would remove its
    directory. A process killed outright (SIGKILL at the SLURM time limit, the SIGABRT of a DuckDB background-thread
    out-of-memory) runs no clean-up, so its directory remains; ``slurm/README.md`` ("Temporary Scratch Space") says
    how to clear it.

    :param duckdb_filename: The database file to open (or ``":memory:"``).
    :param duckdb_config: Per-call settings overriding ``config.yaml``'s ``duckdb_config``; ``None`` for none.
    :return: A context manager yielding the open DuckDB connection.
    """
    config = get_config()
    complete_duckdb_config = {**config.get("duckdb_config", {}), **(duckdb_config or {})}

    # These two keys are Babel conveniences, not DuckDB connect() settings, so pull them out
    # before handing the rest to duckdb.connect(). They let an individual rule override where
    # DuckDB spills and how large that spill may grow.
    temp_directory_override = complete_duckdb_config.pop("temp_directory", None)
    max_temp_directory_size = complete_duckdb_config.pop("max_temp_directory_size", None)

    db = duckdb.connect(duckdb_filename, config=complete_duckdb_config)
    spill_directory = None
    block_error = None
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
            spill_directory = _make_spill_directory(temp_base)
            db.execute(f"SET temp_directory = {sql_str(spill_directory)}")
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

        yield db
    except BaseException as exc:
        # Setup or the caller's block failed: remember the error so clean-up never replaces it.
        block_error = exc
        raise
    finally:
        _close_and_remove_spill_directory(db, duckdb_filename, spill_directory, block_error)


def _close_and_remove_spill_directory(db, duckdb_filename, spill_directory, block_error):
    """Close ``db`` and delete ``spill_directory``, without letting a clean-up failure hide the error that ended the
    block.

    If the block raised, that error is the one the caller sees: a failed close is logged and suppressed rather than
    raised in its place. Otherwise closing -- which writes a checkpoint and can itself run out of memory -- runs under
    :func:`log_duckdb_settings_on_error`, and its error is raised. The spill directory is deleted either way; a close
    that failed may leave DuckDB holding spill files open, which on NFS turns them into undeletable ``.nfsXXXX`` files
    until the process exits, so every file or directory that can't be removed is logged by path rather than ignored.
    """
    close_error = None
    try:
        if block_error is None:
            with log_duckdb_settings_on_error(db, f"closing {duckdb_filename}"):
                db.close()
        else:
            db.close()
    except Exception as exc:
        close_error = exc

    if spill_directory:
        _remove_spill_directory(spill_directory)

    if close_error is not None:
        if block_error is None:
            raise close_error
        logger.error(
            "Closing DuckDB database %s also failed (%s: %s) after the block raised; re-raising the block's error",
            duckdb_filename,
            type(close_error).__name__,
            close_error,
        )


def _remove_spill_directory(spill_directory):
    """Delete ``spill_directory`` and everything in it, logging a WARNING for each path that can't be removed.

    Deletion carries on past a failure, so as much is freed as possible; the warnings say what is left, since a spill
    directory can hold hundreds of gigabytes and ``slurm/README.md`` tells maintainers to clear leftovers by hand.
    """

    def log_failure(_function, path, exc):
        logger.warning(
            "Could not delete DuckDB spill path %s (%s: %s); delete it by hand once this job has exited",
            path,
            type(exc).__name__,
            exc,
        )

    # Python 3.12 renamed shutil.rmtree()'s error callback from `onerror` (passed exc_info) to `onexc` (passed the
    # exception); requires-python still admits 3.11.
    if sys.version_info >= (3, 12):
        shutil.rmtree(spill_directory, onexc=log_failure)
    else:
        shutil.rmtree(
            spill_directory, onerror=lambda function, path, exc_info: log_failure(function, path, exc_info[1])
        )
