"""Unit tests for the shared clique-building helper.

``src.createcompendia.cliques.glom_from_files`` is the skeleton that each compendium's
``compute_cliques_for_impact_report`` (and, ideally, its ``build_compendia``) routes
through. The anatomy CLI test exercises it end-to-end; these tests cover the generic
hooks directly: the concord-pair filter, the overused-xref remover, ``excluded_sources``,
and that ``unique_prefixes`` / ``glom_kwargs`` are forwarded to :func:`glom`.
"""

import pytest

from src.createcompendia import cliques

pytestmark = pytest.mark.unit


def _write(path, lines):
    path.write_text("".join(line + "\n" for line in lines))
    return str(path)


def _clique_of(dicts, curie):
    """Return the frozenset of CURIEs glommed together with ``curie`` (or empty)."""
    return frozenset(dicts.get(curie, set()))


def test_merges_ids_and_concords(tmp_path):
    ids = _write(tmp_path / "SRC", ["FOO:1\tbiolink:Thing", "BAR:1"])
    concord = _write(tmp_path / "SRC.concord", ["FOO:1\teq\tBAR:1"])

    dicts, types = cliques.glom_from_files([concord], [ids], unique_prefixes=[])

    assert _clique_of(dicts, "FOO:1") == frozenset({"FOO:1", "BAR:1"})
    assert types["FOO:1"] == "biolink:Thing"


def test_excluded_sources_skips_ids_and_concords(tmp_path):
    keep_ids = _write(tmp_path / "KEEP", ["FOO:1"])
    drop_ids = _write(tmp_path / "DROP", ["FOO:2"])
    concord = _write(tmp_path / "DROP.concord", ["FOO:1\teq\tFOO:2"])

    # Exclude both the DROP ids file and its concord by basename.
    dicts, _ = cliques.glom_from_files(
        [concord],
        [keep_ids, drop_ids],
        unique_prefixes=[],
        excluded_sources={"DROP", "DROP.concord"},
    )

    assert "FOO:1" in dicts
    assert "FOO:2" not in dicts


def test_concord_pair_filter_can_gate_on_clique_state(tmp_path):
    ids = _write(tmp_path / "SRC", ["FOO:1"])
    # NEW:1 is never declared in an ids file, so a filter that requires both CURIEs to be
    # present should drop this pair, leaving FOO:1 un-merged.
    concord = _write(tmp_path / "SRC.concord", ["FOO:1\teq\tNEW:1"])

    def both_present(parts, infile, dicts):
        return parts[0] in dicts and parts[2] in dicts

    dicts, _ = cliques.glom_from_files([concord], [ids], unique_prefixes=[], concord_pair_filter=both_present)
    assert _clique_of(dicts, "FOO:1") == frozenset({"FOO:1"})

    # Without the filter, the pair merges NEW:1 in.
    dicts2, _ = cliques.glom_from_files([concord], [ids], unique_prefixes=[])
    assert _clique_of(dicts2, "FOO:1") == frozenset({"FOO:1", "NEW:1"})


def test_overused_xref_remover_is_invoked(tmp_path):
    ids = _write(tmp_path / "SRC", ["FOO:1"])
    concord = _write(tmp_path / "SRC.concord", ["FOO:1\teq\tBAR:1"])

    seen = []

    def drop_everything(pairs, infile):
        seen.append((infile, pairs))
        return []

    dicts, _ = cliques.glom_from_files([concord], [ids], unique_prefixes=[], overused_xref_remover=drop_everything)

    assert seen and seen[0][1] == [["FOO:1", "BAR:1"]]
    # The remover dropped the only pair, so nothing merged with FOO:1.
    assert _clique_of(dicts, "FOO:1") == frozenset({"FOO:1"})


def test_unique_prefixes_and_glom_kwargs_forwarded(tmp_path, monkeypatch):
    ids = _write(tmp_path / "SRC", ["FOO:1"])
    concord = _write(tmp_path / "SRC.concord", ["FOO:1\teq\tBAR:1"])

    calls = []

    def fake_glom(conc_set, newgroups, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(cliques, "glom", fake_glom)

    cliques.glom_from_files(
        [concord],
        [ids],
        unique_prefixes=["FOO"],
        glom_kwargs={"pref": "BAR", "close": {"FOO": {}}},
    )

    assert calls, "glom should have been called"
    for kwargs in calls:
        assert kwargs["unique_prefixes"] == ["FOO"]
        assert kwargs["pref"] == "BAR"
        assert kwargs["close"] == {"FOO": {}}
