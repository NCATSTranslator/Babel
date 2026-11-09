"""Unit tests for `src.babel_utils.norm()`, the CURIE prefix renamer.

`norm()` is what turns a source's spelling of another vocabulary's prefix into Babel's
(`config.yaml: disease_xref_prefixes`). A prefix it fails to rename is not an error -- the
un-renamed CURIE still reaches `glom()`, joins nothing, and fuses every subject that cites it
into one clique -- so these cover the two ways a rename can quietly miss.
"""

import pytest

from src.babel_utils import norm
from src.prefixes import OMIM, OMIMPS, SNOMEDCT
from src.util import Text

# RELEASE-STAMPED PREFIXES


@pytest.mark.unit
def test_norm_renames_an_exact_prefix_match():
    """The ordinary case: a key present in the map renames, everything else is returned as-is."""
    assert norm("NCI:C140267", {"NCI": "NCIT"}) == "NCIT:C140267"
    assert norm("GARD:6637", {"NCI": "NCIT"}) == "GARD:6637"


@pytest.mark.unit
@pytest.mark.parametrize(
    "curie",
    [
        # Every SNOMED spelling in the DOID release of 2026-08-18; the map names only the stem.
        "SNOMEDCT_US_2025_09_01:267692008",
        "SNOMEDCT_US_2026_03_01:267692008",
        "SNOMEDCT_US_2021_07_31:267692008",
        "SNOMEDCT_US_2020_03_01:267692008",
    ],
)
def test_norm_matches_the_stem_of_a_release_stamped_prefix(curie):
    """A `_YYYY_MM_DD` release stamp should not defeat the rename.

    DOID mints a new SNOMED prefix on every upstream release, so a map pinning the dates goes
    stale silently -- 5,357 of 5,358 SNOMED rows were reaching glom() un-renamed under the old
    four-date list.
    """
    assert norm(curie, {"SNOMEDCT_US": SNOMEDCT}) == "SNOMEDCT:267692008"


@pytest.mark.unit
def test_norm_leaves_a_stamped_prefix_alone_when_the_stem_is_not_mapped():
    """Stripping the stamp must only ever be a second lookup, never a rewrite in its own right."""
    assert norm("FOO_2025_09_01:1", {"BAR": "BAZ"}) == "FOO_2025_09_01:1"


@pytest.mark.unit
def test_norm_ignores_a_non_date_underscore_suffix():
    """Only a real `_YYYY_MM_DD` counts, so an ordinary underscored prefix is untouched."""
    assert norm("UMLS_CUI:C0037773", {"UMLS": "UMLS"}) == "UMLS_CUI:C0037773"


# LOCAL-ID-DEPENDENT RENAMES


@pytest.mark.unit
def test_norm_accepts_a_callable_rename():
    """A map value may be a callable when the target prefix depends on the CURIE's local id.

    OMIM is the case that needs it: DOID's `MIM:PS303350` is a phenotypic series, which Babel
    spells `OMIM.PS:303350` (the "PS" belongs to the prefix), while `MIM:115210` is a plain entry.
    """
    rename = {"MIM": lambda curie: Text.omim_curie(Text.un_curie(curie))}
    assert norm("MIM:PS303350", rename) == f"{OMIMPS}:303350"
    assert norm("MIM:115210", rename) == f"{OMIM}:115210"


@pytest.mark.unit
def test_norm_passes_through_a_prefixless_value():
    """A DOID xref value can be colonless; that is not a CURIE and must not crash the rename."""
    assert norm("no-colon-here", {"NCI": "NCIT"}) == "no-colon-here"
