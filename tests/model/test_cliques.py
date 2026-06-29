"""Unit tests for the shared clique-building helper.

``src.model.cliques.glom_from_files`` is the skeleton that each compendium's
``compute_cliques_for_impact_report`` (and, ideally, its ``build_compendia``) routes
through. The anatomy CLI test exercises it end-to-end; these tests cover the generic
hooks directly: the concord-pair filter, the overused-xref remover, ``excluded_sources``,
and that ``unique_prefixes`` / ``glom_kwargs`` are forwarded to :func:`glom`.

Test groups
-----------
- Basic merging: ids and concord files produce the expected clique.
- Excluded sources: ``excluded_sources`` gates both ids and concord files by basename.
- Concord pair filter: ``concord_pair_filter`` can inspect clique state to reject a pair.
- Overused-xref remover: ``overused_xref_remover`` is invoked with the right arguments.
- Hook forwarding: ``unique_prefixes`` and ``glom_kwargs`` reach :func:`glom` unchanged.
"""

import pytest

from src.model import cliques

pytestmark = pytest.mark.unit


def write_lines(path, lines):
    """Write *lines* (one per line) to *path* and return the path as a string."""
    path.write_text("".join(line + "\n" for line in lines))
    return str(path)


def _clique_of(dicts, curie):
    """Return the frozenset of CURIEs glommed together with *curie*, or an empty frozenset."""
    return frozenset(dicts.get(curie, set()))


def test_merges_ids_and_concords(tmp_path):
    """A concord pair merges two ids-file entries into a single clique; the Biolink type is preserved."""
    ids = write_lines(tmp_path / "SRC", ["FOO:1\tbiolink:Thing", "BAR:1"])
    concord = write_lines(tmp_path / "SRC.concord", ["FOO:1\teq\tBAR:1"])

    dicts, types = cliques.glom_from_files([concord], [ids], unique_prefixes=[])

    assert _clique_of(dicts, "FOO:1") == frozenset({"FOO:1", "BAR:1"})
    assert types["FOO:1"] == "biolink:Thing"


def test_excluded_sources_skips_ids_and_concords(tmp_path):
    """Files whose basename appears in ``excluded_sources`` are skipped for both ids and concords."""
    keep_ids = write_lines(tmp_path / "KEEP", ["FOO:1"])
    drop_ids = write_lines(tmp_path / "DROP", ["FOO:2"])
    concord = write_lines(tmp_path / "DROP.concord", ["FOO:1\teq\tFOO:2"])

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
    """``concord_pair_filter`` receives the live clique dict and can reject pairs based on it.

    A filter that requires both CURIEs to already be present drops any pair where one side
    was never declared in an ids file, leaving the known CURIE un-merged. Without the filter,
    the unknown CURIE is pulled in.
    """
    ids = write_lines(tmp_path / "SRC", ["FOO:1"])
    # NEW:1 is never declared in an ids file, so a filter that requires both CURIEs to be
    # present should drop this pair, leaving FOO:1 un-merged.
    concord = write_lines(tmp_path / "SRC.concord", ["FOO:1\teq\tNEW:1"])

    def both_present(parts, infile, dicts):
        return parts[0] in dicts and parts[2] in dicts

    dicts, _ = cliques.glom_from_files([concord], [ids], unique_prefixes=[], concord_pair_filter=both_present)
    assert _clique_of(dicts, "FOO:1") == frozenset({"FOO:1"})

    # Without the filter, the pair merges NEW:1 in.
    dicts2, _ = cliques.glom_from_files([concord], [ids], unique_prefixes=[])
    assert _clique_of(dicts2, "FOO:1") == frozenset({"FOO:1", "NEW:1"})


def test_overused_xref_remover_is_invoked(tmp_path):
    """``overused_xref_remover`` is called with the per-file pair list; pairs it drops are not glommed."""
    ids = write_lines(tmp_path / "SRC", ["FOO:1"])
    concord = write_lines(tmp_path / "SRC.concord", ["FOO:1\teq\tBAR:1"])

    seen = []

    def drop_everything(pairs, infile):
        seen.append((infile, pairs))
        return []

    dicts, _ = cliques.glom_from_files([concord], [ids], unique_prefixes=[], overused_xref_remover=drop_everything)

    assert seen and seen[0][1] == [["FOO:1", "BAR:1"]]
    # The remover dropped the only pair, so nothing merged with FOO:1.
    assert _clique_of(dicts, "FOO:1") == frozenset({"FOO:1"})


def test_unique_prefixes_and_glom_kwargs_forwarded(tmp_path, monkeypatch):
    """``unique_prefixes`` and all extra ``glom_kwargs`` are forwarded verbatim to :func:`glom`."""
    ids = write_lines(tmp_path / "SRC", ["FOO:1"])
    concord = write_lines(tmp_path / "SRC.concord", ["FOO:1\teq\tBAR:1"])

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
