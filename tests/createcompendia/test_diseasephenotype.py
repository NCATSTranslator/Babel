"""
Unit tests for src/createcompendia/diseasephenotype.py.

These exercise the UMLS semantic-type-tree → Biolink category map that
``write_umls_ids`` hands to ``umls.write_umls_ids``. The map is built inline,
so we capture it by mocking the downstream ``umls.write_umls_ids`` call rather
than running a real MRSTY parse -- keeping these tests fast and offline.
"""

from collections import defaultdict
from unittest.mock import patch

import pytest

from src.babel_utils import glom
from src.categories import DISEASE, PHENOTYPIC_FEATURE
from src.createcompendia import diseasephenotype
from src.prefixes import HP, MEDDRA, MONDO


def _capture_umlsmap(tmp_path):
    """Run write_umls_ids with the downstream call mocked, returning the category map it built."""
    badumlsfile = tmp_path / "badumls.txt"
    badumlsfile.write_text("# no blocked CUIs\n")
    with patch.object(diseasephenotype.umls, "write_umls_ids") as mock_write:
        diseasephenotype.write_umls_ids(
            mrsty=str(tmp_path / "MRSTY.RRF"),  # never read: write_umls_ids is mocked
            outfile=str(tmp_path / "out"),
            badumlsfile=str(badumlsfile),
        )
    assert mock_write.call_count == 1, "expected diseasephenotype to delegate to umls.write_umls_ids exactly once"
    # umls.write_umls_ids(mrsty, category_map, outfile, ...): the map is the 2nd positional arg.
    return mock_write.call_args.args[1]


@pytest.mark.unit
def test_finding_and_lab_result_trees_are_not_claimed(tmp_path):
    """
    Regression guard for #569: the disease/phenotype compendium must NOT claim UMLS
    "Finding" (A2.2 / T033) or "Laboratory or Test Result" (A2.2.1 / T034). Leaving them
    unmapped is what lets them fall through to the leftover UMLS sweep, where STY_OVERRIDES
    re-types them (T033 → biolink:Phenomenon, T034 → biolink:ClinicalFinding). If either
    tree is re-added here the override never fires, so fail loudly.
    """
    umlsmap = _capture_umlsmap(tmp_path)
    assert "A2.2" not in umlsmap, 'A2.2 "Finding" (T033) must stay unclaimed so leftover re-types it -- see #569'
    assert "A2.2.1" not in umlsmap, (
        'A2.2.1 "Lab/Test Result" (T034) must stay unclaimed so leftover re-types it -- see #569'
    )


@pytest.mark.unit
def test_phenotype_trees_remain_claimed(tmp_path):
    """A2.2.2 (Sign or Symptom) and A2.3 (Organism Attribute) genuinely are phenotypic features."""
    umlsmap = _capture_umlsmap(tmp_path)
    assert umlsmap.get("A2.2.2") == PHENOTYPIC_FEATURE
    assert umlsmap.get("A2.3") == PHENOTYPIC_FEATURE


@pytest.mark.unit
def test_disease_trees_remain_claimed(tmp_path):
    """The core disease semantic-type trees must still map to biolink:Disease."""
    umlsmap = _capture_umlsmap(tmp_path)
    for tree in [
        "B2.2.1.2.1",
        "A1.2.2.1",
        "A1.2.2.2",
        "B2.3",
        "B2.2.1.2",
        "B2.2.1.2.1.1",
        "B2.2.1.2.2",
        "A1.2.2",
        "B2.2.1.2.1.2",
    ]:
        assert umlsmap.get(tree) == DISEASE, f"{tree} should map to {DISEASE}"


# ----------------------------------------------------------------------------------------------
# MONDO CLOSE-MATCH GUARD
#
# MONDO_close is a 3-column concord (subject, predicate, object). load_close_mondos must key each
# MONDO subject to its close-match *objects* (column 3) so glom()'s close= guard can block a close
# (but not exact) match from collapsing into the exact MONDO clique. Keying on the predicate
# (column 2) leaves the guard a silent no-op -- the bug these tests exist to prevent recurring.
# ----------------------------------------------------------------------------------------------


