"""Unit tests for src/synonyms/filter.py."""

import logging

import pytest
import yaml

import src.synonyms.filter as lf_module
from src.synonyms.filter import SynonymFilter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_filter(tmp_path, entries):
    """Write a minimal obsolete_synonyms.yaml and return a SynonymFilter for it."""
    data = {"obsolete_synonyms": entries}
    yaml_file = tmp_path / "obsolete_synonyms.yaml"
    yaml_file.write_text(yaml.dump(data))
    return SynonymFilter(yaml_file)


# ---------------------------------------------------------------------------
# Basic matching
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_exact_match_whole_label(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.should_suppress("mongolism", source="UMLS labels file") is True


@pytest.mark.unit
def test_exact_match_case_insensitive(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.should_suppress("Mongolism", source="UMLS labels file") is True
    assert fltr.should_suppress("MONGOLISM", source="UMLS labels file") is True


@pytest.mark.unit
def test_exact_match_no_partial_by_default(tmp_path):
    """A whole-label entry must not match a label that merely contains the term."""
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.should_suppress("pseudo-mongolism syndrome", source="UMLS labels file") is False


@pytest.mark.unit
def test_partial_match(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mental retardation", "reason": "outdated", "partial": True}])
    assert fltr.should_suppress("mild mental retardation (finding)", source="UMLS labels file") is True


@pytest.mark.unit
def test_partial_match_disabled(tmp_path):
    """partial=False (default) does not match substring."""
    fltr = make_filter(tmp_path, [{"label": "mental retardation", "reason": "outdated", "partial": False}])
    assert fltr.should_suppress("mild mental retardation", source="UMLS labels file") is False


@pytest.mark.unit
def test_regex_match(tmp_path):
    fltr = make_filter(tmp_path, [{"pattern": r"manic.depress", "reason": "outdated"}])
    assert fltr.should_suppress("manic-depressive disorder", source="UMLS labels file") is True
    assert fltr.should_suppress("manic depressive", source="UMLS labels file") is True


@pytest.mark.unit
def test_regex_no_match(tmp_path):
    fltr = make_filter(tmp_path, [{"pattern": r"manic.depress", "reason": "outdated"}])
    assert fltr.should_suppress("bipolar disorder", source="UMLS labels file") is False


@pytest.mark.unit
def test_empty_label_always_false(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.should_suppress("", source="UMLS labels file") is False


@pytest.mark.unit
def test_nonmatching_label(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.should_suppress("Down syndrome", source="UMLS labels file") is False


# ---------------------------------------------------------------------------
# Type-scoped entries
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_type_scoped_matches_when_type_present(tmp_path):
    entries = [{"label": "mongolism", "reason": "offensive", "only_for_types": ["biolink:Disease"]}]
    fltr = make_filter(tmp_path, entries)
    assert (
        fltr.should_suppress("mongolism", source="UMLS", node_types=["biolink:Disease", "biolink:NamedThing"]) is True
    )


@pytest.mark.unit
def test_type_scoped_skipped_when_type_absent(tmp_path):
    entries = [{"label": "mongolism", "reason": "offensive", "only_for_types": ["biolink:Disease"]}]
    fltr = make_filter(tmp_path, entries)
    assert fltr.should_suppress("mongolism", source="UMLS", node_types=["biolink:ChemicalEntity"]) is False


@pytest.mark.unit
def test_type_scoped_skipped_when_node_types_is_none(tmp_path):
    """node_types=None means we don't know the type; type-scoped entries are skipped."""
    entries = [{"label": "mongolism", "reason": "offensive", "only_for_types": ["biolink:Disease"]}]
    fltr = make_filter(tmp_path, entries)
    # Scoped entry is skipped when node_types=None
    assert fltr.should_suppress("mongolism", source="UMLS", node_types=None) is False


@pytest.mark.unit
def test_unscoped_entry_matches_any_type(tmp_path):
    """An entry without only_for_types should match regardless of node type."""
    entries = [{"label": "mongolism", "reason": "offensive"}]
    fltr = make_filter(tmp_path, entries)
    assert fltr.should_suppress("mongolism", source="UMLS", node_types=["biolink:ChemicalEntity"]) is True


# ---------------------------------------------------------------------------
# Counter tracking
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filtered_count_increments(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.filtered_count == 0
    fltr.should_suppress("mongolism", source="UMLS")
    assert fltr.filtered_count == 1
    fltr.should_suppress("mongolism", source="MESH")
    assert fltr.filtered_count == 2


@pytest.mark.unit
def test_filtered_count_does_not_increment_on_miss(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    fltr.should_suppress("Down syndrome", source="UMLS")
    assert fltr.filtered_count == 0


@pytest.mark.unit
def test_filtered_by_source_tracks_per_source(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    fltr.should_suppress("mongolism", source="UMLS labels file")
    fltr.should_suppress("mongolism", source="UMLS labels file")
    fltr.should_suppress("mongolism", source="MESH labels file")
    assert fltr.filtered_by_source["UMLS labels file"] == 2
    assert fltr.filtered_by_source["MESH labels file"] == 1


# ---------------------------------------------------------------------------
# Per-entry action field
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_entry_action_remove_returns_true(tmp_path):
    """action='remove' (default) causes should_suppress to return True."""
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive", "action": "remove"}])
    assert fltr.should_suppress("mongolism", source="UMLS") is True


@pytest.mark.unit
def test_entry_action_default_is_remove(tmp_path):
    """Omitting action is equivalent to action='remove'."""
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.should_suppress("mongolism", source="UMLS") is True


@pytest.mark.unit
def test_entry_action_warn_returns_false(tmp_path):
    """action='warn' logs a warning but returns False so the caller keeps the term."""
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive", "action": "warn"}])
    assert fltr.should_suppress("mongolism", source="UMLS") is False


@pytest.mark.unit
def test_entry_action_warn_still_increments_count(tmp_path):
    """filtered_count increments even for warn-only entries."""
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive", "action": "warn"}])
    assert fltr.filtered_count == 0
    fltr.should_suppress("mongolism", source="UMLS")
    assert fltr.filtered_count == 1


@pytest.mark.unit
def test_entry_invalid_action_defaults_to_remove(tmp_path, caplog):
    """An unrecognised action is logged as a warning and treated as 'remove'."""
    entries = [{"label": "mongolism", "reason": "offensive", "action": "delete"}]
    with caplog.at_level(logging.WARNING, logger="src.synonyms.filter"):
        fltr = make_filter(tmp_path, entries)
    assert any("invalid action" in r.message for r in caplog.records)
    assert fltr.should_suppress("mongolism", source="UMLS") is True


# ---------------------------------------------------------------------------
# Missing / empty filter file
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_missing_filter_file_loads_zero_entries(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    fltr = SynonymFilter(missing)
    assert len(fltr._entries) == 0


@pytest.mark.unit
def test_missing_filter_file_emits_warning(tmp_path, caplog):
    missing = tmp_path / "does_not_exist.yaml"
    with caplog.at_level(logging.WARNING, logger="src.synonyms.filter"):
        SynonymFilter(missing)
    assert any("not found" in r.message for r in caplog.records)


@pytest.mark.unit
def test_empty_yaml_loads_zero_entries(tmp_path):
    yaml_file = tmp_path / "obsolete_synonyms.yaml"
    yaml_file.write_text("obsolete_synonyms: []")
    fltr = SynonymFilter(yaml_file)
    assert len(fltr._entries) == 0
    assert fltr.should_suppress("mongolism", source="UMLS") is False


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def reset_singleton():
    """Ensure the module-level singleton is reset before and after each test that uses it."""
    original = lf_module._instance
    lf_module._instance = None
    yield
    lf_module._instance = original


@pytest.mark.unit
def test_singleton_returns_same_instance(tmp_path, reset_singleton):
    """get_synonym_filter() must return the same object on every call."""
    yaml_file = tmp_path / "obsolete_synonyms.yaml"
    yaml_file.write_text("obsolete_synonyms: []")

    # Pre-populate the singleton directly to avoid needing get_config() / a real config.yaml.
    lf_module._instance = SynonymFilter(yaml_file)

    first = lf_module.get_synonym_filter()
    second = lf_module.get_synonym_filter()
    assert first is second
    assert first is lf_module._instance
