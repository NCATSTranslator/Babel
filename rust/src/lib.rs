//! Native accelerators for babel-pipeline, importable as `from src import _accel`.
//!
//! A function lands here only once benchmarking justifies it (see README.md). Rust is the
//! implementation, not an optional overlay: there is no Python fallback and no runtime toggle. A
//! missing or stale build fails loudly at DAG-parse time (every snakefile imports `src.*`), which is
//! correct now that a Rust toolchain is a hard build prerequisite — see `src/accel.py`. Correctness
//! is guarded by the unit suite (which exercises these functions through their real callers) plus
//! targeted synthetic tests, not by a parallel Python copy kept in the tree.
//!
//! **The FFI boundary is coarse, and that is a rule, not a preference.** A `#[pyfunction]` here
//! takes a file path or a whole dataset and returns the whole result; it never takes one row.
//! Crossing pyo3 once per CURIE costs more than the Python it would replace, so a per-row entry
//! point would be slower while looking like an optimisation.
//!
//! **Parallelism.** Embarrassingly-parallel phases (interning, clique materialization) use rayon over
//! sharded maps so threads don't stall on one lock. Loops whose *order* is load-bearing — e.g. glom's
//! merge/reject decisions — stay sequential, because reordering them would change the output.

use pyo3::prelude::*;

mod glom;

/// Bumped by hand whenever a function's signature or semantics change, in the same commit.
///
/// `src/accel.py` compares this against its own `_REQUIRED_ABI_VERSION` at import time and raises
/// if they disagree. That matters because the extension is installed editable: the compiled
/// artifact sits in the checkout at `src/_accel.*.so` and a `git pull` does not rebuild it, so
/// without this check a stale binary would be used silently for a 12-hour rule.
///
// ponytail: a hand-bumped integer. Move to a build-time hash of this crate's sources if anyone
// forgets to bump it twice.
const ABI_VERSION: u32 = 2;

#[pymodule]
fn _accel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("ABI_VERSION", ABI_VERSION)?;
    m.add_function(wrap_pyfunction!(glom::glom, m)?)?;
    Ok(())
}
