"""Tests for the OMIM data handler and the User-Agent header it sends."""
import os
from unittest.mock import MagicMock, patch

import pytest

from src.babel_utils import BABEL_GITHUB_URL, get_user_agent


@pytest.mark.unit
def test_get_user_agent_includes_branch_and_url():
    """get_user_agent() should embed the build branch and the GitHub URL."""
    with patch("src.babel_utils.get_config", return_value={"build": {"branch": "babel-test"}}):
        ua = get_user_agent()
    assert "TranslatorBabel/babel-test" in ua
    assert BABEL_GITHUB_URL in ua


@pytest.mark.unit
def test_pull_via_urllib_sends_user_agent(tmp_path):
    """pull_via_urllib() should pass a Request with the configured User-Agent."""
    from src.babel_utils import pull_via_urllib

    captured = []

    def fake_open(req):
        captured.append(req)
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        return mock_resp

    mock_opener = MagicMock()
    mock_opener.open.side_effect = fake_open

    fake_config = {
        "download_directory": str(tmp_path),
        "build": {"branch": "babel-test"},
    }

    with patch("urllib.request.build_opener", return_value=mock_opener), patch("src.babel_utils.get_config", return_value=fake_config):
        pull_via_urllib("http://example.com/", "test.txt", decompress=False)

    assert len(captured) == 1
    # urllib capitalises the first letter of each header name
    assert captured[0].get_header("User-agent") == "TranslatorBabel/babel-test (https://github.com/NCATSTranslator/Babel)"


@pytest.mark.network
def test_pull_omim_downloads_mim2gene():
    """pull_omim() should successfully download mim2gene.txt from omim.org."""
    from src.datahandlers.omim import pull_omim

    outfile = pull_omim()
    assert os.path.exists(outfile), f"Expected {outfile} to exist after pull_omim()"
    assert os.path.getsize(outfile) > 1024, f"mim2gene.txt is suspiciously small ({os.path.getsize(outfile)} bytes)"
