import pytest

from src.memory import (
    _bytes_to_gib,
    _parse_cgroup_memory_value,
    _parse_kv_kb_bytes,
    _parse_proc_cgroup,
    log_memory_snapshot,
    process_peak_rss_bytes,
)


@pytest.mark.unit
def test_bytes_to_gib_formats_and_handles_none():
    assert _bytes_to_gib(None) == "unknown"
    assert _bytes_to_gib(0) == "0.0 GiB"
    assert _bytes_to_gib(1024**3) == "1.0 GiB"
    assert _bytes_to_gib(int(1.5 * 1024**3)) == "1.5 GiB"


@pytest.mark.unit
def test_parse_proc_cgroup_resolves_slurm_job_cgroup():
    """The SLURM job cgroup is resolved from /proc/self/cgroup for both cgroup v1 and v2."""
    # cgroup v1: a memory-controller line points under /sys/fs/cgroup/memory.
    v1 = "12:cpuset:/\n7:memory:/slurm/uid_1000/job_1870/step_0\n3:cpu,cpuacct:/slurm\n"
    assert _parse_proc_cgroup(v1) == ["/sys/fs/cgroup/memory/slurm/uid_1000/job_1870/step_0"]

    # cgroup v2: the unified 0:: line points directly under /sys/fs/cgroup.
    v2 = "0::/system.slice/slurmstepd.scope/job_1870/step_0\n"
    assert _parse_proc_cgroup(v2) == ["/sys/fs/cgroup/system.slice/slurmstepd.scope/job_1870/step_0"]

    # No memory controller / malformed lines -> empty, no exception.
    assert _parse_proc_cgroup("9:cpuset:/\ngarbage\n") == []


@pytest.mark.unit
def test_parse_cgroup_memory_value_parses_and_rejects_sentinels():
    """A plain integer is parsed; 'max', empty, and the cgroup-v1 unlimited sentinel become None."""
    assert _parse_cgroup_memory_value("1610612736\n") == 1610612736
    assert _parse_cgroup_memory_value("max\n") is None
    assert _parse_cgroup_memory_value("") is None
    assert _parse_cgroup_memory_value(f"{1 << 63}\n") is None
    assert _parse_cgroup_memory_value("not-a-number") is None


@pytest.mark.unit
def test_parse_kv_kb_bytes_reads_proc_status_and_meminfo_lines():
    """`Key:   N kB` lines (as in /proc/self/status and /proc/meminfo) parse to bytes."""
    status = "Name:\tpython\nVmPeak:\t 1048576 kB\nVmSize:\t  524288 kB\nThreads:\t4\n"
    assert _parse_kv_kb_bytes(status, "VmPeak") == 1048576 * 1024
    assert _parse_kv_kb_bytes(status, "VmSize") == 524288 * 1024

    meminfo = "MemTotal:       16000000 kB\nCommitLimit:     8000000 kB\nCommitted_AS:    1234567 kB\n"
    assert _parse_kv_kb_bytes(meminfo, "CommitLimit") == 8000000 * 1024
    assert _parse_kv_kb_bytes(meminfo, "Committed_AS") == 1234567 * 1024

    # Absent key, and a prefix that is not a full key match, both return None.
    assert _parse_kv_kb_bytes(status, "VmHWM") is None
    assert _parse_kv_kb_bytes(status, "Vm") is None


@pytest.mark.unit
def test_process_peak_rss_bytes_is_positive():
    assert process_peak_rss_bytes() > 0


@pytest.mark.unit
def test_log_memory_snapshot_never_raises_with_db_none(caplog):
    """The snapshot must be best-effort: db=None and missing cgroup files must not raise."""
    with caplog.at_level("INFO"):
        log_memory_snapshot(None, "snapshot-test")
    assert "Memory snapshot (snapshot-test)" in caplog.text
    assert "process peak RSS=" in caplog.text
