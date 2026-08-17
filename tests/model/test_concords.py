"""Unit tests for src/model/concords.py.

Sections:

- ``# --- find_overused_xref_targets ---`` checks the overuse detection that backs
  ``babel-overused-xrefs`` and mirrors ``remove_overused_xrefs``'s 2+ subject rule.
- ``# --- load_mrconso_labels ---`` checks the MRCONSO fallback used to label the
  classification vocabularies (ICD-10, SNOMED) Babel references but never ingests.
"""

import pytest

from src.model.concords import find_overused_xref_targets, load_mrconso_labels

# --- find_overused_xref_targets ---


def _write_concord(path, rows):
    path.write_text("".join(f"{s}\txref\t{o}\n" for s, o in rows))
    return str(path)


@pytest.mark.unit
def test_finds_targets_claimed_by_multiple_subjects(tmp_path):
    """A target claimed by 2+ subjects is reported with all its subjects; a 1:1 target is not.

    The rows are the real shape from intermediate/disease/concords/DOID: three hereditary spastic
    paraplegia terms all citing ICD10:G11.4, each with its own MIM code.
    """
    concord = _write_concord(
        tmp_path / "DOID",
        [
            ("DOID:0110764", "ICD10:G11.4"),
            ("DOID:0110764", "MIM:604360"),
            ("DOID:0110782", "ICD10:G11.4"),
            ("DOID:0110782", "MIM:610250"),
            ("DOID:2476", "ICD10:G11.4"),
        ],
    )

    overused = find_overused_xref_targets(concord)

    assert [o.target for o in overused] == ["ICD10:G11.4"]
    assert overused[0].subjects == {"DOID:0110764", "DOID:0110782", "DOID:2476"}
    assert overused[0].subject_count == 3
    assert overused[0].prefix == "ICD10"


@pytest.mark.unit
def test_sorted_most_claimed_first_then_by_target(tmp_path):
    """Ordering must be deterministic so a regenerated CSV diffs cleanly."""
    concord = _write_concord(
        tmp_path / "DOID",
        [
            ("DOID:1", "ICD10:B"),
            ("DOID:2", "ICD10:B"),
            ("DOID:1", "ICD10:A"),
            ("DOID:2", "ICD10:A"),
            ("DOID:3", "ICD10:A"),
        ],
    )

    assert [o.target for o in find_overused_xref_targets(concord)] == ["ICD10:A", "ICD10:B"]


@pytest.mark.unit
def test_repeated_row_is_one_subject(tmp_path):
    """The same subject asserting a target twice is not overuse -- subjects are a set."""
    concord = _write_concord(tmp_path / "DOID", [("DOID:1", "ICD10:A"), ("DOID:1", "ICD10:A")])

    assert find_overused_xref_targets(concord) == []


@pytest.mark.unit
def test_min_subjects_is_configurable(tmp_path):
    """--min-subjects raises the bar above remove_overused_xrefs' default of 2."""
    concord = _write_concord(tmp_path / "DOID", [("DOID:1", "ICD10:A"), ("DOID:2", "ICD10:A")])

    assert [o.target for o in find_overused_xref_targets(concord, min_subjects=2)] == ["ICD10:A"]
    assert find_overused_xref_targets(concord, min_subjects=3) == []


@pytest.mark.unit
def test_target_prefixes_restricts_to_the_named_prefixes(tmp_path):
    """--target-prefixes with --min-subjects 1 enumerates every row targeting those namespaces,
    which is how a categorical prefix exclusion (DOID's ICD rows) is written out for review.
    Prefixes are matched case-insensitively, hence the lower-case argument here."""
    concord = _write_concord(
        tmp_path / "DOID",
        [("DOID:0110764", "ICD10:G11.4"), ("DOID:0110764", "MIM:604360"), ("DOID:2476", "ICD10:G11.4")],
    )

    icd_only = find_overused_xref_targets(concord, min_subjects=1, target_prefixes=["icd10"])
    assert [o.target for o in icd_only] == ["ICD10:G11.4"]

    # Without the restriction the 1:1 MIM row is reported too.
    assert [o.target for o in find_overused_xref_targets(concord, min_subjects=1)] == ["ICD10:G11.4", "MIM:604360"]


@pytest.mark.unit
def test_malformed_row_raises(tmp_path):
    """A row that is not exactly three tab-separated columns must raise, not be mis-parsed."""
    concord = tmp_path / "DOID"
    concord.write_text("DOID:1\tICD10:A\n")

    with pytest.raises(RuntimeError, match="not a valid concord row"):
        find_overused_xref_targets(str(concord))


# --- load_mrconso_labels ---

# Rows copied verbatim from babel_downloads/UMLS/MRCONSO.RRF (UMLS 2026AA) for G11.4 "Hereditary
# spastic paraplegia", plus the Dutch row that beat the English one before the language filter
# existed, and an obsolete SNOMED row (SUPPRESS=O) that must not be used as a label.
_MRCONSO_ROWS = [
    "C0037773|ENG|P|L0037773|VCW|S0377908|N|A17774363|||G11.4|ICD10CM|PT|G11.4|Hereditary spastic paraplegia|4|N||",
    "C0037773|ENG|P|L0037773|VCW|S0377908|N|A20097855|||G11.4|ICD10CM|AB|G11.4|Hereditary spastic paraplegia|4|Y||",
    "C0037773|DUT|P|L1000000|PF|S1000000|N|A10000000|||G11.4|ICD10DUT|PT|G11.4|Hereditaire spastische paraplegie|3|N||",
    "C0037773|ENG|S|L0037773|PF|S0377908|N|A22000000|166113012|267692008||SNOMEDCT_US|OAS|267692008|Hereditary spastic paraplegia|9|O||",
]


@pytest.fixture
def mrconso(tmp_path):
    path = tmp_path / "MRCONSO.RRF"
    path.write_text("".join(f"{row}\n" for row in _MRCONSO_ROWS))
    return str(path)


@pytest.mark.unit
def test_resolves_icd10_curie_against_icd10cm_sab(mrconso):
    """ICD10:G11.4 must match SAB=ICD10CM: the prefix is a token-prefix of the SAB, not equal to
    it, which is the whole reason this is a heuristic rather than a lookup table."""
    assert load_mrconso_labels(mrconso, {"ICD10:G11.4"}) == {"ICD10:G11.4": "Hereditary spastic paraplegia"}


@pytest.mark.unit
def test_non_english_rows_are_ignored(mrconso):
    """MRCONSO is multilingual and the Dutch row sorts no worse than the English one on TTY, so
    without the language filter it can win. Regression guard: the first generated CSV was Dutch."""
    labels = load_mrconso_labels(mrconso, {"ICD10:G11.4"})

    assert labels["ICD10:G11.4"] == "Hereditary spastic paraplegia"
    assert load_mrconso_labels(mrconso, {"ICD10:G11.4"}, language="DUT") == {
        "ICD10:G11.4": "Hereditaire spastische paraplegie"
    }


@pytest.mark.unit
def test_obsolete_rows_do_not_supply_a_label(mrconso):
    """DOID xrefs retired SNOMED concepts whose only MRCONSO strings are SUPPRESS=O. An empty
    cell is more honest than an obsolete string presented as the current label."""
    assert load_mrconso_labels(mrconso, {"SNOMEDCT_US_2025_09_01:267692008"}) == {}


@pytest.mark.unit
def test_unknown_curie_yields_no_entry(mrconso):
    """A CURIE MRCONSO has nothing for is simply absent, not an empty string."""
    assert load_mrconso_labels(mrconso, {"ICD10:Z99.9"}) == {}
