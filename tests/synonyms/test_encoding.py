"""Unit tests for src/synonyms/encoding.py."""

import json

import pytest

import src.synonyms.encoding as encoding_module
from src.synonyms.encoding import check_encoding, find_encoding_issue, scan_file


@pytest.fixture(autouse=True)
def _clear_allowlist():
    """The allowlist is a module-level cache; reset it so tests don't leak into each other."""
    encoding_module._allowlist = None
    yield
    encoding_module._allowlist = None


# ---------------------------------------------------------------------------
# find_encoding_issue: damaged text
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_mojibake_is_detected_and_repair_suggested():
    """The classic case: UTF-8 'é' read as cp1252 becomes 'Ã©'."""
    reason = find_encoding_issue("Ã©tude")
    assert reason is not None
    assert "étude" in reason


@pytest.mark.unit
def test_mojibake_via_cp1252_suggests_the_original():
    """windows-1252 is what src/datahandlers/unii.py reads with."""
    damaged = "N,N–dimethyl".encode().decode("cp1252")
    assert damaged != "N,N–dimethyl"  # sanity: the misread really did damage it
    reason = find_encoding_issue(damaged)
    assert reason is not None
    assert "N,N–dimethyl" in reason
    assert "cp1252" in reason


@pytest.mark.unit
def test_mojibake_via_latin1_suggests_the_original():
    """latin-1 is what src/datahandlers/datacollect.py reads PubChem with.

    It damages text differently from cp1252 -- bytes 0x80-0x9f become C1 control characters rather
    than printable punctuation -- so it needs its own round-trip to be repairable rather than just
    detectable.
    """
    damaged = "N,N–dimethyl".encode().decode("latin-1")
    reason = find_encoding_issue(damaged)
    assert reason is not None
    assert "N,N–dimethyl" in reason
    assert "latin-1" in reason


@pytest.mark.unit
def test_replacement_character_is_detected():
    assert find_encoding_issue("acetyl�choline") is not None


@pytest.mark.unit
def test_byte_order_mark_is_detected():
    assert find_encoding_issue("﻿water") is not None


@pytest.mark.unit
def test_control_character_is_detected():
    assert find_encoding_issue("water\x01") is not None


# ---------------------------------------------------------------------------
# find_encoding_issue: text that must NOT be flagged
#
# False positives are the expensive failure here: check_encoding() raises, so anything wrongly
# flagged halts the pipeline.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_plain_ascii_is_clean():
    assert find_encoding_issue("water") is None


@pytest.mark.unit
def test_legitimate_greek_letter_is_clean():
    """'α' has no cp1252 byte, so it cannot round-trip and is never mistaken for mojibake."""
    assert find_encoding_issue("Nα-acetyl-L-lysine") is None


@pytest.mark.unit
def test_legitimate_accented_text_is_clean():
    assert find_encoding_issue("Ménière disease") is None
    assert find_encoding_issue("Sjögren syndrome") is None


@pytest.mark.unit
def test_embedded_tab_is_clean():
    """A label may legitimately contain a tab, so it must not be treated as a control character.

    `NodeFactory.load_extra_labels()` in src/node.py splits with maxsplit=1 specifically to preserve
    such labels; `tests/node/test_node_factory.py::test_load_extra_labels_tab_in_label` pins that.
    Flagging tab here would abort the build on data the pipeline deliberately supports.
    """
    assert find_encoding_issue("Water\tbottle") is None
    assert find_encoding_issue("beta\tsubunit\n") is None


@pytest.mark.unit
def test_empty_string_is_clean():
    assert find_encoding_issue("") is None


# ---------------------------------------------------------------------------
# check_encoding: the raising wrapper
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_check_encoding_raises_with_an_actionable_message():
    with pytest.raises(RuntimeError) as excinfo:
        check_encoding("Ã©tude", curie="PUBCHEM.COMPOUND:123", source="PUBCHEM.COMPOUND labels file")
    message = str(excinfo.value)
    assert "PUBCHEM.COMPOUND:123" in message
    assert "PUBCHEM.COMPOUND labels file" in message
    assert "étude" in message


@pytest.mark.unit
def test_check_encoding_passes_clean_text():
    check_encoding("water", curie="CHEBI:15377", source="CHEBI labels file")


@pytest.mark.unit
def test_allowlisted_text_does_not_raise(monkeypatch):
    monkeypatch.setattr(encoding_module, "get_config", lambda: {"encoding_check_allowlist": ["Ã©tude"]}, raising=True)
    check_encoding("Ã©tude", curie="X:1", source="test")


@pytest.mark.unit
def test_check_can_be_disabled(monkeypatch):
    monkeypatch.setattr(encoding_module, "get_config", lambda: {"encoding_check_enabled": False}, raising=True)
    check_encoding("Ã©tude", curie="X:1", source="test")


# ---------------------------------------------------------------------------
# scan_file: the reporting path used by the survey tool
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scan_labels_file(tmp_path):
    path = tmp_path / "labels"
    path.write_text("CHEBI:15377\twater\nPUBCHEM.COMPOUND:1\tÃ©tude\n", encoding="utf-8")
    issues = scan_file(path)
    assert len(issues) == 1
    line_no, curie, text, _reason = issues[0]
    assert (line_no, curie, text) == (2, "PUBCHEM.COMPOUND:1", "Ã©tude")


@pytest.mark.unit
def test_scan_synonyms_file(tmp_path):
    """A synonyms line is three fields; the synonym is the last one, not the second."""
    path = tmp_path / "synonyms"
    path.write_text(
        "CHEBI:15377\thttp://example.org/exactSynonym\tdihydrogen oxide\n"
        "PUBCHEM.COMPOUND:1\thttp://example.org/relatedSynonym\tÃ©tude\n",
        encoding="utf-8",
    )
    issues = scan_file(path)
    assert [(curie, text) for _line, curie, text, _reason in issues] == [("PUBCHEM.COMPOUND:1", "Ã©tude")]


@pytest.mark.unit
def test_scan_compendium_jsonl(tmp_path):
    path = tmp_path / "Chemical.txt"
    path.write_text(
        json.dumps(
            {
                "type": "biolink:SmallMolecule",
                "identifiers": [{"i": "PUBCHEM.COMPOUND:1", "l": "Ã©tude"}],
                "preferred_name": "Ã©tude",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    issues = scan_file(path)
    # Once for the identifier label, once for the preferred name.
    assert len(issues) == 2
    assert all(curie == "PUBCHEM.COMPOUND:1" for _line, curie, _text, _reason in issues)


@pytest.mark.unit
def test_scan_synonyms_jsonl(tmp_path):
    path = tmp_path / "Chemical.txt"
    path.write_text(
        json.dumps({"curie": "PUBCHEM.COMPOUND:1", "names": ["water", "Ã©tude"], "preferred_name": "water"}) + "\n",
        encoding="utf-8",
    )
    issues = scan_file(path)
    assert [(curie, text) for _line, curie, text, _reason in issues] == [("PUBCHEM.COMPOUND:1", "Ã©tude")]


@pytest.mark.unit
def test_scan_clean_file_returns_nothing(tmp_path):
    path = tmp_path / "labels"
    path.write_text("CHEBI:15377\twater\nMONDO:1\tMénière disease\n", encoding="utf-8")
    assert scan_file(path) == []
