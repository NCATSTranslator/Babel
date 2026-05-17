"""Shared pyoxigraph construction helpers for datahandler tests.

These are plain functions (not fixtures) so they can be imported by both unit tests
and pipeline tests without going through pytest's fixture injection machinery.

TSV output assertion helpers (read_tsv, assert_labels_file_valid, etc.) live in
tests/conftest.py so they are accessible to pipeline tests as well.
"""
import pyoxigraph

# ---------------------------------------------------------------------------
# pyoxigraph construction helpers
# ---------------------------------------------------------------------------


def nn(iri: str) -> pyoxigraph.NamedNode:
    return pyoxigraph.NamedNode(iri)


def lit(val: str, language: str | None = None) -> pyoxigraph.Literal:
    if language:
        return pyoxigraph.Literal(val, language=language)
    return pyoxigraph.Literal(val)


def quad(s, p, o) -> pyoxigraph.Quad:
    return pyoxigraph.Quad(s, p, o, pyoxigraph.DefaultGraph())
