"""Unit tests for src/model/inchikey_audit.py: structure-less components, tiers, triage, and the whole audit over a
miniature build of the ofatumumab -> dimethyl ether clique.
"""

import duckdb
import pytest

from src.createcompendia.chemicals import UNICHEM_OVERUSED_XREF_PREFIXES
from src.model.glom_edges import classify_chemical_glom_edges
from src.model.inchikey_audit import (
    BELONGS,
    LIKELY_MISATTACHED,
    REVIEW,
    audit_chemical_inchikeys,
    core_naming_records,
    find_structureless_components,
    heavy_atoms_from_inchi,
    name_agreement,
    read_inchis,
    structure_source_count,
    tier_of,
    triage,
)
from src.util import get_config
from tests.model.chemical_build_fixture import concord, unichem, write_build, write_structure_file

# Standard InChIs copied verbatim from PubChem (CID 8254 dimethyl ether, CID 6116 calcium acetate), with PubChem's
# HeavyAtomCount for each: 3 and 9.
DIMETHYL_ETHER_INCHI = "InChI=1S/C2H6O/c1-3-2/h1-2H3"
DIMETHYL_ETHER_KEY = "INCHIKEY:LCGLNKUTAGEVQW-UHFFFAOYSA-N"
CALCIUM_ACETATE_INCHI = "InChI=1S/2C2H4O2.Ca/c2*1-2(3)4;/h2*1H3,(H,3,4);/q;;+2/p-2"

# COMPONENTS


@pytest.mark.unit
def test_components_are_connected_structureless_groups_with_their_boundary_edges():
    """Structure-less members joined to each other should form one component; one joined only to the core should
    form another; each component should keep exactly the edges that reach the core."""
    edges = [
        ("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:1", False, True),
        ("DrugCentral", "DrugCentral:1", "UNII:X", False, False),
        ("RXNORM", "RXCUI:5", "UNII:X", False, False),
        ("PUBCHEM_CAS", "PUBCHEM.COMPOUND:1", "CAS:1", True, False),
        ("CHEBI", "CHEBI:1", "PUBCHEM.COMPOUND:1", True, True),
    ]
    comps = {c.members: c.boundary for c in find_structureless_components(7, edges)}

    assert comps == {
        frozenset({"DrugCentral:1", "UNII:X", "RXCUI:5"}): (("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:1"),),
        frozenset({"CAS:1"}): (("PUBCHEM_CAS", "PUBCHEM.COMPOUND:1", "CAS:1"),),
    }


@pytest.mark.unit
def test_structure_source_count_counts_distinct_unichem_sources_only():
    """Two ChEMBL records count once, and vocabularies that never carry structures (MeSH, RxNorm) not at all."""
    members = ["CHEMBL.COMPOUND:CHEMBL1", "CHEMBL.COMPOUND:CHEMBL2", "DRUGBANK:DB1", "MESH:D1", "RXCUI:1"]
    assert structure_source_count(members) == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    "n_sources,non_small,expected",
    [(5, False, "A"), (3, True, "A"), (2, False, "B"), (1, True, "B"), (0, True, "T"), (0, False, None)],
)
def test_tier_of(n_sources, non_small, expected):
    """Three or more structure sources is tier A, one or two tier B, none with a non-small declared type tier T."""
    assert tier_of(n_sources, non_small) == expected


# STRUCTURE SIZE AND NAMES


@pytest.mark.unit
def test_heavy_atoms_from_inchi_matches_pubchem():
    """Heavy-atom counts from the InChI formula layer should match PubChem's, including multi-component salts."""
    assert heavy_atoms_from_inchi(DIMETHYL_ETHER_INCHI) == 3
    assert heavy_atoms_from_inchi(CALCIUM_ACETATE_INCHI) == 9


@pytest.mark.unit
def test_heavy_atoms_from_inchi_rejects_a_non_inchi():
    """A string that is not an InChI should raise rather than count as zero atoms."""
    with pytest.raises(ValueError):
        heavy_atoms_from_inchi("LCGLNKUTAGEVQW-UHFFFAOYSA-N")


