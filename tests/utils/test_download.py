"""Unit tests for src/utils/download.py, and for pull_via_ftp() in src/babel_utils.py, which downloads through it.

Every test uses a fake FTP server; tests/test_ftp.py covers pull_via_ftp() against NCBI's real one (network).
"""

import gzip
import hashlib
from unittest.mock import patch

import pytest

from src.babel_utils import pull_via_ftp
from src.utils.download import retrieve_ftp_file


class _FakeFTP:
    """A fake ftplib.FTP serving ``files`` (name -> bytes)."""

    def __init__(self, files, fail_after_bytes=None):
        self.files = files
        self.fail_after_bytes = fail_after_bytes  # drop the connection after sending this many bytes

    def __call__(self, site):
        return self

    def login(self):
        pass

    def cwd(self, ftpdir):
        pass

    def quit(self):
        pass

    def retrbinary(self, cmd, callback):
        data = self.files[cmd.removeprefix("RETR ")]
        for i in range(0, len(data), 4):
            if self.fail_after_bytes is not None and i >= self.fail_after_bytes:
                raise EOFError("connection dropped")
            callback(data[i : i + 4])


# retrieve_ftp_file()


@pytest.mark.unit
def test_retrieve_ftp_file_returns_sha1(tmp_path):
    """A completed download should be at out_path, with no .part file, and its SHA-1 returned."""
    data = b"some MeSH bytes"
    out = tmp_path / "desc.xml.gz"
    assert retrieve_ftp_file(_FakeFTP({"f": data}), "f", out) == hashlib.sha1(data).hexdigest()
    assert out.read_bytes() == data
    assert list(tmp_path.iterdir()) == [out]


@pytest.mark.unit
def test_retrieve_ftp_file_leaves_nothing_when_interrupted(tmp_path):
    """An interrupted transfer should raise and leave neither out_path nor its .part file."""
    with pytest.raises(EOFError):
        retrieve_ftp_file(_FakeFTP({"f": b"x" * 40}, fail_after_bytes=12), "f", tmp_path / "out")
    assert list(tmp_path.iterdir()) == []


# pull_via_ftp()


@pytest.mark.unit
@pytest.mark.parametrize("decompress", [False, True])
def test_pull_via_ftp_writes_complete_files_only(tmp_path, decompress):
    """pull_via_ftp() should write the (optionally decompressed) file when the transfer completes, and leave
    nothing under its name, or beside it, when the transfer is interrupted."""
    text = "line one\nline two\n" * 5
    data = gzip.compress(text.encode()) if decompress else text.encode()
    config = {"download_directory": str(tmp_path)}
    with patch("src.babel_utils.get_config", return_value=config):
        with patch("src.babel_utils.FTP", _FakeFTP({"f": data})):
            out = pull_via_ftp("ftp.example.org", "/dir", "f", decompress_data=decompress, outfilename="SRC/out")
        assert open(out).read() == text
        assert sorted(p.name for p in (tmp_path / "SRC").iterdir()) == ["out"]

        (tmp_path / "SRC" / "out").unlink()
        with patch("src.babel_utils.FTP", _FakeFTP({"f": data}, fail_after_bytes=8)):
            with pytest.raises(EOFError):
                pull_via_ftp("ftp.example.org", "/dir", "f", decompress_data=decompress, outfilename="SRC/out")
        assert list((tmp_path / "SRC").iterdir()) == []
