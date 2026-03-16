import pytest

import src.prefixes as pref
from src.LabeledID import LabeledID

# Node schema (as of the current codebase):
#   {"identifiers": [{"identifier": CURIE, "label": str}, ...], "type": str}
# identifiers[0] is the preferred identifier (highest-priority prefix first).
# Labels stay with their own identifier; they are not promoted to the first entry.
# "type" is a single biolink type string, not a list of ancestors.


@pytest.mark.network
def test_get_ancestors(node_factory):
    """ """
    ancestors = node_factory.get_ancestors("biolink:ChemicalEntity")
    # biolink 4.3.6 adds several mixins compared to earlier versions
    assert len(ancestors) == 8
    assert "biolink:ChemicalEntity" in ancestors  # self is in ancestors
    assert "biolink:PhysicalEssence" in ancestors
    assert "biolink:NamedThing" in ancestors
    assert "biolink:Entity" in ancestors
    assert "biolink:PhysicalEssenceOrOccurrent" in ancestors  # mixins are in ancestors
    assert "biolink:ChemicalOrDrugOrTreatment" in ancestors
    assert "biolink:ChemicalEntityOrGeneOrGeneProduct" in ancestors
    assert "biolink:ChemicalEntityOrProteinOrPolypeptide" in ancestors


@pytest.mark.network
def test_prefixes(node_factory):
    prefixes = node_factory.get_prefixes("biolink:SmallMolecule")
    # Prefix order and membership reflect biolink 4.3.6; update this list when the
    # model version in config.yaml is bumped.
    expected_prefixes = [
        pref.CHEBI,
        pref.UNII,
        pref.PUBCHEMCOMPOUND,
        pref.CHEMBLCOMPOUND,
        pref.DRUGBANK,
        pref.MESH,
        pref.CAS,
        pref.DRUGCENTRAL,
        pref.GTOPDB,
        pref.HMDB,
        pref.KEGGCOMPOUND,
        pref.PHARMGKB_DRUG,
        pref.CHEMBANK,
        pref.PUBCHEMSUBSTANCE,
        pref.SIDERDRUG,
        pref.INCHI,
        pref.INCHIKEY,
        pref.BIGG_METABOLITE,
        pref.FOODB_COMPOUND,
        pref.KEGGGLYCAN,
        pref.KEGGDRUG,
        pref.KEGGENVIRON,
        pref.KEGG,
        pref.UMLS,
    ]
    assert prefixes == expected_prefixes


@pytest.mark.network
def test_taxon_prefixes(node_factory):
    """There was some churn in biolink around organism, so we had it specialcased for a while"""
    prefixes = node_factory.get_prefixes("biolink:OrganismTaxon")
    expected_prefixes = [pref.NCBITAXON, pref.MESH, pref.UMLS]
    assert prefixes == expected_prefixes


@pytest.mark.network
def test_normalization(node_factory):
    """Basic normalization - do we pick the right identifier?  Note that the identifiers are made up."""
    node = node_factory.create_node(["MESH:D012034", "CHEBI:1234"], "biolink:SmallMolecule")
    assert node["identifiers"][0]["identifier"] == "CHEBI:1234"  # CHEBI ranks above MESH
    assert len(node["identifiers"]) == 2
    ids = [x["identifier"] for x in node["identifiers"]]
    assert "MESH:D012034" in ids
    assert "CHEBI:1234" in ids
    assert node["type"] == "biolink:SmallMolecule"  # type is now a single string, not a list


@pytest.mark.network
def test_normalization_bad_prefix(node_factory):
    """When we include the prefix CHEMBL, it does not get added to the list of prefixes (it should be CHEMBL.COMPOUND)"""
    node = node_factory.create_node(["MESH:D012034", "CHEBI:1234", "CHEMBL:CHEMBL123"], "biolink:SmallMolecule")
    assert node["identifiers"][0]["identifier"] == "CHEBI:1234"
    assert len(node["identifiers"]) == 2  # CHEMBL: filtered out, only CHEBI + MESH remain
    ids = [x["identifier"] for x in node["identifiers"]]
    assert "MESH:D012034" in ids
    assert "CHEBI:1234" in ids


@pytest.mark.network
def test_normalization_labeled_id(node_factory):
    """Make sure that the node creator can handle labels passed as a dict"""
    labels = {"CHEBI:1234": "name"}
    node = node_factory.create_node(["MESH:D012034", "CHEBI:1234", "CHEMBL:CHEMBL123"], "biolink:SmallMolecule", labels)
    assert node["identifiers"][0]["identifier"] == "CHEBI:1234"
    assert node["identifiers"][0]["label"] == "name"
    assert len(node["identifiers"]) == 2
    assert "MESH:D012034" in [x["identifier"] for x in node["identifiers"]]


