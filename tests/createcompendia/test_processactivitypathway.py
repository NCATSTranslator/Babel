"""Unit tests for src/createcompendia/processactivitypathway.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.createcompendia import processactivitypathway
from src.prefixes import DOI, GO, PMC, PMID

# --- GO publication xrefs ---


@pytest.mark.unit
def test_go_concord_drops_publication_xrefs(tmp_path):
    """build_process_obo_relationships must keep GO's citations out of concords/GO.

    The rows are 2025dec11's GO concord verbatim for GO:0050212 "progesterone 11-alpha-monooxygenase
    activity": a citation, which must be dropped, beside its EC and RHEA mappings, which must survive.
    A doi and a PMC citation (synthetic; GO had none) check the other publication prefixes. Exercises the
    real call site, because the ignore_list it passes is the whole fix.
    """
    xrefs = {
        "GO:0050212": {"PMID:39766209", "EC:1.14.99.14", "RHEA:18205"},
        "GO:0180012": {"PMID:31499460", "doi:10.1000/example", "PMC:PMC0000001"},
    }
    fake_uber = MagicMock()
    fake_uber.get_subclasses_and_xrefs.return_value = xrefs

    outdir = tmp_path / "concords"
    outdir.mkdir()
    with patch("src.ubergraph.UberGraph", return_value=fake_uber):
        processactivitypathway.build_process_obo_relationships(str(outdir), str(tmp_path / "metadata-GO.yaml"))

    # Each of the three GO roots returns the same fake xrefs, so each surviving row is written three times.
    rows = sorted(set((outdir / GO).read_text().splitlines()))
    assert rows == [f"{GO}:0050212\txref\tEC:1.14.99.14", f"{GO}:0050212\txref\tRHEA:18205"]


@pytest.mark.unit
def test_go_xref_ignore_prefixes_cover_every_publication_prefix():
    """GO_XREF_IGNORE_PREFIXES must name PMID, PMC and doi, upper-cased as build_sets() requires."""
    assert {PMID.upper(), PMC.upper(), DOI.upper()} <= set(processactivitypathway.GO_XREF_IGNORE_PREFIXES)
    assert processactivitypathway.GO_XREF_IGNORE_PREFIXES == [
        p.upper() for p in processactivitypathway.GO_XREF_IGNORE_PREFIXES
    ]
