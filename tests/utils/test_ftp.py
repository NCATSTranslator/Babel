"""Unit tests for src/utils/ftp.py, and for pull_via_ftp() in src/babel_utils.py, which downloads through it.

Every test uses a fake FTP server; tests/test_ftp.py covers pull_via_ftp() against NCBI's real one (network).
"""

import ftplib
import gzip
import hashlib
import posixpath
from unittest.mock import patch

import pytest

from src.babel_utils import pull_via_ftp
from src.utils.ftp import ftp_path_exists, list_ftp_dir, retrieve_ftp_file


class _FakeFTP:
    """A fake ftplib.FTP holding the directories in ``tree`` (absolute path -> names in it) and serving ``files``
    (name -> bytes). NLST of a missing directory raises ``missing_error``, so a test can give it any wording."""

    def __init__(self, tree, files=None, missing_error=None, fail_listing=None, fail_after_bytes=None):
        self.tree = tree
        self.files = files or {}
        self.missing_error = missing_error or ftplib.error_temp("450 No such file or directory")
        self.fail_listing = fail_listing  # a directory whose listing fails transiently
        self.fail_after_bytes = fail_after_bytes  # drop the connection after sending this many bytes

    def __call__(self, site):
        return self

    def login(self):
        pass

    def cwd(self, ftpdir):
        pass

    def quit(self):
        pass

    def nlst(self, ftpdir):
        if ftpdir == self.fail_listing:
            raise ftplib.error_temp("421 Service not available, closing control connection")
        if ftpdir not in self.tree:
            raise self.missing_error
        return [posixpath.join(ftpdir, name) for name in self.tree[ftpdir]]

    def retrbinary(self, cmd, callback):
        data = self.files[cmd.removeprefix("RETR ")]
        for i in range(0, len(data), 4):
            if self.fail_after_bytes is not None and i >= self.fail_after_bytes:
                raise EOFError("connection dropped")
            callback(data[i : i + 4])


_TREE = {
    "/": ["online"],
    "/online": ["mesh"],
    "/online/mesh": ["2025", "MESH_FILES"],
    "/online/mesh/2025": ["xmlmesh"],
    "/online/mesh/2025/xmlmesh": ["desc2025.gz", "supp2025.gz"],
}


# ftp_path_exists() and list_ftp_dir()


@pytest.mark.unit
def test_ftp_path_exists_walks_the_parent_listings():
    """A directory or file should exist only if each of its parents lists it."""
    ftp = _FakeFTP(_TREE)
    assert ftp_path_exists(ftp, "/online/mesh/2025/xmlmesh")
    assert ftp_path_exists(ftp, "/online/mesh/2025/xmlmesh/desc2025.gz")
    assert not ftp_path_exists(ftp, "/online/mesh/2026/xmlmesh")
    assert not ftp_path_exists(ftp, "/online/mesh/2025/asciimesh")


@pytest.mark.unit
@pytest.mark.parametrize(
    "missing_error",
    [ftplib.error_temp("450 No such file or directory"), ftplib.error_perm("550 No files found")],
)
def test_list_ftp_dir_absent_whatever_the_servers_wording(missing_error):
    """A missing directory should list as empty however the server words or codes its error, because that
    error is never asked for."""
    assert list_ftp_dir(_FakeFTP(_TREE, missing_error=missing_error), "/online/mesh/2026/xmlmesh") == set()


@pytest.mark.unit
def test_list_ftp_dir_returns_basenames():
    """An existing directory should list as bare file names, whether the server returns names or paths."""
    assert list_ftp_dir(_FakeFTP(_TREE), "/online/mesh/2025/xmlmesh") == {"desc2025.gz", "supp2025.gz"}


@pytest.mark.unit
def test_list_ftp_dir_raises_a_failed_listing():
    """A transient failure listing a parent should be raised, not read as "this directory does not exist"."""
    with pytest.raises(ftplib.error_temp, match="421"):
        list_ftp_dir(_FakeFTP(_TREE, fail_listing="/online/mesh"), "/online/mesh/2025/xmlmesh")


@pytest.mark.unit
def test_ftp_path_exists_rejects_a_relative_path():
    """A relative path cannot be walked from "/", so it should raise rather than answer for the wrong path."""
    with pytest.raises(ValueError, match="absolute"):
        ftp_path_exists(_FakeFTP(_TREE), "online/mesh")


# retrieve_ftp_file()


@pytest.mark.unit
def test_retrieve_ftp_file_returns_sha1(tmp_path):
    """A completed download should be at out_path, with no .part file, and its SHA-1 returned."""
    data = b"some MeSH bytes"
    out = tmp_path / "desc.xml.gz"
    assert retrieve_ftp_file(_FakeFTP({}, {"f": data}), "f", out) == hashlib.sha1(data).hexdigest()
    assert out.read_bytes() == data
    assert list(tmp_path.iterdir()) == [out]


@pytest.mark.unit
def test_retrieve_ftp_file_leaves_nothing_when_interrupted(tmp_path):
    """An interrupted transfer should raise and leave neither out_path nor its .part file."""
    with pytest.raises(EOFError):
        retrieve_ftp_file(_FakeFTP({}, {"f": b"x" * 40}, fail_after_bytes=12), "f", tmp_path / "out")
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
        with patch("src.babel_utils.FTP", _FakeFTP({}, {"f": data})):
            out = pull_via_ftp("ftp.example.org", "/dir", "f", decompress_data=decompress, outfilename="SRC/out")
        assert open(out).read() == text
        assert sorted(p.name for p in (tmp_path / "SRC").iterdir()) == ["out"]

        (tmp_path / "SRC" / "out").unlink()
        with patch("src.babel_utils.FTP", _FakeFTP({}, {"f": data}, fail_after_bytes=8)):
            with pytest.raises(EOFError):
                pull_via_ftp("ftp.example.org", "/dir", "f", decompress_data=decompress, outfilename="SRC/out")
        assert list((tmp_path / "SRC").iterdir()) == []
