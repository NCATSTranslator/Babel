"""Access to the Rust accelerators. Rust is the implementation, not an optional overlay.

Babel's expensive rules are CPU-bound single-threaded Python (`generate_pubmed_concords` alone is
20 h at 99.7% CPU in the babel-1.18 benchmarks), so the hot ones get Rust implementations. This
module is the one place that imports the compiled extension; nothing else should import
``src._accel`` directly.

There is no Python fallback and no runtime toggle. A Rust toolchain is a hard build prerequisite
(#975 made the project a mixed Rust/Python package built by maturin), so every environment that can
run Babel at all has the extension. Two rules govern what happens at import:

**A missing extension raises.** Every snakefile does a top-level ``import src.foo`` at DAG-parse
time, so a missing build fails in the first second of a run, with the fix in the message, rather
than silently producing nothing. Since the toolchain is mandatory, a missing extension means the
build regressed -- a failure to surface, not a configuration to work around.

**A stale extension raises.** That is a bug, not a configuration. The extension is installed
editable -- the compiled artifact lives in the checkout at ``src/_accel.*.so`` -- so ``git pull``
does not rebuild it and a stale binary would otherwise be used silently. The check runs at import
of this module, i.e. at DAG-parse time, so a stale build fails in the first second of a run rather
than eleven hours into a 12-hour rule.

Correctness of each Rust implementation is guarded by the unit suite (which exercises the functions
through their real callers) plus targeted synthetic tests -- see ``tests/`` and ``rust/README.md``.
"""

from src import _accel as _compiled
from src.util import get_logger

logger = get_logger(__name__)

# Must equal ABI_VERSION in rust/src/lib.rs. Both are bumped by hand, in the same commit, whenever
# an accelerated function's signature or semantics change.
_REQUIRED_ABI_VERSION = 2


def check_abi_version(compiled, required=_REQUIRED_ABI_VERSION):
    """Return ``compiled`` if its ABI_VERSION matches ``required``, else raise RuntimeError.

    Separate from the import above so it can be tested against a stub module: building a genuinely
    stale extension to exercise this would mean compiling Rust inside a unit test.
    """
    found = getattr(compiled, "ABI_VERSION", None)
    if found != required:
        raise RuntimeError(
            f"The compiled Rust extension src/_accel is stale: it reports ABI_VERSION {found!r}, "
            f"but this checkout needs {required!r}. The extension is installed editable, so "
            f"pulling new Rust source does not rebuild it. Run "
            f"`uv sync --reinstall-package babel-pipeline`."
        )
    return compiled


# The compiled module, guaranteed present and current (both conditions raise otherwise).
accel = check_abi_version(_compiled)
logger.info("Using the Rust extension src/_accel (ABI_VERSION %s).", accel.ABI_VERSION)
