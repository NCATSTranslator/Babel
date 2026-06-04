"""Unit tests for src/label_filter.py."""

import pytest
import yaml

import src.label_filter as lf_module
from src.label_filter import LabelFilter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_filter(tmp_path, entries, action="remove"):
    """Write a minimal obsolete_labels.yaml and return a LabelFilter for it."""
    data = {"obsolete_labels": entries}
    yaml_file = tmp_path / "obsolete_labels.yaml"
    yaml_file.write_text(yaml.dump(data))
    return LabelFilter(yaml_file, action)


# ---------------------------------------------------------------------------
# Basic matching
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_exact_match_whole_label(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.check_label("mongolism", source="UMLS labels file") is True


@pytest.mark.unit
def test_exact_match_case_insensitive(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.check_label("Mongolism", source="UMLS labels file") is True
    assert fltr.check_label("MONGOLISM", source="UMLS labels file") is True


@pytest.mark.unit
def test_exact_match_no_partial_by_default(tmp_path):
    """A whole-label entry must not match a label that merely contains the term."""
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.check_label("pseudo-mongolism syndrome", source="UMLS labels file") is False


@pytest.mark.unit
def test_partial_match(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mental retardation", "reason": "outdated", "partial": True}])
    assert fltr.check_label("mild mental retardation (finding)", source="UMLS labels file") is True


@pytest.mark.unit
def test_partial_match_disabled(tmp_path):
    """partial=False (default) does not match substring."""
    fltr = make_filter(tmp_path, [{"label": "mental retardation", "reason": "outdated", "partial": False}])
    assert fltr.check_label("mild mental retardation", source="UMLS labels file") is False


@pytest.mark.unit
def test_regex_match(tmp_path):
    fltr = make_filter(tmp_path, [{"pattern": r"manic.depress", "reason": "outdated"}])
    assert fltr.check_label("manic-depressive disorder", source="UMLS labels file") is True
    assert fltr.check_label("manic depressive", source="UMLS labels file") is True


@pytest.mark.unit
def test_regex_no_match(tmp_path):
    fltr = make_filter(tmp_path, [{"pattern": r"manic.depress", "reason": "outdated"}])
    assert fltr.check_label("bipolar disorder", source="UMLS labels file") is False


@pytest.mark.unit
def test_empty_label_always_false(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.check_label("", source="UMLS labels file") is False


@pytest.mark.unit
def test_nonmatching_label(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.check_label("Down syndrome", source="UMLS labels file") is False


# ---------------------------------------------------------------------------
# Type-scoped entries
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_type_scoped_matches_when_type_present(tmp_path):
    entries = [{"label": "mongolism", "reason": "offensive", "only_for_types": ["biolink:Disease"]}]
    fltr = make_filter(tmp_path, entries)
    assert fltr.check_label("mongolism", source="UMLS", node_types=["biolink:Disease", "biolink:NamedThing"]) is True


@pytest.mark.unit
def test_type_scoped_skipped_when_type_absent(tmp_path):
    entries = [{"label": "mongolism", "reason": "offensive", "only_for_types": ["biolink:Disease"]}]
    fltr = make_filter(tmp_path, entries)
    assert fltr.check_label("mongolism", source="UMLS", node_types=["biolink:ChemicalEntity"]) is False


@pytest.mark.unit
def test_type_scoped_skipped_when_node_types_is_none(tmp_path):
    """node_types=None means we don't know the type; type-scoped entries are skipped."""
    entries = [{"label": "mongolism", "reason": "offensive", "only_for_types": ["biolink:Disease"]}]
    fltr = make_filter(tmp_path, entries)
    # Scoped entry is skipped when node_types=None
    assert fltr.check_label("mongolism", source="UMLS", node_types=None) is False


@pytest.mark.unit
def test_unscoped_entry_matches_any_type(tmp_path):
    """An entry without only_for_types should match regardless of node type."""
    entries = [{"label": "mongolism", "reason": "offensive"}]
    fltr = make_filter(tmp_path, entries)
    assert fltr.check_label("mongolism", source="UMLS", node_types=["biolink:ChemicalEntity"]) is True


# ---------------------------------------------------------------------------
# Counter tracking
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filtered_count_increments(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    assert fltr.filtered_count == 0
    fltr.check_label("mongolism", source="UMLS")
    assert fltr.filtered_count == 1
    fltr.check_label("mongolism", source="MESH")
    assert fltr.filtered_count == 2


@pytest.mark.unit
def test_filtered_count_does_not_increment_on_miss(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    fltr.check_label("Down syndrome", source="UMLS")
    assert fltr.filtered_count == 0


@pytest.mark.unit
def test_filtered_by_source_tracks_per_source(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}])
    fltr.check_label("mongolism", source="UMLS labels file")
    fltr.check_label("mongolism", source="UMLS labels file")
    fltr.check_label("mongolism", source="MESH labels file")
    assert fltr.filtered_by_source["UMLS labels file"] == 2
    assert fltr.filtered_by_source["MESH labels file"] == 1


# ---------------------------------------------------------------------------
# action="warn" vs action="remove"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_action_warn_still_returns_true(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}], action="warn")
    assert fltr.action == "warn"
    assert fltr.check_label("mongolism", source="UMLS") is True


@pytest.mark.unit
def test_action_remove_returns_true(tmp_path):
    fltr = make_filter(tmp_path, [{"label": "mongolism", "reason": "offensive"}], action="remove")
    assert fltr.action == "remove"
    assert fltr.check_label("mongolism", source="UMLS") is True


@pytest.mark.unit
def test_invalid_action_raises(tmp_path):
    yaml_file = tmp_path / "obsolete_labels.yaml"
    yaml_file.write_text("obsolete_labels: []")
    with pytest.raises(ValueError, match="action must be 'remove' or 'warn'"):
        LabelFilter(yaml_file, action="delete")


# ---------------------------------------------------------------------------
# Missing / empty filter file
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_missing_filter_file_loads_zero_entries(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    fltr = LabelFilter(missing, action="remove")
    assert len(fltr._entries) == 0


@pytest.mark.unit
def test_missing_filter_file_emits_warning(tmp_path, caplog):
    import logging

    missing = tmp_path / "does_not_exist.yaml"
    with caplog.at_level(logging.WARNING, logger="src.label_filter"):
        LabelFilter(missing, action="remove")
    assert any("not found" in r.message for r in caplog.records)


@pytest.mark.unit
def test_empty_yaml_loads_zero_entries(tmp_path):
    yaml_file = tmp_path / "obsolete_labels.yaml"
    yaml_file.write_text("obsolete_labels: []")
    fltr = LabelFilter(yaml_file)
    assert len(fltr._entries) == 0
    assert fltr.check_label("mongolism", source="UMLS") is False


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
def test_singleton_returns_same_instance(tmp_path, reset_singleton, monkeypatch):
    """get_label_filter() must return the same object on every call."""
    yaml_file = tmp_path / "obsolete_labels.yaml"
    yaml_file.write_text("obsolete_labels: []")

    # Patch get_config so we don't need a real config.yaml
    monkeypatch.setattr(
        "src.label_filter.LabelFilter",
        lambda path, action: LabelFilter(yaml_file, "remove"),
        raising=False,
    )

    first = lf_module.get_label_filter()
    second = lf_module.get_label_filter()
    assert first is second
