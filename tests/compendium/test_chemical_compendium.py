"""Near-end-to-end tests for `write_compendium()` on chemical cliques.

Verifies that the per-type label demotion still applies for chemicals (the
one Biolink type listed in `config.yaml`'s `demote_labels_longer_than`),
even after PR #725 narrowed demotion away from diseases / phenotypes.
"""

import pytest

from src.babel_utils import write_compendium

from .conftest import assert_preferred_name


@pytest.mark.unit
def test_serine_long_iupac_demoted(babel_test_env):
    """For biolink:ChemicalEntity, CHEBI:17334's IUPAC name (35 chars) should be
    demoted in favour of PUBCHEM.COMPOUND:5951 "serine" (6 chars).
    """
    write_compendium(
        metadata_yamls=[],
        synonym_list=[{"CHEBI:17334", "PUBCHEM.COMPOUND:5951"}],
        ofname="Serine.txt",
        node_type="biolink:ChemicalEntity",
        labels={},
        icrdf_filename=babel_test_env.icrdf_path,
    )
    [record] = babel_test_env.read_records("Serine.txt")
    assert_preferred_name(record, "serine")
