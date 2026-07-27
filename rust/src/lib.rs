//! Placeholder native extension for babel-pipeline.
//!
//! The build backend is maturin; this empty module exists only so the project builds as a
//! mixed Rust/Python package. Real functionality will land in a follow-up PR.

use pyo3::prelude::*;

/// Empty pyo3 module, importable as `from src import rs`. Name must match the last component
/// of `[tool.maturin] module-name` ("src.rs" → `rs`).
#[pymodule]
fn rs(_m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}
