"""
Unit tests for tools/clique_diff/diff.py — the build-vs-build compendium clique diff.

Sections:

- ``# --- Loading ---`` covers JSONL parsing and the leader/member extraction.
- ``# --- Diffing ---`` covers the five destination kinds
  (kept/leader_changed/regrouped/moved/dropped) and the "unchanged clique is omitted" rule.
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
    records = diff_compendium(before, after, set(after.curie_to_leader), {})
    assert records == []


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
    records = diff_compendium(before, after, set(after.curie_to_leader), {})
    assert len(records) == 1
    (record,) = records
    assert record["destination_kind"] == "leader_changed"
    assert record["before_leader"] == "MONDO:1"
    assert record["before_leader_label"] == "label of MONDO:1"
    assert record["before_leader_type"] == "biolink:Disease"
    assert record["destination"] == "MEDDRA:9"
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
    records = diff_compendium(before, after, set(after.curie_to_leader), {})
    kept = [r for r in records if r["destination_kind"] == "kept"]
    dropped = [r for r in records if r["destination_kind"] == "dropped"]
    assert dropped and dropped[0]["example_members"] == 'MEDDRA:9 "label of MEDDRA:9"'
    assert dropped[0]["destination_type"] == ""
    assert kept and kept[0]["after_size"] == 1


@pytest.mark.unit
def test_moved_vs_dropped_distinguished_across_files(tmp_path):
    """A CURIE retyped into another compared compendium is 'moved', not 'dropped'."""
    bdir, adir = tmp_path / "before", tmp_path / "after"
    bdir.mkdir()
    adir.mkdir()
    _write_jsonl(bdir / "Disease.txt", [_clique("MONDO:1", "HP:5")])
    _write_jsonl(bdir / "PhenotypicFeature.txt", [])
    # After: HP:5 left the Disease clique and now leads its own PhenotypicFeature clique.
    _write_jsonl(adir / "Disease.txt", [_clique("MONDO:1")])
    _write_jsonl(adir / "PhenotypicFeature.txt", [_clique("HP:5", biolink_type="biolink:PhenotypicFeature")])
    rows, summary = diff_builds(str(bdir), str(adir), ["Disease.txt", "PhenotypicFeature.txt"])
    disease_rows = [r for r in rows if r["compendium"] == "Disease.txt"]
    moved = [r for r in disease_rows if r["destination_kind"] == "moved"]
    assert moved and moved[0]["example_members"] == 'HP:5 "label of HP:5"'
    # A moved member is typed by the after-clique it landed in, in the other compendium.
    assert moved[0]["destination_type"] == "biolink:PhenotypicFeature"
    assert summary["Disease.txt"]["dropped_member_count"] == 0
    assert summary["Disease.txt"]["moved_member_count"] == 1
