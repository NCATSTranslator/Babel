"""Tests for raise_on_malformed_curies(), which write_compendium() uses to fail a build on malformed CURIEs."""

import pytest

from src.babel_utils import raise_on_malformed_curies


@pytest.mark.unit
def test_no_malformed_curies_does_not_raise():
    """Should do nothing when write_compendium() found no malformed CURIEs."""
    raise_on_malformed_curies([], "Protein.txt")


@pytest.mark.unit
def test_raises_naming_every_malformed_curie(caplog):
    """Should raise once with a per-prefix count and examples, and log every malformed CURIE, so a
    single failed run lists all of them rather than just the first."""
    malformed = [
        ("UniProtKB:P0DP24|P0DP23|P0DP25", "contains '|'", "UniProtKB:P0DP24|P0DP23|P0DP25"),
        ("UniProtKB:P0DTC1|P0DTD1", "contains '|'", "UniProtKB:P0DTC1|P0DTD1"),
        ("doi:10.3760/cma. j. issn.2095-4352. 2014. 07.015", "contains ' '", "PMID:25027433"),
    ]
    with pytest.raises(ValueError) as excinfo:
        raise_on_malformed_curies(malformed, "Protein.txt")
    message = str(excinfo.value)
    assert "3 malformed CURIE(s) in Protein.txt" in message
    assert "'UniProtKB': 2" in message and "'doi': 1" in message
    for curie, _, _ in malformed:
        assert repr(curie) in message
    logged = [r.getMessage() for r in caplog.records]
    assert all(any(repr(curie) in m for m in logged) for curie, _, _ in malformed)
