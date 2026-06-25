import pytest

from src.babel_utils import parse_rdf_literal, reduce_to_most_specific_tree_codes


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


# Tree numbers borrowed from real MRSTY STN values (see src/datahandlers/umls.py).
_UMLS_TREES = {
    "T116": "A1.4.1.2.1.7",  # Amino Acid, Peptide, or Protein
    "T121": "A1.4.1.1.1",  # Pharmacologic Substance
    "T130": "A1.4.1.1.4",  # Indicator, Reagent, or Diagnostic Aid
    "T109": "A1.4.1.2.1",  # Organic Chemical  (ancestor of T116's A1.4.1.2.1.7)
    "T123": "A1.4.1.1.3",  # Biologically Active Substance (ancestor of T126)
    "T126": "A1.4.1.1.3.3",  # Enzyme
}


@pytest.mark.unit
@pytest.mark.parametrize(
    "codes,code_to_tree,expected",
    [
        # Empty input.
        (set(), _UMLS_TREES, set()),
        # Single code is always kept.
        ({"T116"}, _UMLS_TREES, {"T116"}),
        # Sibling/cousin TUIs in different subtrees all survive (the real C0000005 case).
        ({"T116", "T121", "T130"}, _UMLS_TREES, {"T116", "T121", "T130"}),
        # A proper ancestor is dropped in favor of its descendant: T109 (A1.4.1.2.1) is an
        # ancestor of T116 (A1.4.1.2.1.7).
        ({"T109", "T116"}, _UMLS_TREES, {"T116"}),
        # T123 (A1.4.1.1.3) is an ancestor of T126 (A1.4.1.1.3.3).
        ({"T123", "T126"}, _UMLS_TREES, {"T126"}),
        # Ancestor dropped, but an unrelated co-type stays.
        ({"T109", "T116", "T121"}, _UMLS_TREES, {"T116", "T121"}),
        # Component-boundary guard: "A1.2" is NOT an ancestor of "A1.20"; both survive.
        ({"X", "Y"}, {"X": "A1.2", "Y": "A1.20"}, {"X", "Y"}),
        # True dot-component ancestor "A1.2" of "A1.2.3" is dropped.
        ({"X", "Y"}, {"X": "A1.2", "Y": "A1.2.3"}, {"Y"}),
        # A code with no tree number has no ancestor relationship and is always kept.
        ({"X", "Y"}, {"Y": "A1.2.3"}, {"X", "Y"}),
    ],
)
def test_reduce_to_most_specific_tree_codes(codes, code_to_tree, expected):
    assert reduce_to_most_specific_tree_codes(codes, code_to_tree) == expected
