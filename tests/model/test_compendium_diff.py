"""Unit tests for src/model/compendium_diff.py — the build-vs-build compendium clique diff.

The CLI wrapper that drives these functions is tested separately in
``tests/tools/clique_diff/test_cli.py``.
"""

import gzip
import json

import pytest

from src.model.compendium_diff import (
    diff_builds,
    diff_compendium,
    load_cliques,
    load_compendium,
    resolve_compendium_path,
)


def _clique(*curies, biolink_type="biolink:Disease"):
    """Build a minimal compendium record whose leader is the first CURIE.

    Each identifier's label is ``label of <CURIE>`` so tests can tell a rendered label
    apart from the bare CURIE.
    """
    return {"type": biolink_type, "identifiers": [{"i": c, "l": f"label of {c}"} for c in curies]}


def _write_jsonl(path, cliques):
    path.write_text("".join(json.dumps(c) + "\n" for c in cliques))
    return str(path)


def _diff_one(before, after, compendium="Disease.txt"):
    """Diff a single compendium, deriving the after-location map the way diff_builds does."""
    after_location = {c: (compendium, leader) for c, leader in after.curie_to_leader.items()}
    return diff_compendium(compendium, before, {compendium: after}, after_location)


# --- Loading ---


@pytest.mark.unit
def test_load_compendium_streams_records(tmp_path):
    """load_compendium should yield one dict per JSONL record, in file order."""
    path = _write_jsonl(tmp_path / "Disease.txt", [_clique("MONDO:1"), _clique("MONDO:2")])
    assert [c["identifiers"][0]["i"] for c in load_compendium(path)] == ["MONDO:1", "MONDO:2"]


@pytest.mark.unit
def test_load_compendium_skips_blank_lines(tmp_path):
    """Blank lines are not records and must be skipped, not raised on.

    load_compendium is the single compendium reader shared with ``glom_diff``; a trailing
    newline or a blank separator line in a compendium must not crash either consumer.
    """
    path = tmp_path / "Disease.txt"
    path.write_text(json.dumps(_clique("MONDO:1")) + "\n\n" + json.dumps(_clique("MONDO:2")) + "\n\n")
    assert len(list(load_compendium(path))) == 2


@pytest.mark.unit
def test_load_compendium_reads_gzipped(tmp_path):
    """A gzipped compendium must yield exactly what the uncompressed one does.

    Finished builds distribute compendia as ``.txt.gz`` (``rule compress_compendium``), so the
    diff tools only ever see the compressed form once a build is done.
    """
    cliques = [_clique("MONDO:1"), _clique("MONDO:2")]
    plain = _write_jsonl(tmp_path / "Disease.txt", cliques)
    gzipped = tmp_path / "DiseaseGz.txt.gz"
    with gzip.open(gzipped, "wt") as f:
        f.write("".join(json.dumps(c) + "\n" for c in cliques))

    assert list(load_compendium(gzipped)) == list(load_compendium(plain))


@pytest.mark.unit
def test_resolve_compendium_path_prefers_txt_then_gz(tmp_path):
    """Uncompressed wins when both exist; the .gz is the fallback; None when neither is there."""
    assert resolve_compendium_path(tmp_path, "Disease.txt") is None

    (tmp_path / "Disease.txt.gz").write_bytes(gzip.compress(b""))
    assert resolve_compendium_path(tmp_path, "Disease.txt") == tmp_path / "Disease.txt.gz"

    (tmp_path / "Disease.txt").write_text("")
    assert resolve_compendium_path(tmp_path, "Disease.txt") == tmp_path / "Disease.txt"


@pytest.mark.unit
def test_load_cliques_extracts_leader_and_members(tmp_path):
    """load_cliques should key cliques by their first identifier and map every member to it.

    It should also capture each member's label and each clique's Biolink type for CSV
    annotation.
    """
    path = _write_jsonl(tmp_path / "Disease.txt", [_clique("MONDO:1", "MEDDRA:9", "UMLS:7")])
    loaded = load_cliques(path)
    assert loaded.cliques == {"MONDO:1": frozenset({"MONDO:1", "MEDDRA:9", "UMLS:7"})}
    assert loaded.curie_to_leader["MEDDRA:9"] == "MONDO:1"
    assert loaded.labels["MEDDRA:9"] == "label of MEDDRA:9"
    assert loaded.clique_type["MONDO:1"] == "biolink:Disease"


