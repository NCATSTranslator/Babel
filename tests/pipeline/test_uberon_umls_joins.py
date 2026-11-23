"""Pipeline tests for the UBERON/UMLS joins, run against the built anatomy concords.

Skipped by default unless pytest is run with --pipeline. Run with:
    uv run pytest tests/pipeline/test_uberon_umls_joins.py --pipeline --no-cov -v
"""

import csv
import os

import pytest

from src.babel_utils import read_badxrefs
from src.createcompendia.anatomy import ANATOMY_BAD_XREFS, find_uberon_snomed_xrefs_to_review
from src.prefixes import UBERON, UMLS
from src.util import get_repo_root
from tests.pipeline.conftest import _intermediate_concord_path

REVIEWED_CSV = get_repo_root() / "docs/sources/UBERON/umls-joins/snomed-xref-review.csv"


@pytest.fixture
def anatomy_snomed_concords():
    """The built anatomy UBERON and UMLS concords, or skip if this checkout has no anatomy build."""
    paths = [_intermediate_concord_path("anatomy", vocab) for vocab in (UBERON, UMLS)]
    for path in paths:
        if not os.path.exists(path):
            pytest.skip(f"{path} not built; run `uv run snakemake -c all anatomy` first")
    return paths


@pytest.mark.pipeline
def test_every_flagged_uberon_snomed_xref_has_been_reviewed(anatomy_snomed_concords):
    """Every UBERON SNOMED xref that joins a lumped UMLS concept, or one of several, should have been reviewed.

    find_uberon_snomed_xrefs_to_review() flags the two shapes in which a SNOMED xref merges more than the UBERON
    term means. Each flagged xref must be dropped in input_data/anatomy_badxrefs.txt or listed as kept in
    snomed-xref-review.csv; a new UBERON or UMLS release that adds one fails here instead of shipping the merge
    unseen. To fix a failure, judge each xref listed (docs/sources/UBERON/umls-joins/README.md says how), add
    the wrong ones to anatomy_badxrefs.txt, then regenerate the CSV with
    docs/sources/UBERON/umls-joins/scripts/snomed_xref_review.py.
    """
    bad_pairs = {frozenset(pair) for pair in read_badxrefs(ANATOMY_BAD_XREFS)}
    flagged = find_uberon_snomed_xrefs_to_review(*anatomy_snomed_concords, bad_pairs=bad_pairs)
    with open(REVIEWED_CSV) as inf:
        reviewed = {(row["uberon_id"], row["snomed_id"]) for row in csv.DictReader(inf)}
    unreviewed = sorted(set(flagged) - reviewed)
    assert not unreviewed, f"{len(unreviewed)} UBERON SNOMED xrefs need review: {unreviewed[:20]}"