@pytest.mark.unit
def test_name_agreement():
    """The same substance named by different sources should agree; an antibody and a solvent should not."""
    assert name_agreement(["semaglutide"], ["Semaglutide", "CID 122189768"]) >= 0.6
    assert name_agreement(["ofatumumab", "OFATUMUMAB"], ["Dimethyl Ether", "methoxymethane"]) < 0.6
    assert name_agreement([], ["anything"]) == 0.0


@pytest.mark.unit
@pytest.mark.parametrize(
    "score,heavy,expected",
    [
        (1.0, 291, BELONGS),  # semaglutide: names agree, peptide-sized core
        (0.08, 3, LIKELY_MISATTACHED),  # ofatumumab -> dimethyl ether
        (0.93, 4, REVIEW),  # macrogol -> ethylene glycol: names agree on a monomer-sized core
        (0.01, 119, REVIEW),  # givosiran -> its GalNAc conjugate: large core, names disagree
        (1.0, None, REVIEW),  # the key is not in UniChem's structure file
    ],
)
def test_triage(score, heavy, expected):
    """Triage should clear only agreeing names on a non-trivial core, and condemn only disagreeing names on a
    small-molecule core; everything else goes to review."""
    assert triage(score, heavy) == expected


@pytest.mark.unit
def test_read_inchis_returns_only_the_keys_asked_for(tmp_path):
    """Only requested keys are returned, keyed by INCHIKEY CURIE; a missing key is simply absent."""
    path = write_structure_file(
        tmp_path / "structure.tsv.gz",
        [
            ("1", DIMETHYL_ETHER_INCHI, "LCGLNKUTAGEVQW-UHFFFAOYSA-N"),
            ("2", CALCIUM_ACETATE_INCHI, "VSGNNIFQASZAOI-UHFFFAOYSA-L"),
        ],
    )
    found = read_inchis(str(path), [DIMETHYL_ETHER_KEY, "INCHIKEY:NOTPRESENTNOTPR-UHFFFAOYSA-N"])
    assert found == {DIMETHYL_ETHER_KEY: DIMETHYL_ETHER_INCHI}


# WHOLE AUDIT

