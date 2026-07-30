"""Type stub for the compiled Rust extension built from rust/src/lib.rs.

Hand-written and hand-maintained: there is no mypy in this repo, so nothing enforces that this
matches the Rust. It exists so a reader who does not read Rust can see what the module offers.
Import through src/accel.py rather than importing this module directly.
"""

# Bumped in lockstep with ABI_VERSION in rust/src/lib.rs; see src/accel.py.
ABI_VERSION: int
