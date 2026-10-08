# Linux/cgroup memory diagnostics used by the DuckDB exporter and report rules.
# All functions are best-effort: they degrade to None/``unknown`` off Linux or when
# the relevant /proc and /sys/fs/cgroup files are absent, and they never raise.
import os.path
import resource
import sys

from src.util import get_logger

logger = get_logger(__name__)


def _bytes_to_gib(num_bytes):
    """Format a byte count as a human-readable GiB string, or 'unknown' for None."""
    if num_bytes is None:
        return "unknown"
    return f"{num_bytes / (1024**3):.1f} GiB"


def _parse_cgroup_memory_value(raw):
    """Parse a cgroup memory file's contents into an int byte count, or None.

    Returns None for the cgroup-v2 ``max`` sentinel and the cgroup-v1 "unlimited" sentinel
    (a value near 2**63). cgroup-v2 ``memory.peak``/``memory.current`` are plain integers.
    """
    raw = raw.strip()
    if raw == "max" or not raw:
        return None
    try:
        value = int(raw.split()[0])
    except ValueError:
        return None
    # cgroup v1 reports an absurd sentinel (e.g. PAGE_COUNTER_MAX * page size) when unlimited.
    if value >= (1 << 62):
        return None
    return value


def _parse_proc_cgroup(text):
    """Parse ``/proc/self/cgroup`` text into candidate memory-cgroup directories, most specific first.

    Each line is ``hierarchy-id:controllers:path``. cgroup v2 uses a single ``0::<path>`` line
    (empty controllers); cgroup v1 lists controllers per line, and we want the ``memory`` one.
    """
    dirs = []
    for entry in text.splitlines():
        parts = entry.split(":", 2)
        if len(parts) != 3:
            continue
        _, controllers, path = parts
        rel = path.lstrip("/")
        if controllers == "":  # cgroup v2 unified hierarchy
            dirs.append(os.path.join("/sys/fs/cgroup", rel))
        elif "memory" in controllers.split(","):  # cgroup v1 memory controller
            dirs.append(os.path.join("/sys/fs/cgroup/memory", rel))
    return dirs


def _cgroup_memory_dirs():
    """Directories holding this process's memory-cgroup files, most specific first.

    SLURM places each job in a nested memory cgroup (e.g. ``/slurm/uid_N/job_M/step_0``), so the
    machine-wide ``/sys/fs/cgroup`` root reports the node total, not the job's ``mem=`` allocation.
    We resolve the job cgroup from ``/proc/self/cgroup`` for both cgroup v1 and v2. Returns ``[]``
    off Linux/cgroups. Never raises.
    """
    try:
        with open("/proc/self/cgroup") as fin:
            return _parse_proc_cgroup(fin.read())
    except OSError:
        return []


def _read_cgroup_metric(filenames, root_fallbacks):
    """Read a cgroup memory metric, walking up from the job cgroup to the hierarchy root.

    For each resolved job-cgroup directory we look for any of ``filenames`` (v2 then v1 names),
    walking up parent directories because SLURM often sets the limit on the job cgroup while the
    process sits in a deeper ``step`` cgroup. Falls back to ``root_fallbacks`` (the bare
    ``/sys/fs/cgroup`` paths) so a non-SLURM/local run still reports something. Returns None if
    nothing readable is found. Never raises.
    """
    search_dirs = _cgroup_memory_dirs()
    for start in search_dirs:
        current = start
        while True:
            for filename in filenames:
                try:
                    with open(os.path.join(current, filename)) as fin:
                        value = _parse_cgroup_memory_value(fin.read())
                except OSError:
                    value = None
                if value is not None:
                    return value
            parent = os.path.dirname(current)
            if parent == current or not parent.startswith("/sys/fs/cgroup"):
                break
            current = parent
    for path in root_fallbacks:
        try:
            with open(path) as fin:
                value = _parse_cgroup_memory_value(fin.read())
        except OSError:
            value = None
        if value is not None:
            return value
    return None


def cgroup_memory_hard_limit_bytes():
    """The cgroup memory hard limit (the SLURM ``mem=`` allocation), or None if unavailable.

    This is the ceiling that an *untracked* DuckDB allocation overshoots to produce a
    ``bad allocation`` OOM -- the number to compare ``memory_limit`` against when sizing headroom.
    """
    return _read_cgroup_metric(
        ("memory.max", "memory.limit_in_bytes"),
        ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    )


def cgroup_memory_current_bytes():
    """The cgroup's current memory charge (RSS + page cache + kernel), or None if unavailable."""
    return _read_cgroup_metric(
        ("memory.current", "memory.usage_in_bytes"),
        ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"),
    )


def cgroup_memory_peak_bytes():
    """The peak memory the job's cgroup has ever charged (bytes), or None if unavailable.

    Unlike per-process RSS this includes every thread/child and page cache charged to the job,
    so it is the closest proxy for what actually tripped the cgroup OOM-killer.
    """
    return _read_cgroup_metric(
        ("memory.peak", "memory.max_usage_in_bytes"),
        ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"),
    )


