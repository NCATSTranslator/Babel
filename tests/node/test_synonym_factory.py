import json
from collections import defaultdict

import pytest

import src.node as node_module
from src.node import SynonymFactory
from src.util import get_config

BIOLINK_VERSION = get_config()["biolink_version"]

HAS_EXACT_SYNONYM = "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym"


@pytest.mark.unit
def test_load_synonyms_single_column(tmp_path):
    """load_synonyms() must handle single-column lines (identifier with no label) without dropping them."""
    label_dir = tmp_path / "CHEMBL.COMPOUND"
    label_dir.mkdir()
    (label_dir / "labels").write_text("CHEMBL.COMPOUND:CHEMBL1\tWater\nCHEMBL.COMPOUND:CHEMBL2\n")
    sf = object.__new__(SynonymFactory)
    sf.synonym_dir = tmp_path
    sf.synonyms = {}
    sf.common_synonyms = defaultdict(set)

    sf.load_synonyms("CHEMBL.COMPOUND")

    assert (HAS_EXACT_SYNONYM, "Water") in sf.synonyms["CHEMBL.COMPOUND"]["CHEMBL.COMPOUND:CHEMBL1"]
    assert (HAS_EXACT_SYNONYM, "") in sf.synonyms["CHEMBL.COMPOUND"]["CHEMBL.COMPOUND:CHEMBL2"]


def _bare_synonym_factory(tmp_path):
    """A SynonymFactory over tmp_path, bypassing __init__ (which loads the common synonym files)."""
    sf = object.__new__(SynonymFactory)
    sf.synonym_dir = tmp_path
    sf.synonyms = {}
    sf.common_synonyms = defaultdict(set)
    return sf


@pytest.mark.unit
def test_load_synonyms_rejects_a_damaged_label(tmp_path):
    """A mojibake label must abort the load, naming the CURIE and the file it came from.

    This is the wiring test for src/synonyms/encoding.py: the detector is tested on its own in
    tests/synonyms/test_encoding.py, this proves it is actually reached from the load path.
    """
    label_dir = tmp_path / "PUBCHEM.COMPOUND"
    label_dir.mkdir()
    (label_dir / "labels").write_text("PUBCHEM.COMPOUND:1\tÃ©tude\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as excinfo:
        _bare_synonym_factory(tmp_path).load_synonyms("PUBCHEM.COMPOUND")

    message = str(excinfo.value)
    assert "PUBCHEM.COMPOUND:1" in message
    assert "labels" in message
    assert "étude" in message  # the repaired guess, which is what makes the error actionable


@pytest.mark.unit
def test_load_synonyms_rejects_a_damaged_synonym(tmp_path):
    """The synonyms file is checked too, on its third column rather than its second."""
    label_dir = tmp_path / "PUBCHEM.COMPOUND"
    label_dir.mkdir()
    (label_dir / "synonyms").write_text(f"PUBCHEM.COMPOUND:1\t{HAS_EXACT_SYNONYM}\tÃ©tude\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="PUBCHEM.COMPOUND:1"):
        _bare_synonym_factory(tmp_path).load_synonyms("PUBCHEM.COMPOUND")


@pytest.mark.unit
def test_load_synonyms_accepts_legitimate_non_ascii(tmp_path):
    """Real accented and Greek-letter labels must load without complaint."""
    label_dir = tmp_path / "MONDO"
    label_dir.mkdir()
    (label_dir / "labels").write_text(
        "MONDO:1\tMénière disease\nMONDO:2\tNα-acetyl-L-lysine deficiency\n", encoding="utf-8"
    )

    sf = _bare_synonym_factory(tmp_path)
    sf.load_synonyms("MONDO")

    assert (HAS_EXACT_SYNONYM, "Ménière disease") in sf.synonyms["MONDO"]["MONDO:1"]


@pytest.mark.unit
def test_init_rejects_a_damaged_common_synonym(tmp_path, monkeypatch):
    """The common/ synonyms files are a fallback for any CURIE, so they are checked on load too.

    Patches ``src.node.get_config`` only: the encoding check and the synonym filter resolve
    get_config through their own modules, so both keep using the real config.
    """
    common_dir = tmp_path / "common"
    common_dir.mkdir()
    (common_dir / "common_synonyms.jsonl").write_text(
        json.dumps({"curie": "PUBCHEM.COMPOUND:1", "predicate": HAS_EXACT_SYNONYM, "synonym": "Ã©tude"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        node_module,
        "get_config",
        lambda: {"download_directory": str(tmp_path), "common": {"synonyms": ["common_synonyms.jsonl"]}},
        raising=True,
    )

    with pytest.raises(RuntimeError) as excinfo:
        SynonymFactory(str(tmp_path))

    message = str(excinfo.value)
    assert "PUBCHEM.COMPOUND:1" in message
    assert "étude" in message