# The ofatumumab / dimethyl ether glom set of Babel 2026jul22: concord rows copied verbatim from its
# duckdb/Concord.parquet (file name, subject, object), labels from its Node.parquet. DrugCentral's identifier table
# gives DrugCentral:4951 (ofatumumab) PubChem CID 8254 (dimethyl ether); nothing else joins the two.
OFATUMUMAB_CONCORDS = [
    (concord("CHEBI"), "CHEBI:28887", "PUBCHEM.COMPOUND:8254"),
    (concord("DrugCentral"), "DrugCentral:4951", "CHEMBL.COMPOUND:CHEMBL1201836"),
    (concord("DrugCentral"), "DrugCentral:4951", "DRUGBANK:DB06650"),
    (concord("DrugCentral"), "DrugCentral:4951", "GTOPDB:6778"),
    (concord("DrugCentral"), "DrugCentral:4951", "PUBCHEM.COMPOUND:8254"),
    (concord("DrugCentral"), "DrugCentral:4951", "UMLS:C1832027"),
    (concord("DrugCentral"), "DrugCentral:4951", "UNII:M95KG522R0"),
    (concord("PUBCHEM_MESH"), "PUBCHEM.COMPOUND:8254", "MESH:C033413"),
    (concord("RXNORM"), "RXCUI:712566", "DRUGBANK:DB06650"),
    (concord("mesh_unii"), "MESH:C033413", "UNII:AM13FS69BX"),
    (unichem("CHEBI"), "CHEBI:28887", DIMETHYL_ETHER_KEY),
    (unichem("CHEMBL.COMPOUND"), "CHEMBL.COMPOUND:CHEMBL119178", DIMETHYL_ETHER_KEY),
    (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:8254", DIMETHYL_ETHER_KEY),
    (unichem("UNII"), "UNII:AM13FS69BX", DIMETHYL_ETHER_KEY),
]
OFATUMUMAB_LABELS = {
    "CHEBI:28887": "dimethyl ether",
    "UNII:AM13FS69BX": "DIMETHYL ETHER",
    "UNII:M95KG522R0": "OFATUMUMAB",
    "PUBCHEM.COMPOUND:8254": "Dimethyl Ether",
    "CHEMBL.COMPOUND:CHEMBL119178": "METHOXYMETHANE",
    "CHEMBL.COMPOUND:CHEMBL1201836": "OFATUMUMAB",
    "DRUGBANK:DB06650": "Ofatumumab",
    "MESH:C033413": "dimethyl ether",
    "DrugCentral:4951": "ofatumumab",
    "GTOPDB:6778": "ofatumumab",
    "UMLS:C1832027": "ofatumumab",
}


def run_audit(tmp_path, concords, cliques, labels, structures):
    root = write_build(tmp_path / "build", concords, cliques, labels)
    structure_file = write_structure_file(tmp_path / "structure.tsv.gz", structures)
    types = [o.removesuffix(".txt") for o in get_config()["chemical_outputs"]]
    edges = [f"{root}/duckdb/parquet/filename={t}/Edge.parquet" for t in types]
    nodes = [f"{root}/duckdb/parquet/filename={t}/Node.parquet" for t in types]
    con = duckdb.connect()
    classify_chemical_glom_edges(
        con, f"{root}/duckdb/Concord.parquet", edges, get_config()["chemical_concords"], UNICHEM_OVERUSED_XREF_PREFIXES
    )
    work = tmp_path / "work"
    work.mkdir()
    audit_chemical_inchikeys(con, str(work), edges, nodes, f"{root}/duckdb/Identifier.parquet", str(structure_file))
    return con


@pytest.mark.unit
def test_ofatumumab_is_flagged_tier_a_likely_misattached_with_its_one_bad_edge(tmp_path):
    """The antibody's records should form one tier A component (five structure sources, no structure), triaged
    likely misattached against a 3-heavy-atom core, attached by exactly the DrugCentral -> CID 8254 edge."""
    members = sorted({c for _, s, o in OFATUMUMAB_CONCORDS for c in (s, o)} | {"RXCUI:712566"})
    cliques = {"CHEBI:28887": ("SmallMolecule", members)}
    structures = [("1", DIMETHYL_ETHER_INCHI, DIMETHYL_ETHER_KEY.split(":", 1)[1])]
    con = run_audit(tmp_path, OFATUMUMAB_CONCORDS, cliques, OFATUMUMAB_LABELS, structures)

    comps = con.sql("""SELECT clique_leader, inchikey, tier, verdict, n_structure_sources, core_heavy_atoms,
                              structureless_members FROM audit_component""").fetchall()
    assert comps == [
        (
            "CHEBI:28887",
            DIMETHYL_ETHER_KEY,
            "A",
            LIKELY_MISATTACHED,
            5,
            3,
            "CHEMBL.COMPOUND:CHEMBL1201836 DRUGBANK:DB06650 DrugCentral:4951 GTOPDB:6778 RXCUI:712566 "
            "UMLS:C1832027 UNII:M95KG522R0",
        )
    ]
    assert con.sql("SELECT source, subj, obj FROM audit_boundary").fetchall() == [
        ("DrugCentral", "DrugCentral:4951", "PUBCHEM.COMPOUND:8254")
    ]


# The chymopapain / Tiron glom set of Babel 2026jul22: applied concord rows copied verbatim from its Concord.parquet,
# labels from its Node.parquet, and Tiron's row from UniChem's structure.tsv.gz (UCI 651978). CHEBI:193860 and
# HMDB:HMDB0029845 carry Tiron's structure but are labelled "Chymopapain", so a core label matches the enzyme's name.
TIRON_KEY = "INCHIKEY:XXAXVMUWHZHZMJ-UHFFFAOYSA-N"
TIRON_INCHI = "InChI=1S/C6H6O8S2/c7-4-1-3(15(9,10)11)2-5(6(4)8)16(12,13)14/h1-2,7-8H,(H,9,10,11)(H,12,13,14)"
CHYMOPAPAIN_CONCORDS = [
    (concord("CHEBI"), "CHEBI:193860", "PUBCHEM.COMPOUND:9002"),
    (concord("DrugCentral"), "DrugCentral:5131", "CHEMBL.COMPOUND:CHEMBL1201626"),
    (concord("DrugCentral"), "DrugCentral:5131", "DRUGBANK:DB06752"),
    (concord("DrugCentral"), "DrugCentral:5131", "MESH:D002917"),
    (concord("DrugCentral"), "DrugCentral:5131", "PUBCHEM.COMPOUND:9002"),
    (concord("DrugCentral"), "DrugCentral:5131", "UMLS:C0008736"),
    (concord("DrugCentral"), "DrugCentral:5131", "UNII:1UK146T40N"),
    (concord("PUBCHEM_CAS"), "PUBCHEM.COMPOUND:9002", "CAS:149-46-2"),
    (concord("PUBCHEM_CAS"), "PUBCHEM.COMPOUND:9002", "CAS:205-742-0"),
    (concord("RXNORM"), "RXCUI:2525", "DRUGBANK:DB06752"),
    (unichem("CHEBI"), "CHEBI:193860", TIRON_KEY),
    (unichem("CHEMBL.COMPOUND"), "CHEMBL.COMPOUND:CHEMBL1205542", TIRON_KEY),
    (unichem("HMDB"), "HMDB:HMDB0029845", TIRON_KEY),
    (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:9002", TIRON_KEY),
    (unichem("UNII"), "UNII:306J0THJ9U", TIRON_KEY),
]
CHYMOPAPAIN_LABELS = {
    "CHEBI:193860": "Chymopapain",
    "UNII:306J0THJ9U": "TIRON FREE ACID",
    "HMDB:HMDB0029845": "Chymopapain",
    "PUBCHEM.COMPOUND:9002": "4,5-Dihydroxy-1,3-benzenedisulfonic acid",
    "CHEMBL.COMPOUND:CHEMBL1201626": "CHYMOPAPAIN",
    "UMLS:C0008736": "chymopapain",
    "UNII:1UK146T40N": "CHYMOPAPAIN",
    "DrugCentral:5131": "chymopapain",
    "MESH:D002917": "Chymopapain",
    "DRUGBANK:DB06752": "Chymopapain",
}


@pytest.mark.unit
def test_core_naming_records_prefers_pubchem():
    """Core labels should come from the PubChem CIDs when there are any, and from every core record otherwise."""
    assert core_naming_records(["CHEBI:193860", "PUBCHEM.COMPOUND:9002"]) == ["PUBCHEM.COMPOUND:9002"]
    assert core_naming_records(["CHEBI:193860", "HMDB:HMDB0029845"]) == ["CHEBI:193860", "HMDB:HMDB0029845"]


@pytest.mark.unit
def test_a_core_record_named_after_the_biologic_does_not_clear_it(tmp_path):
    """Chymopapain attached to Tiron should triage likely misattached even though two Tiron-structured core records are
    labelled "Chymopapain": the core is named by its PubChem CID, 4,5-dihydroxy-1,3-benzenedisulfonic acid."""
    members = sorted({c for _, s, o in CHYMOPAPAIN_CONCORDS for c in (s, o)})
    cliques = {"CHEBI:193860": ("SmallMolecule", members)}
    structures = [("651978", TIRON_INCHI, TIRON_KEY.split(":", 1)[1])]
    con = run_audit(tmp_path, CHYMOPAPAIN_CONCORDS, cliques, CHYMOPAPAIN_LABELS, structures)

    assert con.sql("SELECT tier, verdict, core_heavy_atoms FROM audit_component").fetchall() == [
        ("A", LIKELY_MISATTACHED, 16)
    ]
