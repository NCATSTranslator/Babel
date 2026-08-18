"""Pipeline tests for the DOID data handler, run against a real built concord.

Skipped by default unless pytest is run with --pipeline.  Run with:
    uv run pytest tests/pipeline/test_doid.py --pipeline --no-cov -v
"""

import os

import pytest

from src.createcompendia.diseasephenotype import DOID_EXCLUDED_XREF_PREFIXES
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


@pytest.mark.pipeline
def test_doid_concord_has_no_icd_targets(doid_disease_concord):
    """No ICD target may survive into the built concord.

    `DOID_EXCLUDED_XREF_PREFIXES` is a denylist, so it fails open: a new ICD spelling DOID starts
    emitting, or an `other_prefixes` rename introducing one (e.g. ICD11CM), would be trusted by
    default and silently re-fuse disease families. This check over the real file is the
    compensating control -- it matches any ICD-shaped prefix, not just the listed ones, so it
    fails on a flavour the constant does not yet cover rather than on the constant's own contents.
    See docs/sources/DOID/mappings.md and issue #1029.
    """
    leaked = set()
    with open(doid_disease_concord) as inf:
        for line in inf:
            target = line.rstrip("\n").split("\t")[-1]
            if target.split(":", 1)[0].upper().startswith("ICD"):
                leaked.add(target)

    assert not leaked, (
        f"{len(leaked)} ICD target(s) reached the DOID concord, e.g. {sorted(leaked)[:5]}. "
        f"An ICD code names a disease family, not a disease, so none of these is an equivalence; "
        f"add the missing flavour to DOID_EXCLUDED_XREF_PREFIXES (currently "
        f"{DOID_EXCLUDED_XREF_PREFIXES})."
    )