@pytest.mark.network
def test_labeling_2(node_factory):
    """Labels remain on the identifier that owns them; they are not promoted to the preferred node.
    Here only the dictyBase identifier has a label."""
    node = node_factory.create_node(
        [f"{pref.ENSEMBL}:81239", f"{pref.NCBIGENE}:123", f"{pref.DICTYBASE}:1234"],
        "biolink:Gene",
        {f"{pref.DICTYBASE}:1234": "name"},
    )
    assert node["identifiers"][0]["identifier"] == f"{pref.NCBIGENE}:123"
    assert node["identifiers"][1]["identifier"] == f"{pref.ENSEMBL}:81239"
    assert node["identifiers"][2]["identifier"] == f"{pref.DICTYBASE}:1234"
    assert node["identifiers"][2]["label"] == "name"
    # The preferred identifier (NCBIGene) has no label because none was provided for it
    assert "label" not in node["identifiers"][0]


@pytest.mark.network
def test_clean_list(node_factory):
    input_ids = frozenset({"UMLS:C1839767", "UMLS:C1853383", LabeledID("HP:0010804", "Tented upper lip vermilion"), "UMLS:C1850072", "HP:0010804"})
    output = node_factory.clean_list(input_ids)
    assert len(output) == 4
    lidfound = False
    for x in output:
        if isinstance(x, LabeledID):
            lidfound = True
            assert x.identifier == "HP:0010804"
    assert lidfound


@pytest.mark.network
def test_losing_umls(node_factory):
    input_ids = frozenset({"HP:0010804", "UMLS:C1839767", "UMLS:C1853383", "HP:0010804", "UMLS:C1850072"})
    node = node_factory.create_node(input_ids, "biolink:PhenotypicFeature", {"HP:0010804": "Tented upper lip vermilion"})
    assert node["identifiers"][0]["identifier"] == "HP:0010804"
    assert node["identifiers"][0]["label"] == "Tented upper lip vermilion"
    assert len(node["identifiers"]) == 4  # HP + 3 UMLS


@pytest.mark.network
def test_same_value_different_prefix(node_factory):
    input_ids = frozenset({"FB:FBgn0261954", "ENSEMBL:FBgn0261954", "NCBIGene:46006"})
    node = node_factory.create_node(input_ids, "biolink:Gene", {})
    assert len(node["identifiers"]) == 3
    assert len(set([x["identifier"] for x in node["identifiers"]])) == 3


@pytest.mark.network
def test_pubchem_simple(node_factory):
    """When multiple PUBCHEM.COMPOUND identifiers exist, prefer the one whose label matches other
    identifiers in the clique.  In biolink 4.3.6 CHEBI ranks above PUBCHEM.COMPOUND, so CHEBI is
    the overall preferred identifier; the pubchem ordering is verified by checking position [1]."""
    node = node_factory.create_node(
        [f"{pref.PUBCHEMCOMPOUND}:999", f"{pref.PUBCHEMCOMPOUND}:111", f"{pref.CHEBI}:XYZ"],
        "biolink:SmallMolecule",
        {f"{pref.PUBCHEMCOMPOUND}:999": "water", f"{pref.PUBCHEMCOMPOUND}:111": "h", f"{pref.CHEBI}:XYZ": "WATER"},
    )
    assert node["identifiers"][0]["identifier"] == f"{pref.CHEBI}:XYZ"  # CHEBI wins overall
    # Among the two PUBCHEMs, :999 ("water") matches the CHEBI label "WATER" → ranked first
    assert node["identifiers"][1]["identifier"] == f"{pref.PUBCHEMCOMPOUND}:999"
    assert node["identifiers"][1]["label"] == "water"


@pytest.mark.network
def test_pubchem_no_match(node_factory):
    """When no PUBCHEM label matches other identifiers, prefer the one with the shortest label."""
    node = node_factory.create_node(
        [f"{pref.PUBCHEMCOMPOUND}:999", f"{pref.PUBCHEMCOMPOUND}:111", f"{pref.CHEBI}:XYZ"],
        "biolink:SmallMolecule",
        {f"{pref.PUBCHEMCOMPOUND}:999": "h", f"{pref.PUBCHEMCOMPOUND}:111": "water", f"{pref.CHEBI}:XYZ": "blahblah"},
    )
    assert node["identifiers"][0]["identifier"] == f"{pref.CHEBI}:XYZ"  # CHEBI wins overall
    # Among the two PUBCHEMs, :999 ("h") has the shortest label → ranked first
    assert node["identifiers"][1]["identifier"] == f"{pref.PUBCHEMCOMPOUND}:999"
    assert node["identifiers"][1]["label"] == "h"


@pytest.mark.network
def test_pubchem_ignore_CID(node_factory):
    """When choosing the shortest PUBCHEM label, skip labels that start with 'CID'."""
    node = node_factory.create_node(
        [f"{pref.PUBCHEMCOMPOUND}:999", f"{pref.PUBCHEMCOMPOUND}:111", f"{pref.CHEBI}:XYZ"],
        "biolink:SmallMolecule",
        {f"{pref.PUBCHEMCOMPOUND}:999": "CID1", f"{pref.PUBCHEMCOMPOUND}:111": "longerlabel", f"{pref.CHEBI}:XYZ": "blahblah"},
    )
    assert node["identifiers"][0]["identifier"] == f"{pref.CHEBI}:XYZ"  # CHEBI wins overall
    # :999 has label "CID1" which is ignored; :111 ("longerlabel") is preferred instead
    assert node["identifiers"][1]["identifier"] == f"{pref.PUBCHEMCOMPOUND}:111"
    assert node["identifiers"][1]["label"] == "longerlabel"