@pytest.mark.unit
def test_load_close_mondos_keys_on_object(tmp_path):
    """A 3-column MONDO_close row should map the MONDO subject to the close-match object CURIE,
    never to the predicate string in column 2 -- keying on the predicate is what silently disabled
    the guard."""
    mondoclose = tmp_path / "MONDO_close"
    mondoclose.write_text(
        f"{MONDO}:0000739\toio:closeMatch\t{MEDDRA}:10051962\n"
        f"{MONDO}:0000739\toio:closeMatch\t{MEDDRA}:99999999\n"
        f"{MONDO}:0005148\toio:closeMatch\t{MEDDRA}:10012601\n"
    )
    close_mondos = diseasephenotype.load_close_mondos(str(mondoclose))
    assert close_mondos[f"{MONDO}:0000739"] == {f"{MEDDRA}:10051962", f"{MEDDRA}:99999999"}
    assert close_mondos[f"{MONDO}:0005148"] == {f"{MEDDRA}:10012601"}
    # The predicate must never leak into the recorded close-match values.
    for objects in close_mondos.values():
        assert "oio:closeMatch" not in objects


@pytest.mark.unit
def test_load_close_mondos_skips_blank_and_rejects_malformed(tmp_path):
    """Blank lines should be skipped; a row that is not exactly 3 columns should raise
    RuntimeError so a malformed MONDO_close file fails loudly instead of corrupting the guard."""
    ok = tmp_path / "ok"
    ok.write_text(f"\n{MONDO}:0000739\toio:closeMatch\t{MEDDRA}:10051962\n\n")
    assert diseasephenotype.load_close_mondos(str(ok)) == {f"{MONDO}:0000739": {f"{MEDDRA}:10051962"}}

    bad = tmp_path / "bad"
    bad.write_text(f"{MONDO}:0000739\t{MEDDRA}:10051962\n")  # only 2 columns
    with pytest.raises(RuntimeError, match="not a valid MONDO_close entry"):
        diseasephenotype.load_close_mondos(str(bad))


@pytest.mark.unit
def test_close_guard_blocks_close_match_merge(tmp_path):
    """End-to-end: with close_mondos loaded from a real 3-column file, glom must refuse to merge a
    MONDO term with a MEDDRA term recorded only as its *close* (not exact) match."""
    mondoclose = tmp_path / "MONDO_close"
    mondoclose.write_text(f"{MONDO}:0000739\toio:closeMatch\t{MEDDRA}:10051962\n")
    close_mondos = diseasephenotype.load_close_mondos(str(mondoclose))

    conc_set = {}
    glom(conc_set, [[f"{MONDO}:0000739"], [f"{MEDDRA}:10051962"]], unique_prefixes=[MONDO, HP])
    # A concord pair that would otherwise merge them:
    glom(
        conc_set,
        [[f"{MONDO}:0000739", f"{MEDDRA}:10051962"]],
        unique_prefixes=[MONDO, HP],
        close={MONDO: close_mondos},
    )
    assert f"{MEDDRA}:10051962" not in conc_set[f"{MONDO}:0000739"], (
        "a close-match MEDDRA term must not collapse into the exact MONDO clique"
    )


@pytest.mark.unit
def test_predicate_keyed_close_dict_is_a_noop(tmp_path):
    """Documents the original bug: a close dict keyed on the predicate (column 2) records a value
    no clique ever contains, so glom's guard never fires and the close match merges in anyway."""
    predicate_keyed = defaultdict(set)
    predicate_keyed[f"{MONDO}:0000739"].add("oio:closeMatch")  # the pre-fix behaviour

    conc_set = {}
    glom(conc_set, [[f"{MONDO}:0000739"], [f"{MEDDRA}:10051962"]], unique_prefixes=[MONDO, HP])
    glom(
        conc_set,
        [[f"{MONDO}:0000739", f"{MEDDRA}:10051962"]],
        unique_prefixes=[MONDO, HP],
        close={MONDO: predicate_keyed},
    )
    assert f"{MEDDRA}:10051962" in conc_set[f"{MONDO}:0000739"], (
        "predicate-keyed close dict leaves the guard a no-op, so the merge goes through"
    )
