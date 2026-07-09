"""
Unit tests for tools/clique_diff/diff.py — the build-vs-build compendium clique diff.

Sections:

- ``# --- Loading ---`` covers JSONL parsing and the leader/member extraction.
- ``# --- Diffing ---`` covers the five destination kinds
  (kept/leader_changed/regrouped/moved/dropped), the "unchanged clique is omitted" rule, the
  nested ``clique_count`` breakdown, and that a wholly new after-clique shows only in the count
  delta.
- ``# --- CLI ---`` covers the self-describing ``about`` block written by ``main()``.
"""

import json

import pytest

from tools.clique_diff.diff import diff_builds, diff_compendium, load_cliques


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
def test_load_cliques_extracts_leader_and_members(tmp_path):
    """load_cliques should key cliques by their first identifier and map every member to it.

    It should also capture each member's label and each clique's Biolink type for CSV
    annotation, while still unpacking as the historical ``(cliques, curie_to_leader)`` tuple.
    """
    path = _write_jsonl(tmp_path / "Disease.txt", [_clique("MONDO:1", "MEDDRA:9", "UMLS:7")])
    loaded = load_cliques(path)
    assert loaded.cliques == {"MONDO:1": frozenset({"MONDO:1", "MEDDRA:9", "UMLS:7"})}
    assert loaded.curie_to_leader["MEDDRA:9"] == "MONDO:1"
    assert loaded.labels["MEDDRA:9"] == "label of MEDDRA:9"
    assert loaded.clique_type["MONDO:1"] == "biolink:Disease"
    # Backward-compatible 2-tuple unpacking still works.
    cliques, leader_of = load_cliques(path)
    assert cliques == loaded.cliques
    assert leader_of == loaded.curie_to_leader


@pytest.mark.unit
def test_load_cliques_rejects_empty_identifiers(tmp_path):
    """A clique line with no identifiers is malformed and must raise ValueError."""
    path = tmp_path / "Disease.txt"
    path.write_text(json.dumps({"identifiers": []}) + "\n")
    with pytest.raises(ValueError, match="no identifiers"):
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


# --- CLI ---


@pytest.mark.unit
def test_cli_writes_self_describing_summary(tmp_path):
    """main() should wrap the per-compendium summary in an ``about`` block carrying the
    baseline labels, note, and compared files, so the JSON explains its own provenance.
    """
    from tools.clique_diff.diff import main

    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    _write_jsonl(bdir / "Disease.txt", [_clique("MONDO:1", "MEDDRA:9")])
    _write_jsonl(adir / "Disease.txt", [_clique("MONDO:1", "MEDDRA:9")])
    out_json = tmp_path / "summary.json"
    main(
        [
            "--before",
            str(bdir),
            "--after",
            str(adir),
            "--files",
            "Disease.txt",
            "--out-csv",
            str(tmp_path / "diff.csv"),
            "--out-json",
            str(out_json),
            "--before-label",
            "main (no MP)",
            "--after-label",
            "branch",
            "--note",
            "isolates X",
        ]
    )
    out = json.loads(out_json.read_text())
    assert out["about"] == {
        "before": "main (no MP)",
        "after": "branch",
        "note": "isolates X",
        "files": ["Disease.txt"],
    }
    assert "Disease.txt" in out["compendia"]
