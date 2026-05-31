"""
Tests for the manual UMLS semantic-type overrides used when building the leftover UMLS compendium
(src/createcompendia/leftover_umls.py).

These are marked ``network`` because they build a Biolink Model Toolkit, which fetches
``biolink-model.yaml`` from GitHub on first use (for the biolink_version pinned in config.yaml).
"""

import warnings

import pytest

from src.categories import PHENOMENON
from src.createcompendia.leftover_umls import (
    STY_OVERRIDES,
    TYPE_COMBO_OVERRIDES,
    tui_to_biolink_type,
)
from src.util import get_biolink_model_toolkit, get_config

BIOLINK_VERSION = get_config()["biolink_version"]

# The Biolink type that bmt currently assigns to each overridden UMLS semantic type (STY:<code>),
# recorded when the override was added, for the biolink_version pinned in config.yaml. Only the STY
# mappings are recorded -- that is all the drift check needs. If the live Biolink mapping diverges
# from these, the override must be re-reviewed; if it has come to equal the override, the override is
# redundant and can be removed.
RECORDED_STY_BASELINE: dict[str, str | None] = {
    "T033": None,  # https://github.com/NCATSTranslator/Babel/issues/569 -- "Finding": Biolink has no STY mapping.
    "T034": PHENOMENON,  # https://github.com/NCATSTranslator/Babel/issues/569 -- "Laboratory or Test Result".
}


@pytest.mark.network
def test_recorded_baseline_covers_all_overrides():
    """Every STY override must record a baseline, otherwise drift cannot be detected for it."""
    missing = set(STY_OVERRIDES) - set(RECORDED_STY_BASELINE)
    assert not missing, f"STY_OVERRIDES entries missing from RECORDED_STY_BASELINE: {sorted(missing)}"


@pytest.mark.network
def test_sty_overrides_have_not_drifted():
    """
    Hard-fail when the live Biolink STY mapping no longer matches the recorded baseline (Biolink
    changed underneath us, so the override must be re-reviewed). Warn -- but do not fail -- when
    Biolink has come to agree with the override, since the override is then redundant.
    """
    toolkit = get_biolink_model_toolkit(BIOLINK_VERSION)
    for tui, override in STY_OVERRIDES.items():
        current = tui_to_biolink_type(tui, toolkit=toolkit)
        baseline = RECORDED_STY_BASELINE[tui]
        assert current == baseline, (
            f"Biolink STY:{tui} now maps to {current!r}, but the recorded baseline is {baseline!r}. "
            f"Re-review the override (currently {override!r}) and update RECORDED_STY_BASELINE."
        )
        if current == override:
            warnings.warn(
                f"Biolink STY:{tui} now maps to {current!r}, which equals the manual override; "
                f"the entry in STY_OVERRIDES is redundant and can be removed.",
                stacklevel=2,
            )


@pytest.mark.network
def test_type_combo_overrides_reference_real_biolink_classes():
    """Every Biolink type named in TYPE_COMBO_OVERRIDES must be a real class in the pinned model."""
    toolkit = get_biolink_model_toolkit(BIOLINK_VERSION)
    referenced = set()
    for combo, value in TYPE_COMBO_OVERRIDES.items():
        referenced.update(combo)
        referenced.add(value)
    for biolink_type in sorted(referenced):
        assert toolkit.get_element(biolink_type) is not None, f"{biolink_type} is not a class in Biolink {BIOLINK_VERSION}"
