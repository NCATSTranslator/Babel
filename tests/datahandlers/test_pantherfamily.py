"""Network tests for the PANTHER family download.

The pipeline uses FTP (ftp.pantherdb.org), but FTP is often blocked by HPC firewalls.
PANTHER also exposes the same files over HTTP; these tests check both endpoints.

Run with: uv run pytest --network tests/datahandlers/test_pantherfamily.py
"""

import ftplib
import urllib.error
import urllib.request

import pytest

from src.babel_utils import get_user_agent

pytestmark = [pytest.mark.network]

FTP_HOST = "ftp.pantherdb.org"
FTP_DIR = "/sequence_classifications/current_release/PANTHER_Sequence_Classification_files/"
FTP_FILE = "PTHR19.0_human"

HTTP_BASE = (
    "http://data.pantherdb.org/ftp/sequence_classifications/current_release/PANTHER_Sequence_Classification_files/"
)
HTTP_FILE = "PTHR19.0_human"


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
    should be updated to use pull_via_urllib/pull_via_wget instead of pull_via_ftp.
    """
    url = HTTP_BASE + HTTP_FILE
    req = urllib.request.Request(url, headers={"User-Agent": get_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            chunk = resp.read(1024)
        assert len(chunk) > 0, "PANTHER HTTP endpoint returned an empty body"
    except urllib.error.HTTPError as e:
        pytest.fail(f"PANTHER HTTP URL {url} returned HTTP {e.code} with User-Agent '{get_user_agent()}'")
    except (TimeoutError, urllib.error.URLError) as e:
        pytest.xfail(f"PANTHER HTTP endpoint unreachable: {e}")
