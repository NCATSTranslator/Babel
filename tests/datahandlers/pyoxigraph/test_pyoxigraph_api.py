"""Smoke tests for the pyoxigraph API surface used across all Babel datahandlers.

These tests exercise Store.bulk_load() and RdfFormat.* directly, which are bypassed
when other tests inject a pre-built store via ClassName.__new__().
"""
import io

import pyoxigraph
import pytest


def _store_from_bytes(data: bytes, fmt: pyoxigraph.RdfFormat, base_iri: str | None = None) -> pyoxigraph.Store:
    store = pyoxigraph.Store()
    kwargs = {"input": io.BytesIO(data), "format": fmt}
    if base_iri is not None:
        kwargs["base_iri"] = base_iri
    store.bulk_load(**kwargs)
    return store


@pytest.mark.unit
def test_bulk_load_rdf_xml():
    rdf = b"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
  <rdf:Description rdf:about="http://example.org/thing1">
    <rdfs:label>Thing One</rdfs:label>
  </rdf:Description>
</rdf:RDF>"""
    store = _store_from_bytes(rdf, pyoxigraph.RdfFormat.RDF_XML)
    results = list(store.query(
        "SELECT ?label WHERE { <http://example.org/thing1> <http://www.w3.org/2000/01/rdf-schema#label> ?label }"
    ))
    assert len(results) == 1
    assert str(results[0]["label"]) == '"Thing One"'


@pytest.mark.unit
def test_bulk_load_turtle():
    ttl = b"""@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://example.org/thing2> rdfs:label "Thing Two" .
"""
    store = _store_from_bytes(ttl, pyoxigraph.RdfFormat.TURTLE)
    results = list(store.query(
        "SELECT ?label WHERE { <http://example.org/thing2> <http://www.w3.org/2000/01/rdf-schema#label> ?label }"
    ))
    assert len(results) == 1
    assert str(results[0]["label"]) == '"Thing Two"'


@pytest.mark.unit
def test_bulk_load_n_triples():
    nt = (
        b'<http://example.org/s> <http://example.org/p> <http://example.org/o> .\n'
        b'<http://example.org/s> <http://www.w3.org/2000/01/rdf-schema#label> "Subject S" .\n'
        b'<http://example.org/o> <http://www.w3.org/2000/01/rdf-schema#label> "Object O" .\n'
    )
    store = _store_from_bytes(nt, pyoxigraph.RdfFormat.N_TRIPLES)
    assert len(list(store)) == 3

    results = list(store.query(
        "SELECT ?s WHERE { ?s <http://example.org/p> <http://example.org/o> }"
    ))
    assert len(results) == 1
    assert str(results[0]["s"]) == "<http://example.org/s>"

    label_results = list(store.query(
        "SELECT ?label WHERE { <http://example.org/s> <http://www.w3.org/2000/01/rdf-schema#label> ?label }"
    ))
    assert len(label_results) == 1
    assert str(label_results[0]["label"]) == '"Subject S"'

    obj_label_results = list(store.query(
        "SELECT ?label WHERE { <http://example.org/o> <http://www.w3.org/2000/01/rdf-schema#label> ?label }"
    ))
    assert len(obj_label_results) == 1
    assert str(obj_label_results[0]["label"]) == '"Object O"'


@pytest.mark.unit
def test_bulk_load_rdf_xml_with_base_iri():
    """base_iri is required when the file contains a relative IRI such as rdf:about="".

    EC, EFO, and CLO all include <owl:Ontology rdf:about=""/> which pyoxigraph cannot
    resolve without a base IRI.  Without one it raises SyntaxError; with one the file
    loads cleanly and the remaining triples are queryable.
    """
    rdf = b"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#">
  <owl:Ontology rdf:about=""/>
  <rdf:Description rdf:about="http://example.org/thing3">
    <rdf:type rdf:resource="http://example.org/Type"/>
  </rdf:Description>
</rdf:RDF>"""

    # Without base_iri the empty relative IRI in rdf:about="" cannot be resolved.
    with pytest.raises(SyntaxError, match="No scheme found in an absolute IRI"):
        _store_from_bytes(rdf, pyoxigraph.RdfFormat.RDF_XML)

    # With base_iri the relative IRI resolves and the substantive triples load correctly.
    store = _store_from_bytes(rdf, pyoxigraph.RdfFormat.RDF_XML, base_iri="http://example.org/")
    results = list(store.query(
        "SELECT ?s WHERE { ?s <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/Type> }"
    ))
    assert len(results) == 1
    assert str(results[0]["s"]) == "<http://example.org/thing3>"


@pytest.mark.unit
def test_sparql_query_row_access_by_name():
    """Verify that SPARQL result rows support row["varname"] access, used throughout Babel."""
    store = pyoxigraph.Store()
    store.add(pyoxigraph.Quad(
        pyoxigraph.NamedNode("http://example.org/s"),
        pyoxigraph.NamedNode("http://example.org/p"),
        pyoxigraph.Literal("hello"),
        pyoxigraph.DefaultGraph(),
    ))
    results = list(store.query("SELECT ?s ?o WHERE { ?s ?p ?o }"))
    assert len(results) == 1
    row = results[0]
    assert str(row["s"]) == "<http://example.org/s>"
    assert str(row["o"]) == '"hello"'
