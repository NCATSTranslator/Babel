import pytest

from src.babel_utils import parse_rdf_literal


@pytest.mark.unit
@pytest.mark.parametrize(
    "literal,expected",
    [
        # Plain quoted literal — most common pyoxigraph SPARQL result form
        ('"Hello"', "Hello"),
        ('""', ""),
        ('"multiple words"', "multiple words"),
        # Language-tagged literals
        ('"Hello"@en', "Hello"),
        ('"Hola"@es', "Hola"),
        ('"Hello"@en_US', "Hello"),
        ('""@en', ""),
        # Non-quoted pass-through (numeric, IRI, plain string)
        ("42", "42"),
        ("<http://example.org/>", "<http://example.org/>"),
        ("plain", "plain"),
    ],
)
def test_parse_rdf_literal(literal, expected):
    assert parse_rdf_literal(literal) == expected
