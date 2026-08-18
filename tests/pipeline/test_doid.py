"""Pipeline tests for the DOID data handler, run against a real built concord.

Skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_doid.py --pipeline --no-cov -v
"""

import collections
import os

import pytest

from src.babel_utils import remove_overused_xrefs
from src.createcompendia.diseasephenotype import DOID_ICD_XREF_PREFIXES
from tests.pipeline.conftest import _intermediate_concord_path


@pytest.fixture
def doid_disease_concord():
    """The built disease/concords/DOID file, or skip if this checkout has no disease build."""
    # "diseasephenotype" is the Python compendium name, which config.yaml's compendium_directories
    # maps to the "disease" snakemake directory. Passing "disease" happens to resolve today only via
    # the unmapped-name fallback, and would start silently skipping if that key were ever added.
    path = _intermediate_concord_path("diseasephenotype", "DOID")
    if not os.path.exists(path):
        pytest.skip(f"{path} not built; run `uv run snakemake -c all get_disease_doid_relationships` first")
    return path


def _icd_pairs(concord_path):
    """(subject, target) for every ICD-shaped row in the concord, whatever the ICD flavour."""
    pairs = []
    with open(concord_path) as inf:
        for line in inf:
            subject, _predicate, target = line.rstrip("\n").split("\t")
            if target.split(":", 1)[0].upper().startswith("ICD"):
                pairs.append((subject, target))
    return pairs


@pytest.mark.pipeline
def test_doid_concord_keeps_its_icd_rows(doid_disease_concord):
    """ICD rows must survive into the concord; they are filtered at glom time, not at build time.

    Dropping them here would delete the ~4,800 1:1 rows along with the family codes, and would
    also erase them from the file `babel-overused-xrefs` audits. See docs/sources/DOID/mappings.md.
    """
    assert _icd_pairs(doid_disease_concord), "no ICD rows in the DOID concord -- has an exclusion crept back in?"


@pytest.mark.pipeline
def test_every_icd_flavour_in_the_concord_is_in_scope_for_the_filter(doid_disease_concord):
    """DOID_ICD_XREF_PREFIXES must cover every ICD spelling actually present.

    The scoped filter is an allowlist of namespaces to police, so it fails *open*: an ICD flavour
    DOID starts emitting that is missing from the list is not filtered at all, and its family codes
    go straight back to fusing every subtype that cites them. This check over the real file matches
    any ICD-shaped prefix rather than the listed ones, so it fails on the flavour the constant does
    not yet cover rather than on the constant's own contents. See issue #1029.
    """
    in_scope = {p.upper() for p in DOID_ICD_XREF_PREFIXES}
    present = {t.split(":", 1)[0].upper() for _s, t in _icd_pairs(doid_disease_concord)}

    assert present <= in_scope, (
        f"ICD flavour(s) {sorted(present - in_scope)} are in the DOID concord but not in "
        f"DOID_ICD_XREF_PREFIXES ({DOID_ICD_XREF_PREFIXES}), so the overuse filter ignores them "
        f"and their family codes will fuse every DOID subtype that cites one."
    )


@pytest.mark.pipeline
def test_the_filter_drops_the_family_codes_and_keeps_the_one_to_one_rows(doid_disease_concord):
    """The scoped filter must remove every multiply-claimed ICD code and keep every 1:1 one.

    This is the behaviour the categorical exclusion used to get wrong in both directions, asserted
    against the real concord rather than a fixture.
    """
    pairs = _icd_pairs(doid_disease_concord)
    subjects_by_target = collections.defaultdict(set)
    for subject, target in pairs:
        subjects_by_target[target].add(subject)
    kept = set(remove_overused_xrefs(pairs, target_prefixes=DOID_ICD_XREF_PREFIXES))

    survivors = {t for _s, t in kept}
    overused = {t for t, subjects in subjects_by_target.items() if len(subjects) > 1}
    one_to_one = {t for t, subjects in subjects_by_target.items() if len(subjects) == 1}

    assert not (survivors & overused), f"family codes survived the filter, e.g. {sorted(survivors & overused)[:5]}"
    assert one_to_one <= survivors, f"1:1 rows were dropped, e.g. {sorted(one_to_one - survivors)[:5]}"
