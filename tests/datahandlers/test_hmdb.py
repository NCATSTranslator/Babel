"""Network tests for the HMDB download.

These verify that HMDB's download URL is reachable with the User-Agent Babel sends.
Run with: uv run pytest --network tests/datahandlers/test_hmdb.py
"""

import urllib.error
import urllib.request

import pytest

from src.babel_utils import get_user_agent

pytestmark = [pytest.mark.network]

HMDB_ZIP_URL = "https://hmdb.ca/system/downloads/current/hmdb_metabolites.zip"


def test_hmdb_url_accessible_with_user_agent():
    """HMDB download URL should be reachable with our User-Agent (not 403)."""
    req = urllib.request.Request(HMDB_ZIP_URL, headers={"User-Agent": get_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            # Read just the first 1 KB to confirm the body streams without error.
            chunk = resp.read(1024)
        assert len(chunk) > 0, "HMDB returned an empty body"
    except urllib.error.HTTPError as e:
        pytest.fail(
            f"HMDB download URL returned HTTP {e.code} with User-Agent '{get_user_agent()}'. "
            "The server may be blocking non-browser clients or the HPC egress IP."
        )


def test_hmdb_url_rejects_no_user_agent():
    """HMDB returns 403 when no User-Agent is set (raw urllib default).

    This documents the known behaviour that motivates always setting our User-Agent.
    If HMDB changes policy and starts accepting bare requests, this test will fail
    and should be removed.
    """
    # urllib's default User-Agent is "Python-urllib/<version>", which HMDB rejects.
    req = urllib.request.Request(HMDB_ZIP_URL)
    try:
        with urllib.request.urlopen(req, timeout=30):
            pass
        # If we get here the server accepted the bare request — document the change.
        pytest.xfail("HMDB no longer rejects bare Python-urllib requests; remove this test.")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            pass  # expected — server rejects bare requests
        else:
            pytest.fail(f"Unexpected HTTP {e.code} from HMDB (expected 403 for bare UA)")
