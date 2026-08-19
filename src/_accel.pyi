"""Type stub for the compiled Rust extension built from rust/src/lib.rs.

Hand-written and hand-maintained: there is no mypy in this repo, so nothing enforces that this
matches the Rust. It exists so a reader who does not read Rust can see what the module offers.
Import through src/accel.py rather than importing this module directly.
"""

from collections.abc import Iterable

# Bumped in lockstep with ABI_VERSION in rust/src/lib.rs; see src/accel.py.
ABI_VERSION: int

def glom(
    conc_set: dict,
    newgroups: Iterable,
    unique_prefixes: Iterable[str] | str | None = None,
    pref: str | None = None,
    close: dict | None = None,
) -> None:
    """Union-find that merges equivalence groups into ``conc_set`` **in place** (returns None).

    Drop-in replacement for the old Python ``babel_utils.glom``. ``conc_set`` maps each identifier
    to the set of equivalent identifiers it belongs to; ``newgroups`` is an iterable of 1–2 element
    groups (set/tuple/list/frozenset of ``str`` or ``LabeledID``). ``unique_prefixes`` (default
    ``["INCHIKEY"]``) is iterated like the Python did, so it may be a list/tuple/set of prefixes or
    a bare string; a clique may hold at most one member per such prefix, and a group that would
    violate this (or a ``close`` constraint) is skipped without adding its new members. A group
    containing a bare ``KEGG:``/``PUBCHEM:`` identifier raises. See rust/src/glom.rs for the
    algorithm.
    """
