"""Access to the optional Rust accelerators, with the Python implementations as the reference.

Babel's expensive rules are CPU-bound single-threaded Python (`generate_pubmed_concords` alone is
20 h at 99.7% CPU in the babel-1.18 benchmarks), so some of them will get Rust implementations.
This module is the one place that decides whether a Rust implementation is available and safe to
use. Nothing else should import ``src._accel`` directly.

Three rules govern how Rust is used here, and each exists for a specific reason:

**Rust is written only when benchmarking justifies it, and is A/B tested before it replaces
Python.** While a port is being proven out, ``BABEL_DISABLE_RUST=1`` forces the Python path so the
two can be timed and diffed against each other in one checkout. Once the Rust side is confirmed
correct and faster, the Python implementation it replaced is deleted rather than kept indefinitely
as a parallel copy -- see AGENTS.md and rust/README.md.

**A missing extension falls back to Python; it does not raise.** Every snakefile does a top-level
``import src.foo`` at DAG-parse time, so an ImportError here would take down every rule for a
contributor without a Rust toolchain, for a reviewer, and for a fork's CI. AGENTS.md's "a log
warning is not a control" is about *wrong output*; a slower path that produces identical bytes is
not that. The active implementation is logged once, at INFO, so it lands in the SLURM job log.

**A stale extension raises.** That is a bug, not a configuration. The extension is installed
editable -- the compiled artifact lives in the checkout at ``src/_accel.*.so`` -- so ``git pull``
does not rebuild it and a stale binary would otherwise be used silently. The check runs at import
of this module, i.e. at DAG-parse time, so a stale build fails in the first second of a run rather
than eleven hours into a 12-hour rule.

Set ``BABEL_DISABLE_RUST=1`` to force the Python path (for an A/B measurement, or to rule the
extension out while debugging). This is an environment variable rather than a ``config.yaml``
entry deliberately: which of two byte-identical implementations runs is an implementation detail
with no user-facing meaning, and ``config.yaml`` is threaded into Snakemake ``params`` and output
paths where changing it risks perturbing the DAG of a running build. Precedent:
``BABEL_DUCKDB_TEMP_DIR`` in ``src/exporters/duckdb_exporters.py``.
"""

import os

from src.util import get_logger

logger = get_logger(__name__)

# Must equal ABI_VERSION in rust/src/lib.rs. Both are bumped by hand, in the same commit, whenever
# an accelerated function's signature or semantics change.
_REQUIRED_ABI_VERSION = 1


def check_abi_version(compiled, required=_REQUIRED_ABI_VERSION):
    """Return ``compiled`` if its ABI_VERSION matches ``required``, else raise RuntimeError.

    Separate from the import below so it can be tested against a stub module: building a genuinely
    stale extension to exercise this would mean compiling Rust inside a unit test.
    """
    found = getattr(compiled, "ABI_VERSION", None)
    if found != required:
        raise RuntimeError(
            f"The compiled Rust extension src/_accel is stale: it reports ABI_VERSION {found!r}, "
            f"but this checkout needs {required!r}. The extension is installed editable, so "
            f"pulling new Rust source does not rebuild it. Run "
            f"`uv sync --reinstall-package babel-pipeline`, or set BABEL_DISABLE_RUST=1 to run "
            f"the Python implementations instead."
        )
    return compiled


# Set to the compiled module when it is present, importable and current; None otherwise. Callers
# should treat it as "use the Rust path if this is not None".
accel = None

if os.environ.get("BABEL_DISABLE_RUST"):
    logger.info("BABEL_DISABLE_RUST is set; using the Python implementations.")
else:
    try:
        from src import _accel as _compiled
    except ImportError:
        # Expected whenever the extension has not been built. Not an error: see the module
        # docstring on why this must not take down the whole DAG.
        logger.info(
            "The Rust extension src/_accel is not built; using the Python implementations. "
            "Build it with `uv sync` (see rust/README.md)."
        )
    else:
        accel = check_abi_version(_compiled)
        logger.info("Using the Rust extension src/_accel (ABI_VERSION %s).", accel.ABI_VERSION)
