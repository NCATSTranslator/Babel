"""Unit tests for src/model/inchikeys.py: splitting InChIKeys and classifying how two relate.

Every key is a real one, as dev NodeNorm (Babel 2026jul22) returned it for the CURIE named beside it.
"""

import pytest

from src.model.inchikeys import InchikeyRelation, classify_inchikey_pair, split_inchikey

RUXOLITINIB = "INCHIKEY:HFNKQEVNSGCOJV-OAHLLOKOSA-N"  # CHEBI:66919, the drug
RUXOLITINIB_NO_STEREO = "INCHIKEY:HFNKQEVNSGCOJV-UHFFFAOYSA-N"  # CHEBI:91405
DEXAMETHASONE = "INCHIKEY:UREBDLICKHMUKA-CXSFZGCWSA-N"  # CHEBI:41879
BETAMETHASONE = "INCHIKEY:UREBDLICKHMUKA-DVTGEIKXSA-N"  # CHEBI:3077
VALPROIC_ACID = "INCHIKEY:NIJJYAXOARWZEE-UHFFFAOYSA-N"  # CHEBI:39867
VALPROATE = "INCHIKEY:NIJJYAXOARWZEE-UHFFFAOYSA-M"  # CHEBI:60654
ETHANOL = "INCHIKEY:LFQSCWFLJHTTHZ-UHFFFAOYSA-N"  # CHEBI:16236
ETHANOL_D6 = "INCHIKEY:LFQSCWFLJHTTHZ-LIDOUZCJSA-N"  # CHEBI:193043

# SPLITTING


@pytest.mark.unit
def test_split_accepts_a_bare_key_or_a_curie():
    """Should return the three blocks whether or not the key carries its INCHIKEY: prefix."""
    assert split_inchikey(RUXOLITINIB) == ("HFNKQEVNSGCOJV", "OAHLLOKOSA", "N")
    assert split_inchikey("HFNKQEVNSGCOJV-OAHLLOKOSA-N") == ("HFNKQEVNSGCOJV", "OAHLLOKOSA", "N")


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["INCHIKEY:HFNKQEVNSGCOJV-OAHLLOKOSA", "HFNKQEVNSGCOJV-OAHLLOKOS-N", "water"])
def test_split_rejects_what_is_not_an_inchikey(bad):
    """Should raise ValueError rather than classify a malformed key."""
    with pytest.raises(ValueError):
        split_inchikey(bad)


# CLASSIFYING


@pytest.mark.unit
@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (RUXOLITINIB, RUXOLITINIB, InchikeyRelation.IDENTICAL),
        (VALPROIC_ACID, VALPROATE, InchikeyRelation.CHARGE_ONLY),
        (RUXOLITINIB, RUXOLITINIB_NO_STEREO, InchikeyRelation.ONE_STEREO_UNSPECIFIED),
        (RUXOLITINIB_NO_STEREO, RUXOLITINIB, InchikeyRelation.ONE_STEREO_UNSPECIFIED),
        (DEXAMETHASONE, BETAMETHASONE, InchikeyRelation.DIFFERENT_STEREO),
        (RUXOLITINIB, DEXAMETHASONE, InchikeyRelation.DIFFERENT_SKELETON),
        (RUXOLITINIB, None, InchikeyRelation.MISSING),
        (None, None, InchikeyRelation.MISSING),
    ],
)
def test_classify_inchikey_pair(a, b, expected):
    """Should name the block in which two keys first differ, in either order."""
    assert classify_inchikey_pair(a, b) == expected


@pytest.mark.unit
def test_isotope_label_is_read_as_a_stereo_difference():
    """Pins current behavior: an isotope-labelled form looks like a stereo-unspecified pair.

    The second InChIKey block hashes the isotope layer along with stereo, so ethanol-d6 and ethanol look
    exactly like a drug and its stereo-less record. #1173 notes that telling them apart needs the InChI's
    /i layer. If classify_inchikey_pair() learns to read it, invert this assertion rather than delete it.
    """
    assert classify_inchikey_pair(ETHANOL_D6, ETHANOL) == InchikeyRelation.ONE_STEREO_UNSPECIFIED
