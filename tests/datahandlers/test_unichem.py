"""Network tests for the UniChem download.

These verify that the UniChem FTP mirror URLs are reachable with the User-Agent
Babel sends, that each file is a valid gzip archive, and that the reference file
header matches the constant in unichem.py.
Run with: uv run pytest --network tests/datahandlers/test_unichem.py
"""

import gzip
import io
import urllib.error
import urllib.request

import pytest

from src.babel_utils import get_user_agent
from src.datahandlers.unichem import UNICHEM_REFERENCE_TSV_HEADER

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
    assert raw[:2] == b"\x1f\x8b", (
        f"UniChem {filename} does not appear to be a gzip file (got {raw[:2]!r})"
    )

    # Try to decompress the partial chunk to catch obviously truncated/corrupt files.
    try:
        # wbits=47 tells zlib to accept gzip format; partial streams raise EOFError,
        # which we allow — we only care that the header and first block are valid.
        import zlib

        d = zlib.decompressobj(wbits=47)
        d.decompress(raw)
    except zlib.error as exc:
        pytest.fail(f"UniChem {filename} first 64 KB failed gzip decompression: {exc}")


@pytest.mark.slow
def test_unichem_reference_header_matches_expected():
    """The first line of reference.tsv.gz must match UNICHEM_REFERENCE_TSV_HEADER exactly.

    This test downloads a small initial chunk of the file (~256 KB) and decompresses
    it to read the header.  It guards against upstream format changes like the
    2026-06 rename of 'ASSIGNMENT' → 'ASSIGMENT'.
    """
    url = UNICHEM_BASE + "reference.tsv.gz"
    req = urllib.request.Request(url, headers={"User-Agent": get_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read(262144)  # 256 KB — header is always in the first block
    except urllib.error.HTTPError as e:
        pytest.fail(f"UniChem reference.tsv.gz returned HTTP {e.code}: {e}")

    assert raw[:2] == b"\x1f\x8b", "reference.tsv.gz does not look like a gzip file"

    try:
        with gzip.open(io.BytesIO(raw), "rt") as gz:
            header = gz.readline()
    except EOFError:
        # Partial gzip stream at end of chunk is expected; we already got the header
        # by this point since readline() returned before raising.
        pass
    except Exception as exc:
        pytest.fail(f"Could not decompress initial chunk of reference.tsv.gz: {exc}")

    assert header == UNICHEM_REFERENCE_TSV_HEADER, (
        f"UniChem reference.tsv.gz header has changed — update UNICHEM_REFERENCE_TSV_HEADER in "
        f"src/datahandlers/unichem.py.\n"
        f"  Expected : {UNICHEM_REFERENCE_TSV_HEADER!r}\n"
        f"  Got      : {header!r}"
    )
