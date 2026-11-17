"""Tests for how write_compendium() fails a build on malformed CURIEs (see raise_on_malformed_curies())."""

import pytest

import src.babel_utils as babel_utils
from src.babel_utils import raise_on_malformed_curies
from src.categories import PROTEIN


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


# WIRING INTO write_compendium()


def _write(cliques):
    babel_utils.write_compendium([], cliques, "Protein.txt", PROTEIN, icrdf_filename="icRDF.tsv")


@pytest.mark.unit
def test_write_compendium_raises_on_malformed_clique_member_and_alternative_id(fake_write_compendium_env):
    """Should raise after writing every clique, naming both a malformed clique member (as shipped in
    babel-1.18, #1109) and a malformed HAS_ALTERNATIVE_ID CURIE from a different clique."""
    cliques = [
        {"UniProtKB:P0DP24|P0DP23|P0DP25", "UMLS:C1366910"},
        {"NCIT:C16375"},
        {"UniProtKB:P0DP24", "PR:P0DP24"},
    ]
    with pytest.raises(ValueError) as excinfo:
        _write(cliques)
    assert "'UniProtKB:P0DP24|P0DP23|P0DP25'" in str(excinfo.value)
    assert "'NCIT:C16375 extra'" in str(excinfo.value)
    written = (fake_write_compendium_env / "compendia" / "Protein.txt").read_text().splitlines()
    assert len(written) == 3


@pytest.mark.unit
def test_write_compendium_accepts_well_formed_curies(fake_write_compendium_env):
    """Should write a compendium of well-formed CURIEs without raising."""
    _write([{"UniProtKB:P0DP24", "PR:P0DP24"}, {"UniProtKB:P0DP24-1"}])
    assert len((fake_write_compendium_env / "compendia" / "Protein.txt").read_text().splitlines()) == 2
