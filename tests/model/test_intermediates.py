"""Unit tests for src/model/intermediates.py, the shared reader for Babel's intermediate files.

Sections:

- ``# --- parse_concord_line / read_concords ---`` pins exactly which rows the shared concord
  parser accepts, including the whitespace edge cases ``line.strip()`` used to decide.
- ``# --- read_concord_pairs ---`` checks the ``(subject, object)`` view that compendium builders
  hand to ``glom()``.
- ``# --- scan_concord_lines ---`` checks the tally behind ``babel-check-concords``.
- ``# --- metadata sidecars ---`` pins which files in a ``concords/`` or ``ids/`` directory are
  metadata rather than data, the rule the DuckDB export, the checker and the source-impact report share.
"""

import pytest

from src.model.intermediates import (
    MalformedConcordRowError,
    is_metadata_sidecar,
    metadata_subject_filename,
    parse_concord_line,
    read_concord_pairs,
    read_concords,
    scan_concord_lines,
)

# --- parse_concord_line / read_concords ---


@pytest.mark.unit
@pytest.mark.parametrize(
    "line",
    [
        "NCIT:C150023\teq\tUniProtKB:Q9C0C9\n",
        "NCIT:C150023\teq\tUniProtKB:Q9C0C9\r\n",  # CRLF: only the terminator is removed
        "NCIT:C150023\teq\tUniProtKB:Q9C0C9",  # last line of a file with no final newline
    ],
)
def test_parse_accepts_three_columns(line):
    """Should return the three columns of a well-formed row, whatever its line terminator."""
    assert parse_concord_line(line, "concord", 1) == ("NCIT:C150023", "eq", "UniProtKB:Q9C0C9")


@pytest.mark.unit
@pytest.mark.parametrize(
    "line,reason",
    [
        ("NCIT:C150023\teq\n", "2 columns"),
        ("NCIT:C150023\teq\tUniProtKB:Q9C0C9\textra\n", "4 columns"),
        # A trailing tab is a fourth, empty column. line.strip() used to remove it and accept the row,
        # while DuckDB's read_csv in the export counted four columns and rejected it.
        ("NCIT:C150023\teq\tUniProtKB:Q9C0C9\t\n", "4 columns"),
        # An empty last column. line.strip() used to eat its delimiting tab and report two columns.
        ("NCIT:C150023\teq\t\n", "empty column"),
        ("NCIT:C150023\t\tUniProtKB:Q9C0C9\n", "empty column"),
        ("\teq\tUniProtKB:Q9C0C9\n", "empty column"),
        # Padding is rejected, not trimmed: the DuckDB export reads columns verbatim.
        ("NCIT:C150023\teq\tUniProtKB:Q9C0C9 \n", "whitespace around a column"),
        (" NCIT:C150023\teq\tUniProtKB:Q9C0C9\n", "whitespace around a column"),
        ("NCIT:C150023 \teq\tUniProtKB:Q9C0C9\n", "whitespace around a column"),
        ("\n", "1 columns"),  # a blank line
        ("   \n", "1 columns"),
    ],
)
def test_parse_rejects_malformed_row(line, reason):
    """Should raise naming the file, line number and kind of problem, rather than clean or skip the row."""
    with pytest.raises(MalformedConcordRowError, match=r"^concord:7 is not a valid concord row") as excinfo:
        parse_concord_line(line, "concord", 7)
    assert excinfo.value.reason == reason


@pytest.mark.unit
def test_malformed_row_error_is_a_value_error():
    """Should stay a ValueError, which callers and older tests catch."""
    assert issubclass(MalformedConcordRowError, ValueError)


@pytest.mark.unit
def test_read_concords_raises_at_the_bad_line(tmp_path):
    """Should yield the good rows, then raise at the first bad one with its 1-based line number."""
    concord = tmp_path / "UMLS"
    concord.write_text("UMLS:C1\teq\tMESH:D1\nUMLS:C2\teq\n")
    rows = read_concords(concord)
    assert next(rows) == ("UMLS:C1", "eq", "MESH:D1")
    with pytest.raises(MalformedConcordRowError, match=r"UMLS:2 is not a valid concord row \(2 columns\)"):
        next(rows)


@pytest.mark.unit
def test_read_concords_decodes_utf8(tmp_path):
    """Should decode a concord as UTF-8 whatever the locale, as babel-check-concords and the DuckDB export do."""
    concord = tmp_path / "MONDO"
    concord.write_bytes("MONDO:1\teq\tUMLS:C1\u00e9\n".encode("utf-8"))
    assert list(read_concords(concord)) == [("MONDO:1", "eq", "UMLS:C1\u00e9")]


# --- read_concord_pairs ---


@pytest.mark.unit
def test_read_concord_pairs_yields_tuples_in_file_order(tmp_path):
    """Should drop the predicate and yield 2-tuples in file order, which glom()'s tie-break depends on."""
    concord = tmp_path / "UniProtKB"
    concord.write_text("UniProtKB:P2\teq\tPR:2\nUniProtKB:P1\teq\tPR:1\n")
    pairs = list(read_concord_pairs(concord))
    assert pairs == [("UniProtKB:P2", "PR:2"), ("UniProtKB:P1", "PR:1")]
    assert all(type(pair) is tuple for pair in pairs)


@pytest.mark.unit
def test_read_concord_pairs_raises_on_a_malformed_row(tmp_path):
    """Should raise like read_concords() does, not skip the row, since it reads through it."""
    concord = tmp_path / "UMLS"
    concord.write_text("UMLS:C1\teq\tMESH:D1\nUMLS:C2\teq\tMESH:D2\t\n")
    with pytest.raises(MalformedConcordRowError, match=r"UMLS:2 is not a valid concord row \(4 columns\)"):
        list(read_concord_pairs(concord))


# --- scan_concord_lines ---


@pytest.mark.unit
def test_scan_tallies_rejects_by_reason():
    """Should count every row and every reject by kind, keeping the first example of each kind."""
    scan = scan_concord_lines(["A:1\teq\tB:1\n", "A:2\teq\n", "A:3\teq\tB:3\n", "A:4\teq\n", "A:5\teq\t\n"], "concord")
    assert scan.rows == 5
    assert scan.rejected == 3
    assert dict(scan.rejects) == {"2 columns": 2, "empty column": 1}
    assert scan.examples["2 columns"] == (2, "A:2\teq\n")


# --- metadata sidecars ---


@pytest.mark.unit
@pytest.mark.parametrize(
    "filename,expected",
    [
        ("metadata-Anatomy.txt.yaml", "Anatomy.txt"),
        ("Metadata-CHEBI.YAML", "CHEBI"),  # matched case-insensitively; the subject keeps its case
        ("metadata.yaml", "metadata.yaml"),  # describes its directory
        ("Anatomy.txt", None),
        ("CHEBI", None),
        # Neither of these is a sidecar by name, so both are data: a concord reader must not skip a
        # file the DuckDB export loads into Concord.parquet.
        ("metadata", None),
        ("UNICHEM.yaml", None),
    ],
)
def test_metadata_subject_filename(filename, expected):
    """A `metadata-<subject>.yaml` sidecar resolves to its subject filename, a bare
    `metadata.yaml` returns its own name (it describes its directory), and any other filename
    returns None so the caller treats it as data."""
    assert metadata_subject_filename(filename) == expected
    assert is_metadata_sidecar(filename) == (expected is not None)
