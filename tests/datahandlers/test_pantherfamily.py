"""Network tests for the PANTHER family download.

The pipeline uses FTP (ftp.pantherdb.org), but FTP is often blocked by HPC firewalls.
PANTHER also exposes the same files over HTTP; these tests check both endpoints.

Run with: uv run pytest --network tests/datahandlers/test_pantherfamily.py
"""

import ftplib
import urllib.error
import urllib.request

import pytest

import src.datahandlers.pantherfamily as pantherfamily
from src.babel_utils import get_user_agent
from src.datahandlers.pantherfamily import FTP_DIR, FTP_FILE, FTP_HOST, HTTP_BASE

pytestmark = [pytest.mark.network]


def test_panther_ftp_accessible():
    """PANTHER FTP endpoint should be reachable and list the expected file.

    This test is expected to fail on HPC nodes where outbound FTP (port 21) is
    firewalled — in that case the pipeline should use the HTTP endpoint instead.
    """
    try:
        ftp = ftplib.FTP(FTP_HOST, timeout=30)
        ftp.login()
        ftp.cwd(FTP_DIR)
        names = ftp.nlst()
        ftp.quit()
    except (TimeoutError, OSError) as e:
        pytest.xfail(f"FTP connection to {FTP_HOST} timed out or was refused — likely firewalled: {e}")
    except ftplib.all_errors as e:
        pytest.xfail(f"FTP error connecting to {FTP_HOST}: {e}")

    assert any(FTP_FILE in n for n in names), (
        f"Expected to find '{FTP_FILE}' in FTP listing of {FTP_HOST}{FTP_DIR}; got: {names[:10]}"
    )


def test_panther_http_accessible_with_user_agent():
    """PANTHER HTTP endpoint should be reachable with our User-Agent.

    This is the fallback when FTP is blocked (e.g. on HPC). If this test passes
    and test_panther_ftp_accessible xfails, the pull_pantherfamily() function
    falls back to HTTP automatically.
    """
    url = HTTP_BASE + FTP_FILE
    req = urllib.request.Request(url, headers={"User-Agent": get_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            chunk = resp.read(1024)
        assert len(chunk) > 0, "PANTHER HTTP endpoint returned an empty body"
    except urllib.error.HTTPError as e:
        pytest.fail(f"PANTHER HTTP URL {url} returned HTTP {e.code} with User-Agent '{get_user_agent()}'")
    except (TimeoutError, urllib.error.URLError) as e:
        pytest.xfail(f"PANTHER HTTP endpoint unreachable: {e}")


def test_pull_pantherfamily_falls_back_to_http_when_ftp_blocked(tmp_path, monkeypatch):
    """pull_pantherfamily() must fall back to HTTP when FTP is blocked (HPC firewall scenario).

    Simulates the HPC environment where port 21 is refused, confirms the HTTP mirror
    is tried and produces a non-empty output file at the expected path.
    """

    def ftp_refused(*args, **kwargs):
        raise OSError("Connection refused (simulating HPC FTP firewall)")

    monkeypatch.setattr("src.datahandlers.pantherfamily.pull_via_ftp", ftp_refused)
    monkeypatch.setattr("src.datahandlers.pantherfamily.get_config", lambda: {"download_directory": str(tmp_path)})
    monkeypatch.setattr("src.datahandlers.pantherfamily.get_user_agent", lambda: "Babel/test")

    try:
        pantherfamily.pull_pantherfamily()
    except (TimeoutError, urllib.error.URLError) as e:
        pytest.xfail(f"HTTP fallback also unreachable (no network?): {e}")

    outfile = tmp_path / "PANTHER.FAMILY" / "family.csv"
    assert outfile.exists(), f"Expected output file {outfile} was not created"
    assert outfile.stat().st_size > 0, f"Output file {outfile} is empty"