@pytest.mark.unit
def test_load_cliques_rejects_empty_identifiers(tmp_path):
    """A clique line with no identifiers is malformed and must raise ValueError.

    The message should name the offending record's ordinal so a bad line in a
    multi-million-record compendium can be located.
    """
    path = tmp_path / "Disease.txt"
    path.write_text(json.dumps(_clique("MONDO:1")) + "\n" + json.dumps({"identifiers": []}) + "\n")
    with pytest.raises(ValueError, match="clique 2 has no identifiers"):
        load_cliques(path)


# --- Diffing ---


@pytest.mark.unit
def test_identical_cliques_produce_no_rows(tmp_path):
    """A clique with identical membership in both builds should be omitted from the diff."""
    before = load_cliques(_write_jsonl(tmp_path / "b.txt", [_clique("MONDO:1", "MEDDRA:9")]))
    after = load_cliques(_write_jsonl(tmp_path / "a.txt", [_clique("MONDO:1", "MEDDRA:9")]))
    assert _diff_one(before, after) == []


@pytest.mark.unit
def test_leader_change_with_identical_membership_is_flagged(tmp_path):
    """A clique whose membership is unchanged but whose leader (preferred identifier)
    changed should be reported as a single 'leader_changed' row — not silently omitted,
    and not misreported as 'regrouped' — naming the old and new leader without repeating
    the (unchanged) membership.
    """
    before = load_cliques(_write_jsonl(tmp_path / "b.txt", [_clique("MONDO:1", "MEDDRA:9")]))
    # Same two members, but MEDDRA:9 is now first, so it's the new leader.
    after = load_cliques(_write_jsonl(tmp_path / "a.txt", [_clique("MEDDRA:9", "MONDO:1")]))
    records = _diff_one(before, after)
    assert len(records) == 1
    (record,) = records
    assert record["destination_kind"] == "leader_changed"
    assert record["before_leader"] == "MONDO:1"
    assert record["before_leader_label"] == "label of MONDO:1"
    assert record["before_leader_type"] == "biolink:Disease"
    assert record["destination"] == "MEDDRA:9"
    assert record["destination_label"] == "label of MEDDRA:9"
    assert record["destination_compendium"] == "Disease.txt"
    assert record["destination_type"] == "biolink:Disease"
    assert record["before_size"] == record["after_size"] == record["member_count"] == 2
    assert record["example_members"] == ""


@pytest.mark.unit
def test_dropped_member_is_flagged(tmp_path):
    """When a member present before is absent from every after compendium, it is 'dropped'.

    This is the close-match-guard regression signal: the separated CURIE leaves the output.
    """
    before = load_cliques(_write_jsonl(tmp_path / "b.txt", [_clique("MONDO:1", "MEDDRA:9")]))
    after = load_cliques(_write_jsonl(tmp_path / "a.txt", [_clique("MONDO:1")]))
    records = _diff_one(before, after)
    kept = [r for r in records if r["destination_kind"] == "kept"]
    dropped = [r for r in records if r["destination_kind"] == "dropped"]
    assert dropped and dropped[0]["example_members"] == 'MEDDRA:9 "label of MEDDRA:9"'
    # A dropped member has no destination clique, so every destination column is empty.
    assert dropped[0]["destination"] == "(dropped)"
    assert dropped[0]["destination_label"] == ""
    assert dropped[0]["destination_compendium"] == ""
    assert dropped[0]["destination_type"] == ""
    assert dropped[0]["after_size"] == 0
    assert kept and kept[0]["after_size"] == 1


@pytest.mark.unit
def test_moved_vs_dropped_distinguished_across_files(tmp_path):
    """A CURIE retyped into another compared compendium is 'moved', not 'dropped'.

    A moved row should name the *destination clique* it landed in — leader, label, type, size
    and compendium file — so the row is readable without inferring anything from
    ``example_members`` (which truncates at five members).
    """
    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    _write_jsonl(bdir / "Disease.txt", [_clique("MONDO:1", "HP:5")])
    _write_jsonl(bdir / "PhenotypicFeature.txt", [])
    # After: HP:5 left the Disease clique and joined a PhenotypicFeature clique led by HP:2.
    _write_jsonl(adir / "Disease.txt", [_clique("MONDO:1")])
    _write_jsonl(adir / "PhenotypicFeature.txt", [_clique("HP:2", "HP:5", biolink_type="biolink:PhenotypicFeature")])
    rows, summary = diff_builds(str(bdir), str(adir), ["Disease.txt", "PhenotypicFeature.txt"])
    disease_rows = [r for r in rows if r["compendium"] == "Disease.txt"]
    moved = [r for r in disease_rows if r["destination_kind"] == "moved"]
    assert moved and moved[0]["example_members"] == 'HP:5 "label of HP:5"'
    # The moved member's destination is the real after-clique, in the other compendium.
    assert moved[0]["destination"] == "HP:2"
    assert moved[0]["destination_label"] == "label of HP:2"
    assert moved[0]["destination_compendium"] == "PhenotypicFeature.txt"
    assert moved[0]["destination_type"] == "biolink:PhenotypicFeature"
    assert moved[0]["after_size"] == 2
    assert summary["Disease.txt"]["dropped_member_count"] == 0
    assert summary["Disease.txt"]["moved_member_count"] == 1
    # clique_count is nested with a before/after/diff/diff_percent breakdown.
    assert summary["Disease.txt"]["clique_count"] == {"before": 1, "after": 1, "diff": 0, "diff_percent": 0.0}


