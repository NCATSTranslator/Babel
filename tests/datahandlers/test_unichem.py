"""Tests for src/datahandlers/unichem.py.

The unit tests cover filter_unichem() over small synthetic reference files. The network tests
verify that the UniChem HTTP mirror URLs are reachable with the User-Agent Babel sends, that each
file is a valid gzip archive, and that the reference file header matches the constant in
unichem.py; run them with: uv run pytest --network tests/datahandlers/test_unichem.py
"""

import gzip
import io
import urllib.error
import urllib.request
import zlib

import pytest

from src.babel_utils import get_user_agent
from src.datahandlers.unichem import UNICHEM_REFERENCE_TSV_HEADER, data_sources, filter_unichem

UNICHEM_BASE = "http://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/"
UNICHEM_FILES = ["structure.tsv.gz", "reference.tsv.gz"]


# FILTERING THE REFERENCE FILE


def _write_reference(path, rows):
    """Write a gzipped UniChem reference file; rows are (uci, src_id, src_compound_id, assignment)."""
    with gzip.open(path, "wt") as out:
        out.write(UNICHEM_REFERENCE_TSV_HEADER)
        for row in rows:
            out.write("\t".join(row) + "\n")


@pytest.mark.unit
def test_filter_unichem_keeps_only_current_rows_of_the_sources_it_is_given(tmp_path):
    """filter_unichem() should keep the header and the current (assignment 1) rows of exactly the
    source IDs passed to it, whatever data_sources holds, and drop obsolete (assignment 0) rows. The
    list comes in as an argument, from rule filter_unichem's params:, so that changing it re-runs
    the rule; this asks for GtoPdb (not in data_sources) and leaves out ChEBI (in it)."""
    assert "4" not in data_sources and "7" in data_sources
    ref = tmp_path / "reference.tsv.gz"
    _write_reference(
        ref,
        [
            ("1", "1", "CHEMBL1", "1"),  # wanted
            ("2", "1", "CHEMBL2", "0"),  # wanted source, obsolete assignment
            ("3", "4", "5688", "1"),  # GtoPdb: wanted here, though not in data_sources
            ("4", "7", "CHEBI:1", "1"),  # ChEBI: in data_sources, but not asked for
        ],
    )
    out = tmp_path / "reference.filtered.tsv"

    filter_unichem(str(ref), str(out), ["1", "4"])

    assert out.read_text() == UNICHEM_REFERENCE_TSV_HEADER + "1\t1\tCHEMBL1\t1\n3\t4\t5688\t1\n"


# NETWORK


@pytest.mark.network
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
        d = zlib.decompressobj(wbits=47)
        d.decompress(raw)
    except zlib.error as exc:
        pytest.fail(f"UniChem {filename} first 64 KB failed gzip decompression: {exc}")


@pytest.mark.network
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

    header = ""
    try:
        with gzip.open(io.BytesIO(raw), "rt") as gz:
            header = gz.readline()
    except EOFError:
        # A partial gzip stream at the end of the chunk is expected. readline() may have
        # already populated `header` before the stream ended; if it didn't, fail loudly.
        if not header:
            pytest.fail("reference.tsv.gz: gzip stream ended before a complete header line could be read")
    except Exception as exc:
        pytest.fail(f"Could not decompress initial chunk of reference.tsv.gz: {exc}")

    assert header == UNICHEM_REFERENCE_TSV_HEADER, (
        f"UniChem reference.tsv.gz header has changed — update UNICHEM_REFERENCE_TSV_HEADER in "
        f"src/datahandlers/unichem.py.\n"
        f"  Expected : {UNICHEM_REFERENCE_TSV_HEADER!r}\n"
        f"  Got      : {header!r}"
    )
