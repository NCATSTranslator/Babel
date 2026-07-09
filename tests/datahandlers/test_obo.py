"""Unit tests for src/datahandlers/obo.py that don't require network access."""

import json

import pytest

from src.datahandlers import obo


class _FakeUberGraph:
    """Stand-in for src.ubergraph.UberGraph returning a fixed synonym set."""

    def __init__(self, synonyms):
        self._synonyms = synonyms

    def get_all_synonyms(self):
        return self._synonyms


# ---------------------------------------------------------------------------
# pull_uber_synonyms
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_uber_synonyms_groups_by_prefix_not_curie(tmp_path, monkeypatch):
    """Regression test: pull_uber_synonyms() used to key its internal dict by full CURIE
    (e.g. "MP:0000002"), so `prefix in ldict` (prefix == "MP") was always False and every
    per-prefix synonyms file came out empty with a spurious "not found" warning -- even
    though the common file and UberGraph itself had the data. Grouping by prefix should
    make both the common file and the per-prefix file contain the right rows."""
    synonyms = [
        ("MP:0000002", "hasExactSynonym", "Anatomy"),
        ("MP:0000005", "hasExactSynonym", "increased brown fat"),
        ("GO:0000001", "hasExactSynonym", "mitochondrion inheritance"),
    ]
    monkeypatch.setattr(obo, "UberGraph", lambda: _FakeUberGraph(synonyms))

    common_file = tmp_path / "common_synonyms.jsonl"
    mp_dir = tmp_path / "MP"
    mp_dir.mkdir()
    mp_synonyms_file = mp_dir / "synonyms"

    obo.pull_uber_synonyms(str(common_file), [str(mp_synonyms_file)])

    common_rows = [json.loads(line) for line in common_file.read_text().splitlines()]
    assert {row["curie"] for row in common_rows} == {"MP:0000002", "MP:0000005", "GO:0000001"}

    mp_rows = [line.split("\t") for line in mp_synonyms_file.read_text().splitlines()]
    assert len(mp_rows) == 2
    for cols in mp_rows:
        assert len(cols) == 3, f"Expected 3 columns (CURIE, predicate, synonym), got {cols}"
        assert cols[0].startswith("MP:")


@pytest.mark.unit
def test_pull_uber_synonyms_warns_and_writes_empty_for_missing_prefix(tmp_path, monkeypatch, caplog):
    """A prefix truly absent from the UberGraph synonym results should still warn and
    produce an empty (not missing) file, so Snakemake's declared output exists."""
    monkeypatch.setattr(obo, "UberGraph", lambda: _FakeUberGraph([("GO:0000001", "hasExactSynonym", "foo")]))

    common_file = tmp_path / "common_synonyms.jsonl"
    mp_dir = tmp_path / "MP"
    mp_dir.mkdir()
    mp_synonyms_file = mp_dir / "synonyms"

    with caplog.at_level("WARNING"):
        obo.pull_uber_synonyms(str(common_file), [str(mp_synonyms_file)])

    assert "MP" in caplog.text
    assert mp_synonyms_file.read_text() == ""