def process_peak_rss_bytes():
    """Peak resident set size of this process, in bytes (covers in-process DuckDB threads)."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is bytes on macOS but kibibytes on Linux.
    return rss if sys.platform == "darwin" else rss * 1024


def _parse_kv_kb_bytes(text, key):
    """Parse a ``Key:   12345 kB`` line (as in /proc/self/status and /proc/meminfo) into bytes.

    Returns the value in bytes, or None if the key is absent or unparseable. Never raises.
    """
    for line in text.splitlines():
        if line.startswith(key + ":"):
            try:
                return int(line.split()[1]) * 1024
            except (ValueError, IndexError):
                return None
    return None


def _read_kv_kb_bytes(path, key):
    """Read a ``Key: value kB`` field from a /proc file as bytes, or None. Never raises."""
    try:
        with open(path) as fin:
            return _parse_kv_kb_bytes(fin.read(), key)
    except OSError:
        return None


def _read_proc_status_bytes(key):
    """Read a ``VmFoo:`` field (kB) from /proc/self/status as bytes, or None."""
    return _read_kv_kb_bytes("/proc/self/status", key)


def _read_meminfo_bytes(key):
    """Read a field (kB) from /proc/meminfo as bytes, or None."""
    return _read_kv_kb_bytes("/proc/meminfo", key)


def _read_int_file(path):
    """Read a file containing a single integer, or None. Never raises."""
    try:
        with open(path) as fin:
            return int(fin.read().strip())
    except (OSError, ValueError):
        return None


def _count_memory_mappings():
    """Number of VMAs in /proc/self/maps (compare against vm.max_map_count), or None."""
    try:
        with open("/proc/self/maps") as fin:
            return sum(1 for _ in fin)
    except OSError:
        return None


def _rlimit_as_bytes():
    """Soft RLIMIT_AS (virtual address-space ceiling) in bytes, or None if unlimited/unavailable."""
    try:
        soft, _ = resource.getrlimit(resource.RLIMIT_AS)
    except (ValueError, OSError, AttributeError):
        return None
    return None if soft == resource.RLIM_INFINITY else soft


def log_memory_snapshot(db, context):
    """Log memory + address-space diagnostics: one RSS/cgroup line and one address-space line.

    A ``bad allocation`` OOM here is not always about running out of *RAM*. With the cgroup figures
    plus the address-space line, three distinct shapes are now distinguishable:

    - cgroup current near the hard limit while DuckDB tracked is small -> untracked memory (string
      heaps, hash-join build sides, file page cache). Lower memory_limit / rewrite the query.
    - cgroup current well below the limit but a *small* allocation still fails -> not a RAM shortage
      but an address-space limit: check ``mappings`` vs ``max_map_count`` (mmap exhaustion), ``VmSize``
      vs ``RLIMIT_AS`` (address-space ulimit), or ``Committed_AS`` vs ``CommitLimit`` with
      ``overcommit=2`` (strict node-level overcommit). The fix is allocator/ulimit/overcommit tuning,
      not more ``mem=``.
    - cgroup current at the limit AND DuckDB tracked large -> the query genuinely needs the RAM.

    Best-effort and self-contained: every lookup is guarded so this never raises and never masks
    the real error, and it degrades to ``unknown`` fields off Linux/cgroups. ``db`` may be None
    (skips the DuckDB tracked-memory query) or any DuckDB connection object.
    """
    try:
        proc_peak = process_peak_rss_bytes()
    except Exception:
        proc_peak = None
    cgroup_limit = cgroup_memory_hard_limit_bytes()
    cgroup_current = cgroup_memory_current_bytes()
    cgroup_peak = cgroup_memory_peak_bytes()

    duckdb_tracked = None
    if db is not None:
        try:
            row = db.execute("SELECT sum(memory_usage_bytes) FROM duckdb_memory()").fetchone()
            duckdb_tracked = row[0] if row else None
        except Exception:
            duckdb_tracked = None

    untracked = None
    if cgroup_current is not None and duckdb_tracked is not None:
        untracked = max(cgroup_current - duckdb_tracked, 0)

    logger.info(
        "Memory snapshot (%s): process peak RSS=%s; cgroup current=%s; cgroup peak=%s; "
        "cgroup hard limit=%s; DuckDB tracked=%s; untracked (cgroup current - DuckDB tracked)=%s",
        context,
        _bytes_to_gib(proc_peak),
        _bytes_to_gib(cgroup_current),
        _bytes_to_gib(cgroup_peak),
        _bytes_to_gib(cgroup_limit),
        _bytes_to_gib(duckdb_tracked),
        _bytes_to_gib(untracked),
    )

    # A second line for the address-space limits that cause a `bad allocation` even with free RAM.
    try:
        mappings = _count_memory_mappings()
        max_map_count = _read_int_file("/proc/sys/vm/max_map_count")
        overcommit = _read_int_file("/proc/sys/vm/overcommit_memory")
        logger.info(
            "Address-space snapshot (%s): VmSize=%s; VmPeak=%s; mappings=%s/max_map_count=%s; "
            "RLIMIT_AS=%s; overcommit_memory=%s; Committed_AS=%s/CommitLimit=%s; MemAvailable=%s",
            context,
            _bytes_to_gib(_read_proc_status_bytes("VmSize")),
            _bytes_to_gib(_read_proc_status_bytes("VmPeak")),
            mappings if mappings is not None else "unknown",
            max_map_count if max_map_count is not None else "unknown",
            _bytes_to_gib(_rlimit_as_bytes()),
            overcommit if overcommit is not None else "unknown",
            _bytes_to_gib(_read_meminfo_bytes("Committed_AS")),
            _bytes_to_gib(_read_meminfo_bytes("CommitLimit")),
            _bytes_to_gib(_read_meminfo_bytes("MemAvailable")),
        )
    except Exception:
        pass
