"""Unit tests for the shared clique-building helper.

``src.model.cliques.glom_from_files`` is the skeleton that each compendium's
``compute_cliques_for_impact_report`` (and, ideally, its ``build_compendia``) routes
through. The anatomy CLI test exercises it end-to-end; these tests cover the generic
hooks directly: the concord-pair filter, the overused-xref remover, ``excluded_sources``,
and that ``unique_prefixes`` / ``glom_kwargs`` are forwarded to :func:`glom`.
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


# --- Basic merging ---


def test_merges_ids_and_concords(tmp_path):
    """A concord pair should merge two ids-file entries into one clique and preserve the Biolink type."""
    ids = write_lines(tmp_path / "SRC", ["FOO:1\tbiolink:Thing", "BAR:1"])
    concord = write_lines(tmp_path / "SRC.concord", ["FOO:1\teq\tBAR:1"])

    dicts, types = cliques.glom_from_files([concord], [ids], unique_prefixes=[])

    assert _clique_of(dicts, "FOO:1") == frozenset({"FOO:1", "BAR:1"})
    assert types["FOO:1"] == "biolink:Thing"


# --- Excluded sources ---


def test_excluded_sources_skips_ids_and_concords(tmp_path):
    """Files whose basename is in ``excluded_sources`` should be ignored for both ids and concords.

    FOO:2 comes only from the excluded DROP file; after exclusion it must not appear in the
    clique dict at all, and the concord that would have linked it to FOO:1 must also be dropped.
    """
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


# --- Concord pair filter ---


def test_concord_pair_filter_can_gate_on_clique_state(tmp_path):
    """``concord_pair_filter`` should receive the live clique dict and can reject pairs based on it.

    With a filter that requires both CURIEs to already be present: the pair FOO:1↔NEW:1 is
    dropped because NEW:1 was never declared in an ids file, so FOO:1's clique stays a
    singleton. Without the filter the same pair pulls NEW:1 in.
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


# --- Overused-xref remover ---


def test_overused_xref_remover_is_invoked(tmp_path):
    """``overused_xref_remover`` should be called with the per-file pair list; dropped pairs must not be glommed.

    A remover that returns an empty list is used as a spy: it records the pairs it received and
    drops them all. The test asserts the spy saw the expected pair and that FOO:1's clique
    remains a singleton because the only concord pair was removed.
    """
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


# --- Hook forwarding ---


def test_unique_prefixes_and_glom_kwargs_forwarded(tmp_path, monkeypatch):
    """``unique_prefixes`` and all extra ``glom_kwargs`` should be forwarded verbatim to :func:`glom`.

    A monkeypatched ``glom`` records every kwargs dict it receives. Each call must contain
    ``unique_prefixes``, ``pref``, and ``close`` exactly as passed to ``glom_from_files``.
    """
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
