"""Tests for the OMIM data handler and the User-Agent header it sends."""
import os
from unittest.mock import MagicMock, patch

import pytest

from src.babel_utils import get_user_agent
from src.prefixes import OMIM
from tests.conftest import assert_labels_file_valid


@pytest.mark.unit
def test_get_user_agent_includes_branch_and_url():
    """get_user_agent() should embed the build branch and the GitHub URL."""
    fake_config = {"build": {"branch": "babel-test"}, "babel": {"github_url": "https://github.com/NCATSTranslator/Babel"}}
    with patch("src.babel_utils.get_config", return_value=fake_config):
        ua = get_user_agent()
    assert "TranslatorBabel/babel-test" in ua
    assert "https://github.com/NCATSTranslator/Babel" in ua


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
        "babel": {"github_url": "https://github.com/NCATSTranslator/Babel"},
    }

    with patch("urllib.request.build_opener", return_value=mock_opener), patch("src.babel_utils.get_config", return_value=fake_config):
        pull_via_urllib("http://example.com/", "test.txt", decompress=False)

    assert len(captured) == 1
    # urllib capitalises the first letter of each header name
    assert captured[0].get_header("User-agent") == "TranslatorBabel/babel-test (https://github.com/NCATSTranslator/Babel)"


# ---------------------------------------------------------------------------
# Unit tests for pull_omim_labels
# ---------------------------------------------------------------------------

_SAMPLE_MIM2GENE = (
    "# Copyright header\n"
    "# MIM Number\tMIM Entry Type\tEntrez Gene ID (NCBI)\tApproved Gene Symbol (HGNC)\tEnsembl Gene ID (Ensembl)\n"
    "100640\tgene\t216\tALDH1A1\tENSG00000165092\n"
    "100650\tgene\t217\tALDH2\tENSG00000111275\n"
    "100070\tphenotype\t100329167\t\t\n"
    "100071\tphenotype\t123\tPHENOSYM\t\n"
    "100500\tmoved/removed\t\t\t\n"
)


@pytest.fixture
def sample_mim2gene(tmp_path):
    p = tmp_path / "mim2gene.txt"
    p.write_text(_SAMPLE_MIM2GENE)
    return p


@pytest.mark.unit
def test_pull_omim_labels_writes_gene_symbols(sample_mim2gene, tmp_path):
    from src.datahandlers.omim import pull_omim_labels

    outfile = tmp_path / "labels"
    pull_omim_labels(str(sample_mim2gene), str(outfile))
    lines = outfile.read_text().splitlines()
    assert f"{OMIM}:100640\tALDH1A1" in lines
    assert f"{OMIM}:100650\tALDH2" in lines


@pytest.mark.unit
def test_pull_omim_labels_skips_empty_symbol(sample_mim2gene, tmp_path):
    from src.datahandlers.omim import pull_omim_labels

    outfile = tmp_path / "labels"
    pull_omim_labels(str(sample_mim2gene), str(outfile))
    content = outfile.read_text()
    assert f"{OMIM}:100070" not in content
    assert f"{OMIM}:100071" not in content
    assert f"{OMIM}:100500" not in content


@pytest.mark.unit
def test_pull_omim_labels_valid_structure(sample_mim2gene, tmp_path):
    from src.datahandlers.omim import pull_omim_labels

    outfile = tmp_path / "labels"
    pull_omim_labels(str(sample_mim2gene), str(outfile))
    assert_labels_file_valid(str(outfile))


# ---------------------------------------------------------------------------
# Network test: download the real file and check labels are produced
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_pull_omim_downloads_mim2gene():
    """pull_omim() should successfully download mim2gene.txt from omim.org."""
    from src.datahandlers.omim import pull_omim

    outfile = pull_omim()
    assert os.path.exists(outfile), f"Expected {outfile} to exist after pull_omim()"
    assert os.path.getsize(outfile) > 1024, f"mim2gene.txt is suspiciously small ({os.path.getsize(outfile)} bytes)"


@pytest.mark.network
def test_pull_omim_labels_from_downloaded_file(tmp_path):
    """pull_omim_labels() should produce a non-empty valid labels file from the real mim2gene.txt."""
    from src.datahandlers.omim import pull_omim, pull_omim_labels

    infile = pull_omim()
    outfile = tmp_path / "labels"
    pull_omim_labels(infile, str(outfile))

    rows = assert_labels_file_valid(str(outfile))
    curies = {row[0] for row in rows}
    # ALDH1A1 (MIM 100640) is a stable well-known gene entry
    assert f"{OMIM}:100640" in curies, "Expected OMIM:100640 (ALDH1A1) in labels"
    labels = {row[1] for row in rows}
    assert "ALDH1A1" in labels
