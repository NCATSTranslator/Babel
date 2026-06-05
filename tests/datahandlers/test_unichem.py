"""Network tests for the UniChem download.

These verify that the UniChem FTP mirror URLs are reachable with the User-Agent
Babel sends and that each file is a valid gzip archive.
Run with: uv run pytest --network tests/datahandlers/test_unichem.py
"""

import urllib.error
import urllib.request

import pytest

from src.babel_utils import get_user_agent

pytestmark = [pytest.mark.network]

UNICHEM_BASE = "http://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/"
UNICHEM_FILES = ["structure.tsv.gz", "reference.tsv.gz"]


@pytest.mark.parametrize("filename", UNICHEM_FILES)
def test_unichem_url_accessible_with_user_agent(filename):
    """UniChem file should be reachable and return a valid gzip stream."""
    url = UNICHEM_BASE + filename
    req = urllib.request.Request(url, headers={"User-Agent": get_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            # Read the first 64 KB and confirm it decompresses without error.
            raw = resp.read(65536)
    except urllib.error.HTTPError as e:
        pytest.fail(
            f"UniChem {filename} returned HTTP {e.code} with User-Agent '{get_user_agent()}'. "
            "The server may be unreachable or blocking this client."
        )

    assert len(raw) > 0, f"UniChem {filename} returned an empty body"

    # Confirm the bytes are a valid gzip stream (magic bytes 0x1f 0x8b).
    assert raw[:2] == b"\x1f\x8b", f"UniChem {filename} does not appear to be a gzip file (got {raw[:2]!r})"

    # Try to decompress the partial chunk to catch obviously truncated/corrupt files.
    try:
        # wbits=47 tells zlib to accept gzip format; partial streams raise EOFError,
        # which we allow — we only care that the header and first block are valid.
        import zlib

        d = zlib.decompressobj(wbits=47)
        d.decompress(raw)
    except zlib.error as exc:
        pytest.fail(f"UniChem {filename} first 64 KB failed gzip decompression: {exc}")
