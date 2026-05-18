"""Shared pyoxigraph construction helpers for datahandler tests.

These are plain functions (not fixtures) so they can be imported by both unit tests
and pipeline tests without going through pytest's fixture injection machinery.

TSV output assertion helpers (read_tsv, assert_labels_file_valid, etc.) live in
tests/conftest.py so they are accessible to pipeline tests as well.
"""
import pyoxigraph

# ---------------------------------------------------------------------------
# Common RDF namespace strings (reused across multiple handler test modules)
# ---------------------------------------------------------------------------

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"

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


def make_graph_from_store(cls, store: pyoxigraph.Store, **attrs):
    """Construct a datahandler graph object with a pre-built store, bypassing __init__.

    Each handler's __init__ loads a file from disk.  Tests inject an in-memory store
    by constructing the object with __new__ and setting obj.m directly.  This helper
    centralises that pattern so individual test modules don't repeat it.

    Extra keyword arguments are set as additional attributes (e.g. filename="foo.rdf"
    for Rhea, which stores the source path alongside the store).
    """
    obj = cls.__new__(cls)
    obj.m = store
    for key, val in attrs.items():
        setattr(obj, key, val)
    return obj
