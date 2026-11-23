"""Tests for the HMDB download and for parsing its metabolites XML.

HMDB fronts its download URL with a Cloudflare bot challenge, so the unattended download cannot
succeed and the operator has to place the zip by hand. The download tests cover the two halves of
that: that Babel still recognizes the live response as a challenge, and that a hand-placed zip is
actually used on the next run. The parsing test runs make_labels_and_synonyms_and_smiles() over
real metabolites.

Run the network test with: uv run pytest --network tests/datahandlers/test_hmdb.py
"""

import urllib.error
import urllib.request
import zipfile
from unittest.mock import patch

import pytest

from src.babel_utils import get_user_agent, raise_if_cloudflare_challenge
from src.datahandlers.hmdb import HMDB_DOWNLOAD_URL, HMDB_ZIP_FILENAME, make_labels_and_synonyms_and_smiles, pull_hmdb
from src.util import get_config
from tests.conftest import REPO_ROOT

HMDB_ZIP_URL = HMDB_DOWNLOAD_URL + HMDB_ZIP_FILENAME


# LIVE HMDB DOWNLOAD


@pytest.mark.network
def test_hmdb_download_either_works_or_is_a_recognized_challenge():
    """The live HMDB URL should either serve the file or be recognized as a Cloudflare challenge.

    As of 2026-09-11 it is the latter (HTTP 403, `cf-mitigated: challenge`). This asserts the
    disjunction rather than reachability because both outcomes are fine -- what is not fine is a
    403 Babel fails to classify, which would send the rule into a retry loop with an unhelpful
    error instead of telling the operator to fetch the zip by hand.
    """
    req = urllib.request.Request(HMDB_ZIP_URL, headers={"User-Agent": get_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            assert len(resp.read(1024)) > 0, "HMDB returned an empty body"
    except urllib.error.URLError as e:
        with pytest.raises(RuntimeError, match="Cloudflare bot challenge"):
            raise_if_cloudflare_challenge(HMDB_ZIP_URL, "babel_downloads/HMDB/" + HMDB_ZIP_FILENAME, e)


# MANUALLY PLACED ZIP


@pytest.mark.unit
def test_pull_hmdb_uses_a_manually_placed_zip(tmp_path):
    """A zip already sitting in the download directory should be unpacked without re-downloading.

    This is what makes the "place it here and re-run" instruction in the Cloudflare error true:
    pull_via_urllib() deletes its target before each attempt, so a manual copy would otherwise be
    wiped and the rule would fail the same way forever.
    """
    hmdb_dir = tmp_path / "HMDB"
    hmdb_dir.mkdir()
    with zipfile.ZipFile(hmdb_dir / HMDB_ZIP_FILENAME, "w") as zipobj:
        zipobj.writestr("hmdb_metabolites.xml", "<hmdb/>")

    config = {**get_config(), "download_directory": str(tmp_path)}
    with (
        patch("src.datahandlers.hmdb.get_config", return_value=config),
        patch("src.datahandlers.hmdb.pull_via_urllib") as pull,
    ):
        pull_hmdb()

    pull.assert_not_called()
    assert (hmdb_dir / "hmdb_metabolites.xml").read_text() == "<hmdb/>"


# PARSING THE METABOLITES XML

# Three <metabolite> records copied verbatim from hmdb_metabolites.xml (HMDB 5.0, zip downloaded
# 2026-11-23), inside that file's own XML declaration and <hmdb> root. They are the smallest
# records with ten synonyms (HMDB0304854), exactly one (HMDB0295356) and none (HMDB0242613).
HMDB_FIXTURE = REPO_ROOT / "tests" / "data" / "hmdb_three_metabolites.xml"


@pytest.mark.unit
def test_make_labels_and_synonyms_and_smiles_writes_every_metabolite(tmp_path):
    """Every metabolite should reach all three outputs, however many synonyms it has.

    xmltodict makes <synonyms> a list for several children, a bare string for one (93,622 of
    217,920 metabolites) and leaves out the key for none (16,293), so each shape is covered. The
    expected rows are what main's whole-document parse wrote before the parse was made to stream.
    """
    labels, synonyms, smiles = tmp_path / "labels", tmp_path / "synonyms", tmp_path / "smiles"
    make_labels_and_synonyms_and_smiles(HMDB_FIXTURE, labels, synonyms, smiles)

    assert labels.read_text().splitlines() == [
        "HMDB:HMDB0242613\tCMLDBU00000416",
        "HMDB:HMDB0295356\tDG(22:6(4Z,7Z,10Z,13E,15E,19Z)-OH(17)/15:0/0:0)",
        "HMDB:HMDB0304854\tGallium 68 Psma-11",
    ]
    assert synonyms.read_text().splitlines() == [
        "HMDB:HMDB0295356\toio:exact\t(2S)-3-Hydroxy-2-(pentadecanoyloxy)propyl"
        " (4Z,7Z,10Z,13E,15E,19Z)-17-hydroxydocosa-4,7,10,13,15,19-hexaenoic acid",
        "HMDB:HMDB0304854\toio:exact\t(68)Ga-psma",
        "HMDB:HMDB0304854\toio:exact\t68 Ga-psma-I and T",
        "HMDB:HMDB0304854\toio:exact\t68Ga-psma",
        "HMDB:HMDB0304854\toio:exact\t68Ga-psma-11",
        "HMDB:HMDB0304854\toio:exact\tGlu-NH-CO-NH-lys-(ahx)-((68)ga(hbed-CC))",
        "HMDB:HMDB0304854\toio:exact\tGallium ga-68 gozetotide",
        "HMDB:HMDB0304854\toio:exact\tGA-68 psma-11",
        "HMDB:HMDB0304854\toio:exact\t(68Ga)glu-urea-lys(ahx)-hbed-CC",
        "HMDB:HMDB0304854\toio:exact\t68 Ga-psma-I-T",
        "HMDB:HMDB0304854\toio:exact\tGlu-NH-CO-NH-lys-(ahx)-(68ga(hbed-CC))",
    ]
    assert smiles.read_text().splitlines() == [
        # Pins current behavior: an empty <smiles/> is written as the string "None" (24 metabolites
        # in the whole file). Nothing in Babel reads HMDB/smiles today; if something starts to,
        # skip these rows and invert this line rather than deleting it.
        "HMDB:HMDB0242613\tNone",
        "HMDB:HMDB0295356\tCCCCCCCCCCCCCCC(=O)O[C@@H](CO)COC(=O)CC\\C=C/C\\C=C/C\\C=C/C\\C=C\\C=C\\C(O)C\\C=C/CC",
        "HMDB:HMDB0304854\t[H+].[68Ga+3].OC(=O)CC[C@H](NC(=O)N[C@@H](CCCCNC(=O)CCCCCNC(=O)CCC1=CC=C([O-])"
        "C(CN(CCN(CC([O-])=O)CC2=CC(CCC(O)=O)=CC=C2[O-])CC([O-])=O)=C1)C(O)=O)C(O)=O",
    ]