@pytest.mark.unit
def test_moved_members_landing_in_different_cliques_get_a_row_each(tmp_path):
    """Members that move to *different* after-cliques must not be lumped into one row.

    Grouping is by destination clique, so two moved members landing under two different
    leaders should produce two rows, each naming its own destination.
    """
    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    _write_jsonl(bdir / "Disease.txt", [_clique("MONDO:1", "HP:5", "MP:7")])
    _write_jsonl(bdir / "PhenotypicFeature.txt", [])
    _write_jsonl(adir / "Disease.txt", [_clique("MONDO:1")])
    _write_jsonl(
        adir / "PhenotypicFeature.txt",
        [
            _clique("HP:5", biolink_type="biolink:PhenotypicFeature"),
            _clique("MP:7", biolink_type="biolink:PhenotypicFeature"),
        ],
    )
    rows, summary = diff_builds(str(bdir), str(adir), ["Disease.txt", "PhenotypicFeature.txt"])
    moved = [r for r in rows if r["destination_kind"] == "moved"]
    assert sorted(r["destination"] for r in moved) == ["HP:5", "MP:7"]
    assert all(r["member_count"] == 1 for r in moved)
    assert summary["Disease.txt"]["moved_member_count"] == 2


@pytest.mark.unit
def test_new_after_clique_shows_only_in_count_delta(tmp_path):
    """A wholly new after-clique (no before counterpart) must not be a change row.

    It should surface only as a positive ``clique_count.diff`` — the exact behavior that makes
    a build adding many cliques show few change rows.
    """
    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    _write_jsonl(bdir / "PhenotypicFeature.txt", [_clique("HP:1", biolink_type="biolink:PhenotypicFeature")])
    # After adds a brand-new MP-only clique alongside the unchanged HP clique.
    _write_jsonl(
        adir / "PhenotypicFeature.txt",
        [
            _clique("HP:1", biolink_type="biolink:PhenotypicFeature"),
            _clique("MP:9", biolink_type="biolink:PhenotypicFeature"),
        ],
    )
    rows, summary = diff_builds(str(bdir), str(adir), ["PhenotypicFeature.txt"])
    assert rows == []  # nothing changed among before-cliques
    assert summary["PhenotypicFeature.txt"]["clique_count"] == {
        "before": 1,
        "after": 2,
        "diff": 1,
        "diff_percent": 100.0,
    }


@pytest.mark.unit
def test_diff_percent_is_null_when_before_compendium_was_empty(tmp_path):
    """A compendium that is empty before and populated after has an undefined percent change;
    ``diff_percent`` should be None (JSON ``null``), not 0.0 — which would read as "unchanged"."""
    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    _write_jsonl(bdir / "Disease.txt", [])
    _write_jsonl(adir / "Disease.txt", [_clique("MONDO:1")])
    _, summary = diff_builds(str(bdir), str(adir), ["Disease.txt"])
    assert summary["Disease.txt"]["clique_count"] == {"before": 0, "after": 1, "diff": 1, "diff_percent": None}


@pytest.mark.unit
def test_diff_percent_is_zero_when_both_compendia_are_empty(tmp_path):
    """Two empty compendia are genuinely unchanged, so diff_percent should be 0.0, not None."""
    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    _write_jsonl(bdir / "Disease.txt", [])
    _write_jsonl(adir / "Disease.txt", [])
    _, summary = diff_builds(str(bdir), str(adir), ["Disease.txt"])
    assert summary["Disease.txt"]["clique_count"] == {"before": 0, "after": 0, "diff": 0, "diff_percent": 0.0}
