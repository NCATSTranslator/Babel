"""Unit tests for src/createcompendia/processactivitypathway.py."""

import pytest

from src.categories import BIOLOGICAL_PROCESS, DISEASE, MOLECULAR_ACTIVITY, PATHWAY
from src.createcompendia.processactivitypathway import (
    _process_concord_pair_drop_reason,
    classify_process_clique,
    compute_cliques_for_impact_report,
)

# CONCORD PAIR FILTER


@pytest.mark.unit
@pytest.mark.parametrize("pair", [("GO:0034227", "EC:2.8.1.4"), ("EC:2.8.1.4", "GO:0034227")])
def test_concord_pair_filter_drops_bad_concords(pair):
    """A BAD_CONCORDS pair should be dropped whichever way round the concord writes it."""
    assert _process_concord_pair_drop_reason([pair[0], "xref", pair[1]], "concords/GO", {}) == "listed in BAD_CONCORDS"


@pytest.mark.unit
def test_concord_pair_filter_keeps_other_pairs():
    """Any other non-UMLS pair should be kept, even when neither CURIE is in the clique state yet."""
    assert _process_concord_pair_drop_reason(["GO:0140741", "xref", "EC:2.8.1.4"], "concords/GO", {}) is None


@pytest.mark.unit
def test_concord_pair_filter_requires_known_umls_pair():
    """A UMLS concord pair should be kept only when both CURIEs are already in the clique state."""
    parts = ["UMLS:C1158785", "eq", "GO:0045943"]
    assert _process_concord_pair_drop_reason(parts, "concords/UMLS", {"UMLS:C1158785": set()}) is not None
    assert (
        _process_concord_pair_drop_reason(parts, "concords/UMLS", {"UMLS:C1158785": set(), "GO:0045943": set()}) is None
    )


# CLIQUES


@pytest.mark.unit
def test_compute_cliques_logs_dropped_pairs_and_skips_them(tmp_path, caplog):
    """The UMLS gate and BAD_CONCORDS should drop their pairs, with one log line per file and reason."""
    ids = tmp_path / "ids" / "GO"
    ids.parent.mkdir()
    ids.write_text(f"GO:0034227\t{BIOLOGICAL_PROCESS}\nGO:0045943\t{BIOLOGICAL_PROCESS}\nUMLS:C1158785\n")
    concords = tmp_path / "concords"
    concords.mkdir()
    (concords / "RHEA").write_text("GO:0034227\txref\tEC:2.8.1.4\n")
    (concords / "UMLS").write_text("UMLS:C1158785\teq\tGO:0045943\nUMLS:C2249862\teq\tGO:0045943\n")

    with caplog.at_level("INFO", logger="src.createcompendia.processactivitypathway"):
        dicts, _ = compute_cliques_for_impact_report(
            [str(concords / "RHEA"), str(concords / "UMLS")], [str(ids)], mesh_ownership="ignored"
        )

    assert dicts["UMLS:C1158785"] == {"UMLS:C1158785", "GO:0045943"}
    assert "UMLS:C2249862" not in dicts
    assert "EC:2.8.1.4" not in dicts
    assert f"dropped 1 concord pairs from {concords / 'RHEA'}: listed in BAD_CONCORDS" in caplog.text
    assert f"dropped 1 concord pairs from {concords / 'UMLS'}: UMLS pair" in caplog.text


@pytest.mark.unit
def test_classify_process_clique():
    """GO's declared type should win; otherwise a majority vote, with ties broken Pathway first."""
    types = {"GO:1": MOLECULAR_ACTIVITY, "REACT:1": PATHWAY, "REACT:2": PATHWAY, "UMLS:1": BIOLOGICAL_PROCESS}
    assert classify_process_clique({"GO:1", "REACT:1", "REACT:2"}, types) == MOLECULAR_ACTIVITY
    assert classify_process_clique({"REACT:1", "REACT:2", "UMLS:1"}, types) == PATHWAY
    assert classify_process_clique({"REACT:1", "UMLS:1"}, types) == PATHWAY
    assert classify_process_clique({"UMLS:2"}, types) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "clique,types,message",
    [
        pytest.param(
            {"GO:1", "REACT:1"}, {"REACT:1": PATHWAY}, "GO term GO:1 .* has no declared type", id="untyped-go"
        ),
        pytest.param(
            {"REACT:1", "UMLS:1"},
            {"REACT:1": PATHWAY, "UMLS:1": DISEASE},
            rf"declared \['{DISEASE}'\]",
            id="vote-with-unexpected-type",
        ),
    ],
)
def test_classify_process_clique_raises_on_untypable_input(clique, types, message):
    """A clique the pipeline cannot type should raise a ValueError naming the problem, not a bare KeyError or the
    ValueError of a failed list.index()."""
    with pytest.raises(ValueError, match=message):
        classify_process_clique(clique, types)
