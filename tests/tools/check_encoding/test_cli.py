"""Unit tests for the ``babel-check-encoding`` CLI (src/tools/check_encoding/cli.py).

Only the CLI layer — path expansion, exit code, and the TSV it writes. The detector itself lives in
``src/synonyms/encoding.py`` and is tested in ``tests/synonyms/test_encoding.py``.
"""

import pytest

from src.tools.check_encoding.cli import find_files, main


def _write_labels(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{curie}\t{label}\n" for curie, label in rows), encoding="utf-8")


@pytest.mark.unit
def test_exit_code_is_zero_when_clean(tmp_path):
    _write_labels(tmp_path / "labels", [("CHEBI:15377", "water")])
    assert main([str(tmp_path / "labels")]) == 0


@pytest.mark.unit
def test_exit_code_is_one_when_damaged(tmp_path):
    """A non-zero exit lets a script gate on the survey without parsing its output."""
    _write_labels(tmp_path / "labels", [("PUBCHEM.COMPOUND:1", "Ã©tude")])
    assert main([str(tmp_path / "labels")]) == 1


@pytest.mark.unit
def test_recursive_finds_labels_synonyms_and_txt(tmp_path):
    _write_labels(tmp_path / "PUBCHEM.COMPOUND" / "labels", [("PUBCHEM.COMPOUND:1", "water")])
    _write_labels(tmp_path / "PUBCHEM.COMPOUND" / "synonyms", [("PUBCHEM.COMPOUND:1", "water")])
    (tmp_path / "Chemical.txt").write_text("{}\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("ignore me\n", encoding="utf-8")

    found = {p.name for p in find_files([str(tmp_path)], recursive=True)}
    assert found == {"labels", "synonyms", "Chemical.txt"}


@pytest.mark.unit
def test_directory_without_recursive_is_an_error(tmp_path):
    with pytest.raises(RuntimeError, match="--recursive"):
        find_files([str(tmp_path)], recursive=False)


@pytest.mark.unit
def test_out_tsv_lists_every_issue(tmp_path):
    _write_labels(
        tmp_path / "labels",
        [("CHEBI:15377", "water"), ("PUBCHEM.COMPOUND:1", "Ã©tude"), ("PUBCHEM.COMPOUND:2", "Ã¤ther")],
    )
    out_tsv = tmp_path / "issues.tsv"
    main([str(tmp_path / "labels"), "--out-tsv", str(out_tsv)])

    lines = out_tsv.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "file\tline\tcurie\ttext\treason"
    assert len(lines) == 3  # header + the two damaged rows; `water` is clean
    assert "PUBCHEM.COMPOUND:1" in lines[1]
    assert "PUBCHEM.COMPOUND:2" in lines[2]
