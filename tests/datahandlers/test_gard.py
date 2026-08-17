"""Unit tests for src.datahandlers/gard.py (NCATS GARD rare-disease registry).

The fixture `tests/data/gard_sample.csv` holds two rows copied verbatim from the GARD distribution
CSV (BOM + CRLF, as published): one term with pipe-separated synonyms
([`GARD:0021052`](https://rarediseases.info.nih.gov/?gard_id=0021052)) and one with neither
synonyms nor a URL ([`GARD:0027416`](https://rarediseases.info.nih.gov/?gard_id=0027416)) -- both
are kept, since the presence of a `URL` is not a reliable signal that a row is a real rare disease
(a term may simply lack a GARD page). Re-derive either row from the `gard_download_url` in
`config.yaml`.
"""

import csv
from pathlib import Path

import pytest

from src.categories import DISEASE
from src.datahandlers.gard import normalize_gard_curie, pull_gard_labels_and_synonyms
from src.node import NodeFactory
from src.prefixes import GARD, OIO
from src.util import get_biolink_model_toolkit, get_config
from tests.conftest import assert_labels_file_valid, assert_synonyms_file_valid

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "gard_sample.csv"

# Verbatim rows from the GARD distribution CSV. The distribution zero-pads local ids to seven
# digits; Babel emits the unpadded form (what DOID's xrefs use), so the expected output ids drop
# the padding the fixture carries.
_WITH_SYNS = "GARD:21052"  # published as GARD:0021052; has a URL + pipe-separated synonyms
_WITH_SYNS_NAME = "10q22.3q23.3 microduplication syndrome"
_WITH_SYNS_SYNS = ["dup(10)(q22.3q23.3)", "trisomy 10q22.3q23.3"]
_NO_SYNS = "GARD:27416"  # published as GARD:0027416; no synonyms and no URL -- still kept
_NO_SYNS_NAME = "10p13-p14 deletion syndrome"


@pytest.mark.unit
def test_pull_gard_labels_and_synonyms_writes_label_and_synonyms(tmp_path):
    """The DisplayName is written as a label and as an exact synonym, and each pipe-separated
    synonym becomes its own exact-synonym row. Rows without a URL are kept -- a missing GARD page
    does not mean the term is not a rare disease."""
    labels = str(tmp_path / "labels")
    syns = str(tmp_path / "synonyms")
    pull_gard_labels_and_synonyms(str(FIXTURE), labels, syns)

    label_rows = assert_labels_file_valid(labels)
    syn_rows = assert_synonyms_file_valid(syns)

    # Both terms get a label row (GARD:<id>\t<name>), including the no-synonym, no-URL term.
    label_map = {r[0]: r[1] for r in label_rows}
    assert label_map[_WITH_SYNS] == _WITH_SYNS_NAME
    assert label_map[_NO_SYNS] == _NO_SYNS_NAME

    # The term with synonyms: DisplayName as an exact synonym, plus each pipe-split synonym.
    assert [_WITH_SYNS, f"{OIO}:hasExactSynonym", _WITH_SYNS_NAME] in syn_rows
    for syn in _WITH_SYNS_SYNS:
        assert [_WITH_SYNS, f"{OIO}:hasExactSynonym", syn] in syn_rows

    # The no-synonym term gets exactly one synonym row (its DisplayName); no pipe-split rows.
    no_syn_rows = [r for r in syn_rows if r[0] == _NO_SYNS]
    assert no_syn_rows == [[_NO_SYNS, f"{OIO}:hasExactSynonym", _NO_SYNS_NAME]]


@pytest.mark.unit
def test_pull_gard_labels_and_synonyms_skips_non_gard_rows(tmp_path):
    """A row whose ID is not a ``GARD:`` CURIE (a malformed/trailing row the registry does not
    actually contain) is skipped, so only real GARD terms reach the labels/synonyms files.

    This is a defensive-branch test over a synthetic CSV (not a verbatim GARD record), built in
    the test so the skip path is genuinely exercised rather than trivially true against the
    GARD-only fixture. The ``URL`` column is intentionally left empty to confirm it does not gate
    inclusion.
    """
    synth = tmp_path / "synthetic.csv"
    synth.write_text(
        "ID,DisplayName,Synonyms,URL\n"
        "GARD:0000001,Real rare disease,,\n"
        "BOGUS:9999,Should be skipped,,\n"
        ",No id either,,\n",
        encoding="utf-8",
    )
    labels = str(tmp_path / "labels")
    syns = str(tmp_path / "synonyms")
    pull_gard_labels_and_synonyms(str(synth), labels, syns)

    label_rows = assert_labels_file_valid(labels)
    syn_rows = assert_synonyms_file_valid(syns)
    assert [r[0] for r in label_rows] == ["GARD:1"]
    assert all(r[0] == "GARD:1" for r in syn_rows)


