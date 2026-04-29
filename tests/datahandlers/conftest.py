"""Shared helpers for datahandler tests.

These are plain functions (not fixtures) so they can be imported by both unit tests
and pipeline tests without going through pytest's fixture injection machinery.
"""


def read_tsv(path: str) -> list[list[str]]:
    """Return non-empty lines of a TSV file split into columns."""
    rows = []
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                rows.append(line.split("\t"))
    return rows


def assert_labels_file_valid(path: str) -> list[list[str]]:
    """Assert every line is PREFIX:ID\\tLabel and return the rows."""
    rows = read_tsv(path)
    for cols in rows:
        assert len(cols) == 2, f"Expected 2 columns, got {len(cols)}: {cols}"
        assert ":" in cols[0], f"First column is not a CURIE: {cols[0]}"
    return rows


def assert_synonyms_file_valid(path: str) -> list[list[str]]:
    """Assert every line is PREFIX:ID\\tlabeltype\\tLabel and return the rows."""
    rows = read_tsv(path)
    for cols in rows:
        assert len(cols) == 3, f"Expected 3 columns, got {len(cols)}: {cols}"
        assert ":" in cols[0], f"First column is not a CURIE: {cols[0]}"
    return rows


def assert_ids_file_valid(path: str) -> list[list[str]]:
    """Assert every line is PREFIX:ID\\tbiolink:Category and return the rows."""
    rows = read_tsv(path)
    for cols in rows:
        assert len(cols) == 2, f"Expected 2 columns, got {len(cols)}: {cols}"
        assert ":" in cols[0], f"First column is not a CURIE: {cols[0]}"
    return rows


def assert_concordance_file_valid(path: str) -> list[list[str]]:
    """Assert every line is CURIE\\trelation\\tCURIE and return the rows."""
    rows = read_tsv(path)
    for cols in rows:
        assert len(cols) == 3, f"Expected 3 columns, got {len(cols)}: {cols}"
        assert ":" in cols[0], f"First column is not a CURIE: {cols[0]}"
        assert ":" in cols[2], f"Third column is not a CURIE: {cols[2]}"
    return rows
