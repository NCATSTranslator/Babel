"""Tests for the manual compendium (src/createcompendia/manual.py). Offline / unit-only."""

from pathlib import Path

import pytest

from src.babel_utils import TypedClique
from src.createcompendia.manual import (
    DEFAULT_TERMS_FILE,
    ManualTerm,
    build_manual_cliques,
    read_manual_terms,
    write_manual_labels_and_synonyms,
)
from src.predicates import HAS_EXACT_SYNONYM

# repo root, so the shipped-data test is independent of the pytest cwd.
REPO_ROOT = Path(__file__).resolve().parents[2]

# One NDJSON object per line: curie, type, preferred, alternatives.
_TERMS = (
    '{"curie": "EUPATH:0009259", "type": "biolink:ClinicalFinding", '
    '"preferred": "Shannon-indexed alpha diversity data", '
    '"alternatives": ["Shannon alpha diversity", "Shannon diversity index", "Shannon entropy"]}\n'
    '{"curie": "EUPATH:0000099", "type": "biolink:ClinicalFinding", '
    '"preferred": "No alternatives term", "alternatives": []}\n'
)

# A term with equivalents across multiple prefixes to exercise multi-CURIE cliques. Includes a
# duplicate equivalent and the primary self-listed, to verify deduplication.
_EQUIV_TERMS = (
    '{"curie": "EUPATH:0009259", "type": "biolink:ClinicalFinding", '
    '"preferred": "Shannon-indexed alpha diversity data", "alternatives": [], '
    '"equivalents": ["FOO:1", "BAR:2", "FOO:1", "EUPATH:0009259"]}\n'
)

# Two terms that both reference FOO:1 (an equivalent of the first is the second's primary).
# This is a conflict: the two terms must be merged into one line instead.
_CLASH_TERMS = (
    '{"curie": "EUPATH:0009259", "type": "biolink:ClinicalFinding", '
    '"preferred": "First", "alternatives": [], "equivalents": ["FOO:1"]}\n'
    '{"curie": "FOO:1", "type": "biolink:ClinicalFinding", '
    '"preferred": "Second", "alternatives": []}\n'
)


def _write(tmp_path: Path, contents: str, name: str = "terms.ndjson") -> Path:
    terms = tmp_path / name
    terms.write_text(contents)
    return terms


@pytest.mark.unit
def test_read_manual_terms_parses_rows(tmp_path: Path) -> None:
    terms = _write(tmp_path, _TERMS)
    rows = list(read_manual_terms(terms))
    assert rows == [
        ManualTerm(
            curie="EUPATH:0009259",
            biolink_type="biolink:ClinicalFinding",
            preferred="Shannon-indexed alpha diversity data",
            alternatives=["Shannon alpha diversity", "Shannon diversity index", "Shannon entropy"],
            equivalents=[],
        ),
        ManualTerm(
            curie="EUPATH:0000099",
            biolink_type="biolink:ClinicalFinding",
            preferred="No alternatives term",
            alternatives=[],
            equivalents=[],
        ),
    ]


@pytest.mark.unit
def test_read_manual_terms_parses_equivalents(tmp_path: Path) -> None:
    terms = _write(tmp_path, _EQUIV_TERMS)
    rows = list(read_manual_terms(terms))
    assert len(rows) == 1
    assert rows[0].equivalents == ["FOO:1", "BAR:2", "FOO:1", "EUPATH:0009259"]


@pytest.mark.unit
def test_read_manual_terms_real_file() -> None:
    """The shipped data file must parse to exactly one well-formed term."""
    rows = list(read_manual_terms(str(REPO_ROOT / DEFAULT_TERMS_FILE)))
    assert len(rows) == 1
    term = rows[0]
    assert term.curie == "EUPATH:0009259"
    assert term.biolink_type == "biolink:ClinicalFinding"
    assert term.preferred
    assert term.alternatives  # real synonyms are kept
    assert term.equivalents == []  # no equivalents in the current data


