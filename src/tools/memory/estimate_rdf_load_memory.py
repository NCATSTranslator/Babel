#!/usr/bin/env python
"""Estimate the peak RAM needed to bulk-load RDF file(s) into an in-memory store.

Several Babel data handlers load a whole RDF/TTL/OWL dump into an in-memory
``pyoxigraph.Store`` before querying it (e.g. ``ChemblRDF`` in
``src/datahandlers/chembl.py``). On a large dump this can need far more memory
than the file size on disk, which determines the ``mem=`` resource on the
Snakemake rule and the ``@pytest.mark.min_memory_gb`` guard on its pipeline test.

This tool gives an empirical number instead of a guess. It streams the input in
small chunks into an in-memory store, samples resident memory (RSS) against the
number of bytes consumed, and extrapolates linearly to the full file size. It
stops once RSS crosses ``--rss-ceiling-gib`` (or ``--max-fraction`` of the input
is loaded) so the probe itself never exhausts RAM — you can estimate a 120 GiB
load on a 32 GiB laptop.

Reading the output: the per-sample ``projected full load`` is noisy at very low
percentages (fixed startup overhead dominates) and stabilises as more loads. The
in-memory store also indexes as it loads, so the real peak is usually somewhat
above a pure linear projection — treat the number as a floor and add headroom.

macOS caveat: this estimate is most trustworthy on Linux. macOS transparently
compresses memory, so once the working set gets large the *resident* page count
stops growing while the store keeps expanding — the projection then drifts
downward and understates the true requirement. On macOS, trust the early-region
projection (before ``current RSS`` plateaus) and prefer running on Linux, where
RSS tracks the real footprint, for an authoritative number.

Usage:
    uv run python src/tools/memory/estimate_rdf_load_memory.py FILE [FILE ...] [options]

Examples:
    # ChEMBL: load cco.ttl (tiny) first, then the big molecule dump, like ChemblRDF
    uv run python src/tools/memory/estimate_rdf_load_memory.py \
        babel_downloads/CHEMBL.COMPOUND/cco.ttl \
        babel_downloads/CHEMBL.COMPOUND/chembl_latest_molecule.ttl

    # Stop higher if you have more RAM to spend on a more accurate projection
    uv run python src/tools/memory/estimate_rdf_load_memory.py big.nt --rss-ceiling-gib 24
"""

import argparse
import ctypes
import ctypes.util
import os
import resource
import subprocess
import sys

import pyoxigraph

GIB = 1024**3

# Fast macOS RSS probe via proc_pidinfo (avoids forking ps on every sample).
# proc_pidinfo(pid, PROC_PIDTASKINFO=4, 0, &info, sizeof(info)) returns bytes
# written on success; pti_resident_size is the second uint64 in the struct.
# Initialised once at import; _macos_rss_fn stays None if ctypes setup fails.
_macos_rss_fn: "ctypes.CFUNCTYPE | None" = None
if sys.platform == "darwin":
    try:
        _libproc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)

        class _ProcTaskinfo(ctypes.Structure):
            _fields_ = [
                ("pti_virtual_size", ctypes.c_uint64),
                ("pti_resident_size", ctypes.c_uint64),
                ("pti_total_user", ctypes.c_uint64),
                ("pti_total_system", ctypes.c_uint64),
                ("pti_threads_user", ctypes.c_uint64),
                ("pti_threads_system", ctypes.c_uint64),
                ("pti_policy", ctypes.c_int32),
                ("pti_faults", ctypes.c_int32),
                ("pti_pageins", ctypes.c_int32),
                ("pti_cow_faults", ctypes.c_int32),
                ("pti_messages_sent", ctypes.c_int32),
                ("pti_messages_received", ctypes.c_int32),
                ("pti_syscalls_mach", ctypes.c_int32),
                ("pti_syscalls_unix", ctypes.c_int32),
                ("pti_csw", ctypes.c_int32),
                ("pti_threadnum", ctypes.c_int32),
                ("pti_numrunning", ctypes.c_int32),
                ("pti_priority", ctypes.c_int32),
            ]

        _PROC_PIDTASKINFO = 4
        _pid = os.getpid()
        _taskinfo_buf = _ProcTaskinfo()

        def _macos_rss_fn() -> float:
            _libproc.proc_pidinfo(_pid, _PROC_PIDTASKINFO, 0, ctypes.byref(_taskinfo_buf), ctypes.sizeof(_taskinfo_buf))
            return _taskinfo_buf.pti_resident_size / GIB

    except (OSError, AttributeError, TypeError):
        pass

# Map file extensions to pyoxigraph RDF formats.
_EXT_TO_FORMAT = {
    ".ttl": pyoxigraph.RdfFormat.TURTLE,
    ".nt": pyoxigraph.RdfFormat.N_TRIPLES,
    ".nq": pyoxigraph.RdfFormat.N_QUADS,
    ".trig": pyoxigraph.RdfFormat.TRIG,
    ".rdf": pyoxigraph.RdfFormat.RDF_XML,
    ".owl": pyoxigraph.RdfFormat.RDF_XML,
    ".xml": pyoxigraph.RdfFormat.RDF_XML,
}