# --- local-id form -------------------------------------------------------------
#
# The registry publishes GARD:0006038; DOID xrefs GARD:6038. Babel standardizes on the unpadded
# form, so the same rare disease is one identifier rather than two cliques.


@pytest.mark.unit
@pytest.mark.parametrize(
    "curie,expected",
    [
        ("GARD:0006038", "GARD:6038"),  # verbatim registry form for "Chikungunya fever"
        ("GARD:6038", "GARD:6038"),  # verbatim DOID:0050012 xref form -- already unpadded
        ("GARD:0000072", "GARD:72"),
        ("MONDO:0005084", "MONDO:0005084"),  # non-GARD CURIEs are untouched, zero-padding and all
        ("GARD:not-a-number", "GARD:not-a-number"),  # never seen; must not mangle
    ],
)
def test_normalize_gard_curie(curie, expected):
    """Zero-padding is stripped from GARD local ids only; everything else passes through."""
    assert normalize_gard_curie(curie) == expected


# --- ingest guards -------------------------------------------------------------
#
# A silently zeroed GARD ingest drops ~16k rare diseases from a build that still exits green, so
# the parser raises rather than logging (AGENTS.md: "A log warning is not a control").


@pytest.mark.unit
def test_pull_gard_labels_and_synonyms_raises_on_renamed_header(tmp_path):
    """An NCATS column rename must raise, not write an empty labels file."""
    synth = tmp_path / "renamed.csv"
    synth.write_text("GardId,Name,Synonyms,URL\nGARD:0000001,Real rare disease,,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing expected column"):
        pull_gard_labels_and_synonyms(str(synth), str(tmp_path / "labels"), str(tmp_path / "synonyms"))


@pytest.mark.unit
@pytest.mark.parametrize("bad_value", ["Rare\tdisease", "Rare\ndisease"])
def test_pull_gard_labels_and_synonyms_raises_on_tsv_control_chars(tmp_path, bad_value):
    """A tab or newline in a name would split one TSV record into two malformed ones, so the
    writer rejects it rather than trusting that no future GARD distribution introduces one."""
    synth = tmp_path / "control_chars.csv"
    with open(synth, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["ID", "DisplayName", "Synonyms", "URL"], ["GARD:0000001", bad_value, "", ""]])
    with pytest.raises(ValueError, match="tab or newline"):
        pull_gard_labels_and_synonyms(str(synth), str(tmp_path / "labels"), str(tmp_path / "synonyms"))


@pytest.mark.unit
def test_pull_gard_labels_and_synonyms_raises_when_no_terms_parsed(tmp_path):
    """A CSV with the right headers but no usable GARD rows must raise."""
    synth = tmp_path / "empty.csv"
    synth.write_text("ID,DisplayName,Synonyms,URL\nBOGUS:9999,Not a GARD term,,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="yielded no terms"):
        pull_gard_labels_and_synonyms(str(synth), str(tmp_path / "labels"), str(tmp_path / "synonyms"))


# --- extra_prefixes regression -------------------------------------------------
#
# GARD is not in the Biolink Model's `disease` id_prefixes, so the disease compendium build passes
# extra_prefixes=[GARD] at its write_compendium call site (src/createcompendia/diseasephenotype.py).
# These two tests lock that linchpin in: the first asserts the precondition that makes the escape
# hatch necessary (and flips to prompt removing the line once GARD is registered upstream); the
# second asserts NodeFactory tolerates extra_prefixes=[GARD] for biolink:Disease without raising
# (the failure mode the leftover-UMLS analogue catches in test_leftover_umls.py). Both are
# network-marked because building the Biolink Model Toolkit fetches biolink-model.yaml on first
# use (for the biolink_version pinned in config.yaml).


@pytest.mark.network
def test_gard_not_in_biolink_disease_id_prefixes():
    """GARD is not in the Biolink Model's `disease` `id_prefixes` for the pinned biolink_version.

    This is why extra_prefixes=[GARD] is required. When GARD is registered upstream this assertion
    fails -- drop the extra_prefixes=[GARD] line in diseasephenotype.py and update the GARD docs.
    """
    tk = get_biolink_model_toolkit(get_config()["biolink_version"])
    assert "GARD" not in tk.get_element("disease").id_prefixes


@pytest.mark.network
def test_disease_node_factory_tolerates_extra_prefixes_gard():
    """NodeFactory.create_node() for biolink:Disease must not raise when given extra_prefixes=[GARD]
    (the disease build's escape hatch). Mirrors test_all_override_target_types_are_writable in
    tests/createcompendia/test_leftover_umls.py."""
    factory = NodeFactory(label_dir=None, biolink_version=get_config()["biolink_version"])
    # Must not raise. Returns None because input_identifiers is empty.
    factory.create_node(input_identifiers=[], node_type=DISEASE, labels={}, extra_prefixes=[GARD])
