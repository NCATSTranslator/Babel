"""Tests for src/snakefiles/util.py (offline / unit-only). Covers the unstable gating."""

import pytest

from src.snakefiles.util import (
    get_all_compendia,
    get_all_synonyms,
    unstable_enabled,
)


def _full_config(unstable: object) -> dict[str, object]:
    """A config with every key the aggregators read; only manual_outputs carries a filename."""
    keys = [
        "anatomy_outputs",
        "chemical_outputs",
        "disease_outputs",
        "gene_outputs",
        "genefamily_outputs",
        "process_outputs",
        "protein_outputs",
        "taxon_outputs",
        "cell_line_outputs",
        "umls_outputs",
        "macromolecularcomplex_outputs",
        "publication_outputs",
        "drugchemicalconflated_synonym_outputs",
        "geneproteinconflated_synonym_outputs",
    ]
    cfg: dict[str, object] = {key: [] for key in keys}
    cfg["manual_outputs"] = ["Manual.txt"]
    cfg["unstable"] = unstable
    return cfg


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("  true  ", True),
        (False, False),
        ("false", False),
        ("False", False),
        ("no", False),
        (None, False),
        (1, False),  # only an actual bool True or the string "true" opts in
    ],
)
def test_unstable_enabled(value: object, expected: bool) -> None:
    assert unstable_enabled({"unstable": value}) is expected


@pytest.mark.unit
def test_unstable_enabled_defaults_false_when_absent() -> None:
    assert unstable_enabled({}) is False


@pytest.mark.unit
def test_get_all_compendia_excludes_manual_when_stable() -> None:
    cfg = _full_config(False)
    assert get_all_compendia(cfg) == []
    assert "Manual.txt" not in get_all_synonyms(cfg)


@pytest.mark.unit
def test_get_all_compendia_includes_manual_when_unstable() -> None:
    cfg = _full_config(True)
    assert get_all_compendia(cfg) == ["Manual.txt"]
    assert "Manual.txt" in get_all_synonyms(cfg)
