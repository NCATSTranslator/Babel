"""Unit tests for src.datahandlers/doid.py.

The fixture `tests/data/doid_gard_xref_sample.json` holds two nodes copied verbatim from
`babel_downloads/DOID/doid.json`: [`DOID:0050012`](http://purl.obolibrary.org/obo/DOID_0050012)
"chikungunya", whose GARD xref is already unpadded, and
[`DOID:0061030`](http://purl.obolibrary.org/obo/DOID_0061030) "hemophilia", whose GARD xref is
zero-padded -- the two forms DOID mixes. Re-derive either node from the DOID release.
"""

from pathlib import Path

import pytest

from src.datahandlers.doid import build_xrefs
from tests.conftest import assert_concordance_file_valid

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "doid_gard_xref_sample.json"


@pytest.mark.unit
def test_build_xrefs_unpads_gard_ids(tmp_path):
    """DOID emits GARD ids in both forms (GARD:6038 and GARD:0418); both must reach the concord
    unpadded, so they join the GARD registry's identifiers instead of forming parallel cliques."""
    outfile = tmp_path / "DOID"
    build_xrefs(str(FIXTURE), str(outfile))

    rows = assert_concordance_file_valid(str(outfile))
    assert {(r[0], r[2]) for r in rows} == {
        ("DOID:0050012", "GARD:6038"),
        ("DOID:0061030", "GARD:418"),
    }
