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
    assert len(list(store)) > 0


@pytest.mark.unit
def test_bulk_load_turtle():
    ttl = b"""@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://example.org/thing2> rdfs:label "Thing Two" .
"""
    store = _store_from_bytes(ttl, pyoxigraph.RdfFormat.TURTLE)
    assert len(list(store)) > 0


@pytest.mark.unit
def test_bulk_load_n_triples():
    nt = b'<http://example.org/s> <http://example.org/p> <http://example.org/o> .\n'
    store = _store_from_bytes(nt, pyoxigraph.RdfFormat.N_TRIPLES)
    assert len(list(store)) > 0


@pytest.mark.unit
def test_bulk_load_rdf_xml_with_base_iri():
    """The base_iri workaround is used by EC, EFO, and CLO handlers for malformed Ontology elements."""
    rdf = b"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#">
  <owl:Ontology rdf:about=""/>
  <rdf:Description rdf:about="http://example.org/thing3">
    <rdf:type rdf:resource="http://example.org/Type"/>
  </rdf:Description>
</rdf:RDF>"""
    store = _store_from_bytes(rdf, pyoxigraph.RdfFormat.RDF_XML, base_iri="http://example.org/")
    assert len(list(store)) > 0


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
