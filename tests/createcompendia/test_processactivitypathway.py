"""Unit tests for src/createcompendia/processactivitypathway.py."""

import pytest

from src.categories import BIOLOGICAL_PROCESS, MOLECULAR_ACTIVITY, PATHWAY
from src.createcompendia.processactivitypathway import _process_concord_pair_filter, classify_process_clique

# CONCORD PAIR FILTER


@pytest.mark.unit
@pytest.mark.parametrize("pair", [("GO:0034227", "EC:2.8.1.4"), ("EC:2.8.1.4", "GO:0034227")])
def test_concord_pair_filter_drops_bad_concords(pair):
    """A BAD_CONCORDS pair should be dropped whichever way round the concord writes it."""
    assert not _process_concord_pair_filter([pair[0], "xref", pair[1]], "concords/GO", {})


@pytest.mark.unit
def test_concord_pair_filter_keeps_other_pairs():
    """Any other non-UMLS pair should be kept, even when neither CURIE is in the clique state yet."""
    assert _process_concord_pair_filter(["GO:0140741", "xref", "EC:2.8.1.4"], "concords/GO", {})


@pytest.mark.unit
def test_concord_pair_filter_requires_known_umls_pair():
    """A UMLS concord pair should be kept only when both CURIEs are already in the clique state."""
    parts = ["UMLS:C1158785", "eq", "GO:0045943"]
    assert not _process_concord_pair_filter(parts, "concords/UMLS", {"UMLS:C1158785": set()})
    assert _process_concord_pair_filter(parts, "concords/UMLS", {"UMLS:C1158785": set(), "GO:0045943": set()})


# CLIQUE TYPING


@pytest.mark.unit
def test_classify_process_clique():
    """GO's declared type should win; otherwise a majority vote, with ties broken Pathway first."""
    types = {"GO:1": MOLECULAR_ACTIVITY, "REACT:1": PATHWAY, "REACT:2": PATHWAY, "UMLS:1": BIOLOGICAL_PROCESS}
    assert classify_process_clique({"GO:1", "REACT:1", "REACT:2"}, types) == MOLECULAR_ACTIVITY
    assert classify_process_clique({"REACT:1", "REACT:2", "UMLS:1"}, types) == PATHWAY
    assert classify_process_clique({"REACT:1", "UMLS:1"}, types) == PATHWAY
    assert classify_process_clique({"UMLS:2"}, types) is None
