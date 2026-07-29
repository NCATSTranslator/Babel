"""Unit tests for src.babel_utils.read_concord_file.

read_concord_file is the single reader every compendium builder uses for concord files, replacing
the ``line.strip().split("\\t")`` idiom that was duplicated across nine modules. Its contract is
narrow on purpose -- pairs in file order, blank lines skipped, anything else raises -- because
those three properties are what the callers depend on:

- **order** because :func:`glom` is order-sensitive, so which pair merges first decides which later
  pair a ``unique_prefixes`` conflict rejects;
- **blank lines skipped** because a concord that ends in a newline yields one;
- **short rows raise** because they mean a truncated or malformed concord, and silently dropping
  them would quietly shrink cliques. Before this function, ``glom_from_files`` skipped such rows
  while the other eight call sites raised IndexError; raising everywhere is the deliberate choice.
"""

import pytest

from src.babel_utils import read_concord_file

# Copied verbatim from babel_outputs/intermediate/anatomy/concords/UMLS, which is
# `CURIE1 \t PREDICATE \t CURIE2`. UMLS:C0000726 is "Abdomen".
REAL_CONCORD_ROWS = [
    "UMLS:C0000726\teq\tMESH:D000005",
    "UMLS:C0000726\teq\tFMA:9577",
    "UMLS:C0000726\teq\tSNOMEDCT:818983003",
]


def write_concord(tmp_path, text, name="SRC"):
    path = tmp_path / name
    path.write_text(text)
    return path


# READING WELL-FORMED CONCORDS


@pytest.mark.unit
def test_reads_subject_and_object_dropping_the_predicate(tmp_path):
    """Each row should yield a `(subject, object)` tuple; the predicate column is not returned."""
    path = write_concord(tmp_path, "\n".join(REAL_CONCORD_ROWS) + "\n")
    assert read_concord_file(path) == [
        ("UMLS:C0000726", "MESH:D000005"),
        ("UMLS:C0000726", "FMA:9577"),
        ("UMLS:C0000726", "SNOMEDCT:818983003"),
    ]


@pytest.mark.unit
def test_preserves_file_order(tmp_path):
    """Pairs come back in file order, because glom() is order-sensitive."""
    path = write_concord(tmp_path, "\n".join(reversed(REAL_CONCORD_ROWS)) + "\n")
    assert [obj for _, obj in read_concord_file(path)] == ["SNOMEDCT:818983003", "FMA:9577", "MESH:D000005"]


@pytest.mark.unit
def test_an_empty_file_reads_as_no_pairs(tmp_path):
    """An empty concord is legitimate -- some sources contribute none -- and is not an error."""
    assert read_concord_file(write_concord(tmp_path, "")) == []


@pytest.mark.unit
def test_extra_columns_are_ignored(tmp_path):
    """Only columns 1 and 3 are read, so a source that appends its own columns still parses."""
    path = write_concord(tmp_path, "UMLS:C0000726\teq\tMESH:D000005\t0.98\tsome-provenance\n")
    assert read_concord_file(path) == [("UMLS:C0000726", "MESH:D000005")]


# MALFORMED INPUT


@pytest.mark.unit
@pytest.mark.parametrize(
    "text,description",
    [
        ("\n".join(REAL_CONCORD_ROWS) + "\n\n", "trailing blank line, as a file ending in a newline gives"),
        ("\n" + "\n".join(REAL_CONCORD_ROWS) + "\n", "leading blank line"),
        ("\n".join(REAL_CONCORD_ROWS) + "\n   \n", "whitespace-only line"),
    ],
)
def test_blank_lines_are_skipped(tmp_path, text, description):
    """Blank and whitespace-only lines should be skipped rather than raising."""
    assert len(read_concord_file(write_concord(tmp_path, text))) == len(REAL_CONCORD_ROWS), description


@pytest.mark.unit
@pytest.mark.parametrize(
    "row",
    [
        "UMLS:C0000726",  # subject only -- a line truncated mid-write
        "UMLS:C0000726\teq",  # subject and predicate, object lost
        "UMLS:C0000726 eq MESH:D000005",  # space separated, not tab
    ],
)
def test_a_short_row_raises(tmp_path, row):
    """A non-blank row with fewer than three fields means a malformed concord, and must raise.

    Silently skipping these is what glom_from_files used to do, and it would let a concord
    truncated by a killed job build quietly smaller cliques instead of failing the run.
    """
    path = write_concord(tmp_path, REAL_CONCORD_ROWS[0] + "\n" + row + "\n")
    with pytest.raises(ValueError, match="expected at least 3"):
        read_concord_file(path)


@pytest.mark.unit
def test_the_error_names_the_file_and_line(tmp_path):
    """The message should locate the bad row, since these files have millions of lines."""
    path = write_concord(tmp_path, "\n".join(REAL_CONCORD_ROWS) + "\nUMLS:C0000726\n")
    with pytest.raises(ValueError, match=r"line 4"):
        read_concord_file(path)
