"""
Unit tests for tools/clique_diff/diff.py — the build-vs-build compendium clique diff.

Sections:

- ``# --- Loading ---`` covers JSONL parsing and the leader/member extraction.
- ``# --- Diffing ---`` covers the four destination kinds (kept/regrouped/moved/dropped)
  and the "unchanged clique is omitted" rule.
"""

import json

import pytest

from tools.clique_diff.diff import diff_builds, diff_compendium, load_cliques


def _clique(*curies):
    """Build a minimal compendium record whose leader is the first CURIE."""
    return {"type": "biolink:Disease", "identifiers": [{"i": c, "l": c} for c in curies]}


def _write_jsonl(path, cliques):
    path.write_text("".join(json.dumps(c) + "\n" for c in cliques))
    return str(path)


# --- Loading ---


@pytest.mark.unit
def test_load_cliques_extracts_leader_and_members(tmp_path):
    """load_cliques should key cliques by their first identifier and map every member to it."""
    path = _write_jsonl(tmp_path / "Disease.txt", [_clique("MONDO:1", "MEDDRA:9", "UMLS:7")])
    cliques, leader_of = load_cliques(path)
    assert cliques == {"MONDO:1": frozenset({"MONDO:1", "MEDDRA:9", "UMLS:7"})}
    assert leader_of["MEDDRA:9"] == "MONDO:1"


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
    before, _ = load_cliques(_write_jsonl(tmp_path / "b.txt", [_clique("MONDO:1", "MEDDRA:9")]))
    after, after_leader = load_cliques(_write_jsonl(tmp_path / "a.txt", [_clique("MONDO:1", "MEDDRA:9")]))
    records = diff_compendium(before, after, after_leader, set(after_leader))
    assert records == []


@pytest.mark.unit
def test_dropped_member_is_flagged(tmp_path):
    """When a member present before is absent from every after compendium, it is 'dropped'.

    This is the close-match-guard regression signal: the separated CURIE leaves the output.
    """
    before, _ = load_cliques(_write_jsonl(tmp_path / "b.txt", [_clique("MONDO:1", "MEDDRA:9")]))
    after, after_leader = load_cliques(_write_jsonl(tmp_path / "a.txt", [_clique("MONDO:1")]))
    records = diff_compendium(before, after, after_leader, set(after_leader))
    kept = [r for r in records if r["destination_kind"] == "kept"]
    dropped = [r for r in records if r["destination_kind"] == "dropped"]
    assert dropped and dropped[0]["example_members"] == "MEDDRA:9"
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
    _write_jsonl(adir / "PhenotypicFeature.txt", [_clique("HP:5")])
    rows, summary = diff_builds(str(bdir), str(adir), ["Disease.txt", "PhenotypicFeature.txt"])
    disease_rows = [r for r in rows if r["compendium"] == "Disease.txt"]
    moved = [r for r in disease_rows if r["destination_kind"] == "moved"]
    assert moved and moved[0]["example_members"] == "HP:5"
    assert summary["Disease.txt"]["dropped_member_count"] == 0
    assert summary["Disease.txt"]["moved_member_count"] == 1
