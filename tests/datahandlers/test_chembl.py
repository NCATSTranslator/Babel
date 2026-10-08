"""Unit tests for src/datahandlers/chembl.py (ChemblRDF)."""

from pathlib import Path

import pyoxigraph
import pytest

from src.datahandlers.chembl import ChemblRDF
from src.prefixes import CHEMBLCOMPOUND
from tests.datahandlers.conftest import RDF_NS, RDFS_NS, lit, make_graph_from_store, nn, quad

_CHEMBL_MOL_NS = "http://rdf.ebi.ac.uk/resource/chembl/molecule/"
_CCO_NS = "http://rdf.ebi.ac.uk/terms/chembl#"
_CHEMINF_NS = "http://semanticscience.org/resource/"


def _make_chembl_store() -> pyoxigraph.Store:
    """In-memory Store with two ChEMBL molecules.

    CHEMBL1234: SmallMolecule (subClassOf Substance) + label + SMILES.
    CHEMBL9999: label equal to its ID (should be filtered out by pull_labels).
    """
    store = pyoxigraph.Store()
    small_mol = nn(f"{_CCO_NS}SmallMolecule")
    substance = nn(f"{_CCO_NS}Substance")
    mol1 = nn(f"{_CHEMBL_MOL_NS}CHEMBL1234")
    mol2 = nn(f"{_CHEMBL_MOL_NS}CHEMBL9999")

    # Class hierarchy so subClassOf* query finds mol1 as a Substance
    store.add(quad(small_mol, nn(f"{RDFS_NS}subClassOf"), substance))

    # CHEMBL1234: real label
    store.add(quad(mol1, nn(f"{RDF_NS}type"), small_mol))
    store.add(quad(mol1, nn(f"{RDFS_NS}label"), lit("Aspirin")))

    # CHEMBL9999: label matches the chemblid → should be filtered by pull_labels
    store.add(quad(mol2, nn(f"{RDF_NS}type"), small_mol))
    store.add(quad(mol2, nn(f"{RDFS_NS}label"), lit("CHEMBL9999")))

    # SMILES chain for CHEMBL1234
    smile_bnode = nn("http://example.org/_smileEntity1")
    store.add(quad(mol1, nn(f"{_CHEMINF_NS}SIO_000008"), smile_bnode))
    store.add(quad(smile_bnode, nn(f"{RDF_NS}type"), nn(f"{_CHEMINF_NS}CHEMINF_000018")))
    store.add(quad(smile_bnode, nn(f"{_CHEMINF_NS}SIO_000300"), lit("CC(=O)Oc1ccccc1C(=O)O")))

    return store


@pytest.fixture(scope="module")
def chembl():
    return make_graph_from_store(ChemblRDF, _make_chembl_store())


@pytest.mark.unit
def test_pull_labels_writes_label(chembl, tmp_path):
    out = str(tmp_path / "labels.tsv")
    chembl.pull_labels(out)
    assert f"{CHEMBLCOMPOUND}:CHEMBL1234\tAspirin" in Path(out).read_text().splitlines()


@pytest.mark.unit
def test_pull_labels_filters_id_equal_to_label(chembl, tmp_path):
    out = str(tmp_path / "labels.tsv")
    chembl.pull_labels(out)
    assert "CHEMBL9999\tCHEMBL9999" not in Path(out).read_text()


@pytest.mark.unit
def test_pull_smiles_writes_smiles(chembl, tmp_path):
    out = str(tmp_path / "smiles.tsv")
    chembl.pull_smiles(out)
    assert f"{CHEMBLCOMPOUND}:CHEMBL1234\tCC(=O)Oc1ccccc1C(=O)O" in Path(out).read_text().splitlines()
