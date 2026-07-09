"""Unit tests for src/datahandlers/obo.py that don't require network access."""

import json

import pytest

from src.datahandlers import obo
from tests.conftest import assert_synonyms_file_valid


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
    per-prefix synonyms file came out empty -- even though the common file and UberGraph
    itself had the data. Grouping by prefix should make both the common file and the
    per-prefix file contain the right rows, the latter with the 3 columns
    SynonymFactory.load_synonyms() expects."""
    synonyms = [
        ("MP:0000002", "hasExactSynonym", "Anatomy"),
        ("MP:0000005", "hasExactSynonym", "increased brown fat"),
        ("GO:0000001", "hasExactSynonym", "mitochondrion inheritance"),
    ]
    monkeypatch.setattr(obo, "UberGraph", lambda: _FakeUberGraph(synonyms))

    common_file = tmp_path / "common_synonyms.jsonl"
    mp_synonyms_file = tmp_path / "MP" / "synonyms"

    obo.pull_uber_synonyms(str(common_file), [str(mp_synonyms_file)])

    common_rows = [json.loads(line) for line in common_file.read_text().splitlines()]
    assert {row["curie"] for row in common_rows} == {"MP:0000002", "MP:0000005", "GO:0000001"}

    mp_rows = assert_synonyms_file_valid(str(mp_synonyms_file))
    assert len(mp_rows) == 2
    assert all(cols[0].startswith("MP:") for cols in mp_rows)


@pytest.mark.unit
def test_pull_uber_synonyms_skips_non_ontology_prefixes(tmp_path, monkeypatch):
    """Results that aren't real ontology CURIEs -- bare IRIs, the `ro` and `t...` prefixes,
    and anything containing '#' -- should be dropped from the common synonyms file rather
    than written out as bogus identifiers."""
    synonyms = [
        ("CHEBI:15377", "hasExactSynonym", "water"),
        ("http://example.org/x", "hasExactSynonym", "ignored"),
        ("ro:0000001", "hasExactSynonym", "ignored"),
        ("t123:456", "hasExactSynonym", "ignored"),
        ("foo#bar:1", "hasExactSynonym", "ignored"),
        ("no_colon_here", "hasExactSynonym", "ignored"),
    ]
    monkeypatch.setattr(obo, "UberGraph", lambda: _FakeUberGraph(synonyms))

    common_file = tmp_path / "common_synonyms.jsonl"
    obo.pull_uber_synonyms(str(common_file), [])

    common_rows = [json.loads(line) for line in common_file.read_text().splitlines()]
    assert [row["curie"] for row in common_rows] == ["CHEBI:15377"]


@pytest.mark.unit
def test_pull_uber_synonyms_raises_for_missing_prefix(tmp_path, monkeypatch):
    """Every prefix we generate a per-prefix file for is a large OBO ontology that certainly has
    synonyms, so a prefix missing from the UberGraph results means the download or our filtering
    broke. pull_uber_synonyms() should raise (as pull_uber_labels() does) rather than leave an
    empty file behind for the rest of the build to consume."""
    monkeypatch.setattr(obo, "UberGraph", lambda: _FakeUberGraph([("GO:0000001", "hasExactSynonym", "foo")]))

    common_file = tmp_path / "common_synonyms.jsonl"
    mp_synonyms_file = tmp_path / "MP" / "synonyms"

    with pytest.raises(ValueError, match="MP"):
        obo.pull_uber_synonyms(str(common_file), [str(mp_synonyms_file)])

    assert not mp_synonyms_file.exists()
