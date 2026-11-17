"""Tests for unique_prefixes_from_config(), which reads a pipeline's unique prefixes from config.yaml.

glom()'s own checks on unique_prefixes are in tests/test_glom.py; these cover only what the config
reader adds: an empty list and prefixes src/prefixes.py doesn't define are rejected.
"""

import pytest

import src.babel_utils as babel_utils
from src.babel_utils import unique_prefixes_from_config
from src.util import get_config

pytestmark = pytest.mark.unit


def use_config(monkeypatch, value):
    """Make get_config() return a config whose only entry is ``test_unique_prefixes: value``."""
    monkeypatch.setattr(babel_utils, "get_config", lambda: {"test_unique_prefixes": value})


# THE REAL CONFIG


# Every pipeline whose glom() can merge anything (#882). cell_line, genefamily and
# macromolecular_complex load ids files alone, so they pass () in code and have no entry.
PIPELINE_KEYS = {
    "anatomy_unique_prefixes",
    "chemical_unique_prefixes",
    "disease_unique_prefixes",
    "drugchemical_unique_prefixes",
    "gene_unique_prefixes",
    "geneprotein_unique_prefixes",
    "process_unique_prefixes",
    "protein_unique_prefixes",
    "taxon_unique_prefixes",
}
# The only entries whose recorded decision is to restrict nothing, read with allow_empty=True.
EMPTY_KEYS = {"geneprotein_unique_prefixes"}


def test_config_yaml_has_an_entry_for_every_pipeline_that_merges():
    """Should find exactly one ``*_unique_prefixes`` entry per glomming pipeline in the real config.yaml."""
    keys = {key for key in get_config() if key.endswith("_unique_prefixes")}
    assert keys == PIPELINE_KEYS


@pytest.mark.parametrize("key", sorted(PIPELINE_KEYS))
def test_every_unique_prefixes_entry_in_config_yaml_is_valid(key):
    """Should read every real entry: non-empty except the EMPTY_KEYS, which must be empty."""
    if key in EMPTY_KEYS:
        assert unique_prefixes_from_config(key, allow_empty=True) == frozenset()
    else:
        assert unique_prefixes_from_config(key)


# ACCEPTED


def test_returns_a_frozenset_of_known_prefixes(monkeypatch):
    """Should return the listed prefixes as a frozenset when each is defined in src/prefixes.py."""
    use_config(monkeypatch, ["UBERON", "GO"])
    assert unique_prefixes_from_config("test_unique_prefixes") == frozenset({"UBERON", "GO"})


# REJECTED


@pytest.mark.parametrize(
    "value, message",
    [
        pytest.param("UBERON", r"did you mean \['UBERON'\]", id="string-without-brackets"),
        pytest.param(None, "not NoneType", id="key-with-no-value"),
        pytest.param([], "is empty", id="empty-list"),
        pytest.param(["UBERON", "UBRON"], r"not defined in src/prefixes.py: \['UBRON'\]", id="misspelt-prefix"),
        pytest.param(["uberon"], "not defined in src/prefixes.py", id="wrong-case"),
    ],
)
def test_a_bad_entry_raises_naming_the_key(monkeypatch, value, message):
    """Should raise ValueError naming the config key, for a malformed, empty or unknown-prefix entry."""
    use_config(monkeypatch, value)
    with pytest.raises(ValueError, match=message) as excinfo:
        unique_prefixes_from_config("test_unique_prefixes")
    assert "config.yaml: test_unique_prefixes" in str(excinfo.value)


def test_a_missing_key_raises(monkeypatch):
    """Should raise ValueError, not KeyError or TypeError, when config.yaml has no such key."""
    use_config(monkeypatch, None)
    with pytest.raises(ValueError, match="config.yaml: no_such_unique_prefixes"):
        unique_prefixes_from_config("no_such_unique_prefixes")


# ALLOW_EMPTY


def test_allow_empty_accepts_an_empty_list(monkeypatch):
    """Should return an empty frozenset for ``[]`` when allow_empty is set, as geneprotein's entry is."""
    use_config(monkeypatch, [])
    assert unique_prefixes_from_config("test_unique_prefixes", allow_empty=True) == frozenset()


@pytest.mark.parametrize(
    "value, message",
    [
        pytest.param("UBERON", r"did you mean \['UBERON'\]", id="string-without-brackets"),
        pytest.param(None, "not NoneType", id="key-with-no-value"),
        pytest.param(["UBRON"], r"not defined in src/prefixes.py: \['UBRON'\]", id="misspelt-prefix"),
    ],
)
def test_allow_empty_still_rejects_every_other_bad_entry(monkeypatch, value, message):
    """Should still raise for a bare string, a key with no value, or an unknown prefix when allow_empty is set."""
    use_config(monkeypatch, value)
    with pytest.raises(ValueError, match=message):
        unique_prefixes_from_config("test_unique_prefixes", allow_empty=True)
