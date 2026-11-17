"""Tests for src.babel_utils.remove_overused_xrefs(), beyond the scoping tests in test_diseasephenotype.py."""

import pytest

from src.babel_utils import remove_overused_xrefs

# MEMORY


@pytest.mark.unit
@pytest.mark.parametrize("bothways", [False, True])
def test_surviving_pairs_are_the_callers_own_objects(bothways):
    """Should return the very pair objects it was given, not rebuilt copies.

    Callers keep the unfiltered list alive while this runs, so a rebuilt (k, v) per survivor doubles
    the tuples held at peak on a large concord.
    """
    # X:1 is claimed twice (dropped either way); A:3 claims twice (dropped only with bothways).
    pairs = [("A:1", "X:1"), ("A:2", "X:1"), ("A:3", "X:2"), ("A:3", "X:3"), ("A:4", "X:4")]
    kept = remove_overused_xrefs(pairs, bothways=bothways)
    assert kept == ([pairs[4]] if bothways else pairs[2:])
    assert all(any(k is p for p in pairs) for k in kept)


@pytest.mark.unit
def test_out_of_scope_pairs_are_the_callers_own_objects():
    """Should return the caller's own pair object for a target outside target_prefixes, too."""
    pairs = [("A:1", "X:1"), ("A:2", "X:1")]
    kept = remove_overused_xrefs(pairs, target_prefixes=["Y"])
    assert kept == pairs
    assert all(k is p for k, p in zip(kept, pairs, strict=True))
