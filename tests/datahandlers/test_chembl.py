"""Unit tests for src/datahandlers/chembl.py (ChemblRDF)."""
import pyoxigraph
import pytest

from src.datahandlers.chembl import ChemblRDF
from src.prefixes import CHEMBLCOMPOUND

_CHEMBL_MOL_NS = "http://rdf.ebi.ac.uk/resource/chembl/molecule/"
_CCO_NS = "http://rdf.ebi.ac.uk/terms/chembl#"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
_CHEMINF_NS = "http://semanticscience.org/resource/"


def _nn(iri: str) -> pyoxigraph.NamedNode:
    return pyoxigraph.NamedNode(iri)


def _lit(val: str) -> pyoxigraph.Literal:
    return pyoxigraph.Literal(val)


def _quad(s, p, o) -> pyoxigraph.Quad:
    return pyoxigraph.Quad(s, p, o, pyoxigraph.DefaultGraph())


def _make_chembl_store() -> pyoxigraph.Store:
    """In-memory Store with two ChEMBL molecules.

    CHEMBL1234: SmallMolecule (subClassOf Substance) + label + SMILES.
    CHEMBL9999: label equal to its ID (should be filtered out by pull_labels).
    """
    store = pyoxigraph.Store()
    rdf_type = _nn(f"{_RDF_NS}type")
    rdfs_label = _nn(f"{_RDFS_NS}label")
    rdfs_sub = _nn(f"{_RDFS_NS}subClassOf")

    small_mol = _nn(f"{_CCO_NS}SmallMolecule")
    substance = _nn(f"{_CCO_NS}Substance")
    mol1 = _nn(f"{_CHEMBL_MOL_NS}CHEMBL1234")
    mol2 = _nn(f"{_CHEMBL_MOL_NS}CHEMBL9999")

    # Class hierarchy so subClassOf* query finds mol1 as a Substance
    store.add(_quad(small_mol, rdfs_sub, substance))

    # CHEMBL1234: real label
    store.add(_quad(mol1, rdf_type, small_mol))
    store.add(_quad(mol1, rdfs_label, _lit("Aspirin")))

    # CHEMBL9999: label matches the chemblid → should be filtered by pull_labels
    store.add(_quad(mol2, rdf_type, small_mol))
    store.add(_quad(mol2, rdfs_label, _lit("CHEMBL9999")))

    # SMILES chain for CHEMBL1234
    sio_has_part = _nn(f"{_CHEMINF_NS}SIO_000008")
    sio_smiles_entity = _nn(f"{_CHEMINF_NS}CHEMINF_000018")
    sio_value = _nn(f"{_CHEMINF_NS}SIO_000300")
    smile_bnode = _nn("http://example.org/_smileEntity1")
    store.add(_quad(mol1, sio_has_part, smile_bnode))
    store.add(_quad(smile_bnode, rdf_type, sio_smiles_entity))
    store.add(_quad(smile_bnode, sio_value, _lit("CC(=O)Oc1ccccc1C(=O)O")))

    return store


def _make_chembl(store: pyoxigraph.Store) -> ChemblRDF:
    obj = ChemblRDF.__new__(ChemblRDF)
    obj.m = store
    return obj


@pytest.fixture(scope="module")
def chembl():
    return _make_chembl(_make_chembl_store())


@pytest.mark.unit
def test_pull_labels_writes_label(chembl, tmp_path):
    out = str(tmp_path / "labels.tsv")
    chembl.pull_labels(out)
    lines = open(out).read().splitlines()
    assert f"{CHEMBLCOMPOUND}:CHEMBL1234\tAspirin" in lines


@pytest.mark.unit
def test_pull_labels_filters_id_equal_to_label(chembl, tmp_path):
    out = str(tmp_path / "labels.tsv")
    chembl.pull_labels(out)
    content = open(out).read()
    assert "CHEMBL9999\tCHEMBL9999" not in content


@pytest.mark.unit
def test_pull_smiles_writes_smiles(chembl, tmp_path):
    out = str(tmp_path / "smiles.tsv")
    chembl.pull_smiles(out)
    lines = open(out).read().splitlines()
    assert f"{CHEMBLCOMPOUND}:CHEMBL1234\tCC(=O)Oc1ccccc1C(=O)O" in lines
