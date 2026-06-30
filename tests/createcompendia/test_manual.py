"""Tests for the manual compendium (src/createcompendia/manual.py). Offline / unit-only."""

from pathlib import Path

import pytest

from src.babel_utils import TypedClique
from src.createcompendia.manual import (
    ManualTerm,
    build_manual_cliques,
    read_manual_terms,
    write_manual_labels_and_synonyms,
)
from src.predicates import HAS_EXACT_SYNONYM

# One NDJSON object per line: curie, type, preferred, alternatives.
_TERMS = (
    '{"curie": "EUPATH:0009259", "type": "biolink:ClinicalFinding", '
    '"preferred": "Shannon-indexed alpha diversity data", '
    '"alternatives": ["Shannon alpha diversity", "Shannon diversity index", "Shannon entropy"]}\n'
    '{"curie": "EUPATH:0000099", "type": "biolink:ClinicalFinding", '
    '"preferred": "No alternatives term", "alternatives": []}\n'
)


def _write_terms(tmp_path: Path) -> Path:
    terms = tmp_path / "terms.ndjson"
    terms.write_text(_TERMS)
    return terms


@pytest.mark.unit
def test_read_manual_terms_parses_rows(tmp_path: Path) -> None:
    terms = _write_terms(tmp_path)
    rows = list(read_manual_terms(terms))
    assert rows == [
        ManualTerm(
            curie="EUPATH:0009259",
            biolink_type="biolink:ClinicalFinding",
            preferred="Shannon-indexed alpha diversity data",
            alternatives=["Shannon alpha diversity", "Shannon diversity index", "Shannon entropy"],
        ),
        ManualTerm(
            curie="EUPATH:0000099",
            biolink_type="biolink:ClinicalFinding",
            preferred="No alternatives term",
            alternatives=[],
        ),
    ]


@pytest.mark.unit
def test_build_manual_cliques(tmp_path: Path) -> None:
    terms = _write_terms(tmp_path)
    cliques, extra_prefixes = build_manual_cliques(terms)
    assert cliques == [
        TypedClique(node_type="biolink:ClinicalFinding", identifiers=["EUPATH:0009259"]),
        TypedClique(node_type="biolink:ClinicalFinding", identifiers=["EUPATH:0000099"]),
    ]
    assert extra_prefixes == ["EUPATH"]


@pytest.mark.unit
def test_write_manual_labels_and_synonyms(tmp_path: Path) -> None:
    terms = _write_terms(tmp_path)
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