@pytest.mark.unit
def test_build_manual_cliques(tmp_path: Path) -> None:
    """Singleton terms (no equivalents) are backward-compatible: one identifier each."""
    terms = _write(tmp_path, _TERMS)
    cliques, extra_prefixes = build_manual_cliques(terms)
    assert cliques == [
        TypedClique(node_type="biolink:ClinicalFinding", identifiers=["EUPATH:0009259"]),
        TypedClique(node_type="biolink:ClinicalFinding", identifiers=["EUPATH:0000099"]),
    ]
    assert extra_prefixes == ["EUPATH"]


@pytest.mark.unit
def test_build_manual_cliques_with_equivalents(tmp_path: Path) -> None:
    """Equivalents join the primary in one clique; the primary stays first and leads extra_prefixes."""
    terms = _write(tmp_path, _EQUIV_TERMS)
    cliques, extra_prefixes = build_manual_cliques(terms)
    assert cliques == [
        TypedClique(
            node_type="biolink:ClinicalFinding",
            identifiers=["EUPATH:0009259", "FOO:1", "BAR:2"],
        ),
    ]
    # Primary prefix first, then each equivalent prefix in first-seen order.
    assert extra_prefixes == ["EUPATH", "FOO", "BAR"]
    assert cliques[0].identifiers[0] == "EUPATH:0009259"


@pytest.mark.unit
def test_build_manual_cliques_dedupes_equivalents(tmp_path: Path) -> None:
    """A duplicate equivalent and the primary self-listed as an equivalent are dropped."""
    terms = _write(tmp_path, _EQUIV_TERMS)
    cliques, _ = build_manual_cliques(terms)
    assert cliques[0].identifiers == ["EUPATH:0009259", "FOO:1", "BAR:2"]


@pytest.mark.unit
def test_build_manual_cliques_rejects_duplicate_identifier(tmp_path: Path) -> None:
    """A CURIE appearing in two terms raises; the user must merge them into one line."""
    terms = _write(tmp_path, _CLASH_TERMS)
    with pytest.raises(ValueError, match="FOO:1"):
        build_manual_cliques(terms)


@pytest.mark.unit
def test_write_manual_labels_and_synonyms(tmp_path: Path) -> None:
    terms = _write(tmp_path, _TERMS)
    download_dir = tmp_path / "downloads"
    write_manual_labels_and_synonyms(terms, download_dir, ["EUPATH"])

    labels = (download_dir / "EUPATH" / "labels").read_text().splitlines()
    assert labels == [
        "EUPATH:0000099\tNo alternatives term",
        "EUPATH:0009259\tShannon-indexed alpha diversity data",
    ]

    synonyms = (download_dir / "EUPATH" / "synonyms").read_text().splitlines()
    # Every name (preferred + alternatives) is an hasExactSynonym, matching src/datahandlers/umls.py.
    assert f"EUPATH:0009259\t{HAS_EXACT_SYNONYM}\tShannon-indexed alpha diversity data" in synonyms
    assert f"EUPATH:0009259\t{HAS_EXACT_SYNONYM}\tShannon alpha diversity" in synonyms
    assert f"EUPATH:0009259\t{HAS_EXACT_SYNONYM}\tShannon diversity index" in synonyms
    assert f"EUPATH:0009259\t{HAS_EXACT_SYNONYM}\tShannon entropy" in synonyms
    assert f"EUPATH:0000099\t{HAS_EXACT_SYNONYM}\tNo alternatives term" in synonyms


@pytest.mark.unit
def test_write_ignores_equivalents(tmp_path: Path) -> None:
    """Equivalents get no labels/synonyms of their own; only the primary prefix is materialized."""
    terms = _write(tmp_path, _EQUIV_TERMS)
    download_dir = tmp_path / "downloads"
    write_manual_labels_and_synonyms(terms, download_dir, ["EUPATH"])

    labels = (download_dir / "EUPATH" / "labels").read_text().splitlines()
    assert labels == ["EUPATH:0009259\tShannon-indexed alpha diversity data"]
    assert not (download_dir / "FOO").exists()
    assert not (download_dir / "BAR").exists()