def current_rss_gib() -> float:
    """Current (not peak) resident set size of this process, in GiB.

    Current RSS is preferred over getrusage's peak ``ru_maxrss`` because the
    projection needs a value that can go *down* — on macOS this makes
    memory-compression plateaus visible instead of being hidden by a monotonic peak.

    On Linux reads ``/proc/self/status`` directly. On macOS calls ``proc_pidinfo``
    via ctypes (no subprocess). Falls back to ``ps -o rss=`` if ctypes is
    unavailable, then to peak RSS (via getrusage) as the last resort — the
    projection will then be monotonically non-decreasing but the tool won't abort.
    """
    if sys.platform == "linux":
        try:
            with open("/proc/self/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) * 1024 / GIB
        except (OSError, ValueError, IndexError):
            pass
    if _macos_rss_fn is not None:
        return _macos_rss_fn()
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True, check=True)
        return int(out.stdout.strip()) * 1024 / GIB
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return peak_rss_gib()


def peak_rss_gib() -> float:
    """Peak RSS of this process, in GiB (bytes on macOS, kibibytes on Linux)."""
    maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return (maxrss / GIB) if sys.platform == "darwin" else (maxrss * 1024 / GIB)


def format_for(path: str, override: str | None) -> pyoxigraph.RdfFormat:
    if override:
        try:
            return getattr(pyoxigraph.RdfFormat, override.upper())
        except AttributeError:
            valid = sorted(k for k in dir(pyoxigraph.RdfFormat) if k.isupper())
            raise ValueError(f"Unknown RDF format {override!r}; valid --format values: {', '.join(valid)}") from None
    ext = os.path.splitext(path)[1].lower()
    if ext not in _EXT_TO_FORMAT:
        raise ValueError(f"Cannot infer RDF format for {path!r} (extension {ext!r}); pass --format")
    return _EXT_TO_FORMAT[ext]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", help="RDF file(s) to load, in order")
    parser.add_argument(
        "--rss-ceiling-gib", type=float, default=16.0, help="stop once current RSS exceeds this (default: 16)"
    )
    parser.add_argument(
        "--max-fraction", type=float, default=0.30, help="stop once this fraction of input is loaded (default: 0.30)"
    )
    parser.add_argument(
        "--batch", type=int, default=500_000, help="quads inserted per batch / sample interval (default: 500000)"
    )
    parser.add_argument(
        "--format", default=None, help="pyoxigraph RdfFormat name to force (e.g. TURTLE); default: infer from extension"
    )
    args = parser.parse_args()

    total_bytes = sum(os.path.getsize(p) for p in args.files)
    if total_bytes == 0:
        print("inputs: all files are empty — nothing to load")
        return 0
    print(f"inputs: {len(args.files)} file(s), {total_bytes / GIB:.2f} GiB on disk")
    print(
        f"baseline RSS: {current_rss_gib():.3f} GiB; stopping at {args.rss_ceiling_gib:.1f} GiB or {args.max_fraction * 100:.0f}% loaded\n"
    )

    store = pyoxigraph.Store()
    bytes_done = 0  # bytes from files already fully loaded
    bytes_read = 0  # bytes_done plus bytes read from the file in progress
    n_quads = 0
    stopped_early = False

    for path in args.files:
        fmt = format_for(path, args.format)
        batch = []
        with open(path, "rb") as raw:
            for quad in pyoxigraph.parse(input=raw, format=fmt):
                batch.append(quad)
                if len(batch) >= args.batch:
                    store.extend(batch)
                    n_quads += len(batch)
                    batch.clear()
                    bytes_read = bytes_done + raw.tell()
                    frac = bytes_read / total_bytes
                    rss = current_rss_gib()
                    projected = rss / frac if frac else float("nan")
                    print(
                        f"quads={n_quads:>13,}  read={bytes_read / GIB:6.2f} GiB ({frac * 100:5.1f}%)  "
                        f"RSS={rss:6.2f} GiB (peak {peak_rss_gib():6.2f})  ->  projected ≈ {projected:6.1f} GiB",
                        flush=True,
                    )
                    if rss >= args.rss_ceiling_gib or frac >= args.max_fraction:
                        stopped_early = True
                        break
            if not stopped_early and batch:
                store.extend(batch)
                n_quads += len(batch)
        if stopped_early:
            break
        # Only count the whole file once we've actually read all of it.
        bytes_done += os.path.getsize(path)
        bytes_read = bytes_done

    frac = bytes_read / total_bytes
    rss = current_rss_gib()
    print(f"\nquads in store: {len(store):,}")
    print(f"loaded {frac * 100:.1f}% of input at current RSS {rss:.2f} GiB (peak {peak_rss_gib():.2f} GiB)")
    if stopped_early:
        print(f"PROJECTED peak for full load ≈ {rss / frac:.0f} GiB (linear extrapolation; add headroom)")
    else:
        print(f"ACTUAL peak for full load: {peak_rss_gib():.2f} GiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
