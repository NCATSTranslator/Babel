"""Unit tests for src.datahandlers/gard.py (NCATS GARD rare-disease registry).

The fixture `tests/data/gard_sample.csv` holds two rows copied verbatim from the GARD distribution
CSV (BOM + CRLF, as published): one real rare disease with a URL + pipe-separated synonyms
([`GARD:0021052`](https://rarediseases.info.nih.gov/?gard_id=0021052)) and one with no URL
([`GARD:0027416`](https://rarediseases.info.nih.gov/?gard_id=0027416)), which is excluded because
a GARD term with no public page is not a real rare disease. Re-derive either row from the
`gard_download_url` in `config.yaml`.
"""

from pathlib import Path

import pytest

from src.categories import DISEASE
from src.datahandlers.gard import pull_gard_labels_and_synonyms
from src.node import NodeFactory
from src.prefixes import GARD, OIO
from src.util import get_biolink_model_toolkit, get_config
from tests.conftest import assert_labels_file_valid, assert_synonyms_file_valid

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "gard_sample.csv"

# Verbatim rows from the GARD distribution CSV.
_KEPT = "GARD:0021052"  # has a URL + synonyms -> kept
_KEPT_NAME = "10q22.3q23.3 microduplication syndrome"
_KEPT_SYNS = ["dup(10)(q22.3q23.3)", "trisomy 10q22.3q23.3"]
_EXCLUDED_NO_URL = "GARD:0027416"  # no URL -> not a real rare disease, excluded


@pytest.mark.unit
def test_pull_gard_labels_and_synonyms_keeps_url_rows_excludes_no_url(tmp_path):
    """A GARD term with a URL is kept (label + the DisplayName and each pipe-split synonym as
    exact synonyms); a GARD term with no URL is excluded entirely -- it is not a real rare
    disease."""
    labels = str(tmp_path / "labels")
    syns = str(tmp_path / "synonyms")
    pull_gard_labels_and_synonyms(str(FIXTURE), labels, syns)

    label_rows = assert_labels_file_valid(labels)
    syn_rows = assert_synonyms_file_valid(syns)

    # The URL-bearing term is kept: it gets a label row.
    label_map = {r[0]: r[1] for r in label_rows}
    assert label_map[_KEPT] == _KEPT_NAME

    # The DisplayName is emitted as an exact synonym, and each pipe-split synonym is its own row.
    assert [_KEPT, f"{OIO}:hasExactSynonym", _KEPT_NAME] in syn_rows
    for syn in _KEPT_SYNS:
        assert [_KEPT, f"{OIO}:hasExactSynonym", syn] in syn_rows

    # The no-URL term is excluded: it appears in neither labels nor synonyms.
    assert _EXCLUDED_NO_URL not in {r[0] for r in label_rows}
    assert _EXCLUDED_NO_URL not in {r[0] for r in syn_rows}


@pytest.mark.unit
def test_pull_gard_labels_and_synonyms_skips_non_gard_and_no_url_rows(tmp_path):
    """Only a real GARD term (``GARD:`` id *and* a URL) reaches the labels/synonyms files; a
    non-``GARD:`` id, a ``GARD:`` id with no URL, and a row with no id at all are all skipped.

    This is a defensive-branch test over a synthetic CSV (not a verbatim GARD record), built in
    the test so the skip paths are genuinely exercised rather than trivially true against the
    GARD-only fixture.
    """
    synth = tmp_path / "synthetic.csv"
    synth.write_text(
        "ID,DisplayName,Synonyms,URL\n"
        "GARD:0000001,Real rare disease,,https://rarediseases.info.nih.gov/?gard_id=0000001\n"
        "GARD:0000002,Excluded no url,,\n"
        "BOGUS:9999,Non-GARD id,,https://example.com\n"
        ",No id,,https://example.com\n",
        encoding="utf-8",
    )
    labels = str(tmp_path / "labels")
    syns = str(tmp_path / "synonyms")
    pull_gard_labels_and_synonyms(str(synth), labels, syns)

    label_rows = assert_labels_file_valid(labels)
    syn_rows = assert_synonyms_file_valid(syns)
    assert [r[0] for r in label_rows] == ["GARD:0000001"]
    assert all(r[0] == "GARD:0000001" for r in syn_rows)


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
