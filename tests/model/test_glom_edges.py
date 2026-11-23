"""Unit tests for src/model/glom_edges.py: reconstructing what glom() did with each chemical concord edge.

The builds here are synthetic: each is the smallest set of cliques and concord rows that exercises one path through
the classification (applied, InChIKey refusal, overused filter, the #83 split, CUI ownership, keys dropped from Drug
and Food) or one way the model can fail to describe a build.
"""

import duckdb
import pytest

from src.babel_utils import unique_prefixes_from_config
from src.createcompendia.chemicals import UNICHEM_OVERUSED_XREF_PREFIXES
from src.model.glom_edges import (
    APPLIED,
    ENDPOINT_ABSENT,
    FILTERED_BADXREF,
    FILTERED_OVERUSED,
    FILTERED_OWNED_ELSEWHERE,
    REFUSED_INCHIKEY,
    classify_chemical_glom_edges,
)
from src.prefixes import INCHIKEY
from src.util import get_config
from tests.model.chemical_build_fixture import concord, unichem, write_build

KEY_A = "INCHIKEY:AAAAAAAAAAAAAA-UHFFFAOYSA-N"
KEY_B = "INCHIKEY:BBBBBBBBBBBBBB-UHFFFAOYSA-N"
KEY_C = "INCHIKEY:CCCCCCCCCCCCCC-UHFFFAOYSA-N"


def classify(root, owned_elsewhere=(), bad_pairs=()):
    """Run classify_chemical_glom_edges over a fixture build; return {(base, subj, obj): verdict}."""
    return {(b, s, o): v for b, s, o, v, _ in classify_rows(root, owned_elsewhere, bad_pairs)}


def classify_rows(root, owned_elsewhere=(), bad_pairs=()):
    """Run classify_chemical_glom_edges over a fixture build; return (base, subj, obj, verdict, key_dropped) rows."""
    con = duckdb.connect()
    types = [o.removesuffix(".txt") for o in get_config()["chemical_outputs"]]
    classify_chemical_glom_edges(
        con,
        f"{root}/duckdb/Concord.parquet",
        {t: f"{root}/duckdb/parquet/filename={t}/Edge.parquet" for t in types},
        get_config()["chemical_concords"],
        UNICHEM_OVERUSED_XREF_PREFIXES,
        owned_elsewhere,
        bad_pairs,
        structure_concords=get_config()["chemical_structure_concords"],
    )
    return con.sql("SELECT base, subj, obj, verdict, key_dropped FROM glom_edge").fetchall()


# VERDICTS


@pytest.mark.unit
def test_verdicts_for_applied_refused_overused_and_absent_edges(tmp_path):
    """Each edge should get the verdict its fate in glom() implies.

    Two keyed cliques. An xref inside one is applied; an xref between them was refused by the InChIKey guard; a
    CAS number claimed by both CIDs in one PUBCHEM_CAS file was dropped by remove_overused_xrefs (inside or across
    cliques alike); an xref to a CURIE in no chemical output is reported as such.
    """
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:1", KEY_A),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:2", KEY_B),
        (concord("PUBCHEM_MESH"), "PUBCHEM.COMPOUND:1", "MESH:C1"),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:2"),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:1"),
        (concord("PUBCHEM_CAS"), "PUBCHEM.COMPOUND:1", "CAS:99"),
        (concord("PUBCHEM_CAS"), "PUBCHEM.COMPOUND:2", "CAS:99"),
        (concord("PUBCHEM_CAS"), "PUBCHEM.COMPOUND:2", "CAS:404"),
    ]
    cliques = {
        "PUBCHEM.COMPOUND:1": ("SmallMolecule", ["PUBCHEM.COMPOUND:1", KEY_A, "MESH:C1", "DrugCentral:1"]),
        "PUBCHEM.COMPOUND:2": ("SmallMolecule", ["PUBCHEM.COMPOUND:2", KEY_B, "CAS:99"]),
    }
    verdicts = classify(write_build(tmp_path, concords, cliques))

    assert verdicts[("UNICHEM_PUBCHEM.COMPOUND", "PUBCHEM.COMPOUND:1", KEY_A)] == APPLIED
    assert verdicts[("PUBCHEM_MESH", "PUBCHEM.COMPOUND:1", "MESH:C1")] == APPLIED
    assert verdicts[("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:1")] == APPLIED
    assert verdicts[("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:2")] == REFUSED_INCHIKEY
    assert verdicts[("PUBCHEM_CAS", "PUBCHEM.COMPOUND:1", "CAS:99")] == FILTERED_OVERUSED
    assert verdicts[("PUBCHEM_CAS", "PUBCHEM.COMPOUND:2", "CAS:99")] == FILTERED_OVERUSED
    assert verdicts[("PUBCHEM_CAS", "PUBCHEM.COMPOUND:2", "CAS:404")] == ENDPOINT_ABSENT


@pytest.mark.unit
def test_an_83_split_off_mixture_clique_is_rejoined_to_its_parent(tmp_path):
    """Edges across a #83 split should count as applied, not as unexplained crossings.

    create_typed_sets() moved PUBCHEM.COMPOUND:30 (MolecularMixture-typed) out of its glom set, leaving KEY_C and its
    CAS number in the SmallMolecule half. CID 30's own UniChem key is in the parent, which is how the pre-split set
    is found.
    """
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:3", KEY_C),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:30", KEY_C),
        (concord("PUBCHEM_CAS"), "PUBCHEM.COMPOUND:30", "CAS:30"),
    ]
    cliques = {
        "PUBCHEM.COMPOUND:3": ("SmallMolecule", ["PUBCHEM.COMPOUND:3", KEY_C, "CAS:30"]),
        "PUBCHEM.COMPOUND:30": ("MolecularMixture", ["PUBCHEM.COMPOUND:30"]),
    }
    verdicts = classify(write_build(tmp_path, concords, cliques))

    assert verdicts[("UNICHEM_PUBCHEM.COMPOUND", "PUBCHEM.COMPOUND:30", KEY_C)] == APPLIED
    assert verdicts[("PUBCHEM_CAS", "PUBCHEM.COMPOUND:30", "CAS:30")] == APPLIED


@pytest.mark.unit
def test_pairs_naming_a_cui_owned_elsewhere_are_reported_as_filtered(tmp_path):
    """A pair naming a UMLS CUI another pipeline owns was skipped by the build, so it should be reported as filtered,
    and it should not count towards another row's overuse."""
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:1", KEY_A),
        (concord("DrugCentral"), "DrugCentral:1", "UMLS:C9"),
        (concord("DrugCentral"), "DrugCentral:2", "UMLS:C9"),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:1"),
    ]
    cliques = {"PUBCHEM.COMPOUND:1": ("SmallMolecule", ["PUBCHEM.COMPOUND:1", KEY_A, "DrugCentral:1"])}
    verdicts = classify(write_build(tmp_path, concords, cliques), owned_elsewhere={"UMLS:C9"})

    assert verdicts[("DrugCentral", "DrugCentral:1", "UMLS:C9")] == FILTERED_OWNED_ELSEWHERE
    assert verdicts[("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:1")] == APPLIED


# MODEL DRIFT


def test_the_model_assumes_the_chemical_glom_restricts_inchikey_alone():
    """config.yaml: chemical_unique_prefixes should be exactly [INCHIKEY], the restriction this model assumes.

    A cross-clique edge between two keyed cliques is read as REFUSED_INCHIKEY because INCHIKEY is the only prefix
    the chemical glom() restricts. Adding a prefix there gives glom() a second reason to refuse a pair, which
    classify_chemical_glom_edges() would misreport as the InChIKey guard. Change the model first, then this test.
    """
    assert unique_prefixes_from_config("chemical_unique_prefixes") == frozenset({INCHIKEY})


@pytest.mark.unit
def test_an_unexplained_crossing_raises(tmp_path):
    """An xref joining two cliques that are not both keyed has no explanation in glom(), so classification should
    raise rather than return verdicts."""
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:1", KEY_A),
        (concord("PUBCHEM_MESH"), "PUBCHEM.COMPOUND:1", "MESH:C1"),
    ]
    cliques = {
        "PUBCHEM.COMPOUND:1": ("SmallMolecule", ["PUBCHEM.COMPOUND:1", KEY_A]),
        "MESH:C1": ("ChemicalEntity", ["MESH:C1"]),
    }
    with pytest.raises(RuntimeError, match="no filter or InChIKey refusal"):
        classify(write_build(tmp_path, concords, cliques))


@pytest.mark.unit
def test_a_split_off_clique_with_two_parents_raises(tmp_path):
    """A keyless clique whose records' keys sit in two different keyed cliques cannot be a #83 split, so the
    pre-split model should refuse it."""
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:1", KEY_A),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:2", KEY_B),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:10", KEY_A),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:20", KEY_B),
    ]
    cliques = {
        "PUBCHEM.COMPOUND:1": ("SmallMolecule", ["PUBCHEM.COMPOUND:1", KEY_A]),
        "PUBCHEM.COMPOUND:2": ("SmallMolecule", ["PUBCHEM.COMPOUND:2", KEY_B]),
        "PUBCHEM.COMPOUND:10": ("MolecularMixture", ["PUBCHEM.COMPOUND:10", "PUBCHEM.COMPOUND:20"]),
    }
    with pytest.raises(RuntimeError, match="pre-split set is ambiguous"):
        classify(write_build(tmp_path, concords, cliques))


# BAD XREFS


@pytest.mark.unit
def test_a_blocked_pair_is_filtered_and_omitting_it_fails_loudly(tmp_path):
    """A build that skipped a chemical_badxrefs pair leaves its endpoints in different cliques. Given the pair, the
    classification should report it as filtered; without it, the crossing is unexplained and should raise."""
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:1", KEY_A),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:1"),
        (concord("DrugCentral"), "DrugCentral:1", "DRUGBANK:DB1"),
    ]
    cliques = {
        "PUBCHEM.COMPOUND:1": ("SmallMolecule", ["PUBCHEM.COMPOUND:1", KEY_A]),
        "DrugCentral:1": ("ChemicalEntity", ["DrugCentral:1", "DRUGBANK:DB1"]),
    }
    root = write_build(tmp_path, concords, cliques)

    verdicts = classify(root, bad_pairs={("PUBCHEM.COMPOUND:1", "DrugCentral:1")})
    assert verdicts[("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:1")] == FILTERED_BADXREF
    assert verdicts[("DrugCentral", "DrugCentral:1", "DRUGBANK:DB1")] == APPLIED
    with pytest.raises(RuntimeError, match="no filter or InChIKey refusal"):
        classify(root)


@pytest.mark.unit
def test_a_blocked_pair_naming_a_cui_owned_elsewhere_is_reported_as_a_bad_xref(tmp_path):
    """build_untyped_compendia() matches bad pairs before the owned-elsewhere skip, so a pair that is both should be
    reported as a bad xref, the way the build counts it."""
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:1", KEY_A),
        (concord("DrugCentral"), "DrugCentral:1", "UMLS:C9"),
    ]
    cliques = {"PUBCHEM.COMPOUND:1": ("SmallMolecule", ["PUBCHEM.COMPOUND:1", KEY_A])}
    verdicts = classify(
        write_build(tmp_path, concords, cliques),
        owned_elsewhere={"UMLS:C9"},
        bad_pairs={("DrugCentral:1", "UMLS:C9")},
    )

    assert verdicts[("DrugCentral", "DrugCentral:1", "UMLS:C9")] == FILTERED_BADXREF


# KEYS DROPPED FROM DRUG AND FOOD


@pytest.mark.unit
def test_a_drug_cliques_dropped_key_edges_are_applied(tmp_path):
    """Drug does not register INCHIKEY, so write_compendium() drops the key from a Drug clique. Its records' UniChem
    edges to that key were applied all the same, and the clique counts as keyed: an xref from it to another keyed
    clique was refused by the InChIKey guard, not left unexplained."""
    concords = [
        (unichem("CHEMBL.COMPOUND"), "CHEMBL.COMPOUND:CHEMBL1", KEY_A),
        (unichem("UNII"), "UNII:U1", KEY_A),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:2", KEY_B),
        (concord("DrugCentral"), "DrugCentral:1", "CHEMBL.COMPOUND:CHEMBL1"),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:2"),
    ]
    cliques = {
        "CHEMBL.COMPOUND:CHEMBL1": ("Drug", ["CHEMBL.COMPOUND:CHEMBL1", "UNII:U1", "DrugCentral:1"]),
        "PUBCHEM.COMPOUND:2": ("SmallMolecule", ["PUBCHEM.COMPOUND:2", KEY_B]),
    }
    rows = {(b, s, o): (v, kd) for b, s, o, v, kd in classify_rows(write_build(tmp_path, concords, cliques))}

    assert rows[("UNICHEM_CHEMBL.COMPOUND", "CHEMBL.COMPOUND:CHEMBL1", KEY_A)] == (APPLIED, True)
    assert rows[("UNICHEM_UNII", "UNII:U1", KEY_A)] == (APPLIED, True)
    assert rows[("UNICHEM_PUBCHEM.COMPOUND", "PUBCHEM.COMPOUND:2", KEY_B)] == (APPLIED, False)
    assert rows[("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:2")] == (REFUSED_INCHIKEY, False)


@pytest.mark.unit
def test_a_key_missing_from_a_small_molecule_clique_is_not_inferred(tmp_path):
    """SmallMolecule registers INCHIKEY, so a record there whose UniChem key is in no output did not keep it (glom()
    refused the pair). The clique is not keyed, so an xref from it to a keyed clique has no explanation and raises,
    rather than being passed off as an InChIKey refusal."""
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:5", KEY_C),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:6", KEY_B),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:5"),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:6"),
    ]
    cliques = {
        "PUBCHEM.COMPOUND:5": ("SmallMolecule", ["PUBCHEM.COMPOUND:5", "DrugCentral:1"]),
        "PUBCHEM.COMPOUND:6": ("SmallMolecule", ["PUBCHEM.COMPOUND:6", KEY_B]),
    }
    with pytest.raises(RuntimeError, match="no filter or InChIKey refusal"):
        classify(write_build(tmp_path, concords, cliques))


@pytest.mark.unit
def test_a_drug_output_holding_an_inchikey_raises(tmp_path):
    """If a Drug clique holds an InChIKey, Drug registers INCHIKEY after all and KEY_DROPPING_TYPES is out of date, so
    classification should raise rather than infer keys that were never dropped."""
    concords = [(unichem("CHEMBL.COMPOUND"), "CHEMBL.COMPOUND:CHEMBL1", KEY_A)]
    cliques = {"CHEMBL.COMPOUND:CHEMBL1": ("Drug", ["CHEMBL.COMPOUND:CHEMBL1", KEY_A])}
    with pytest.raises(RuntimeError, match="KEY_DROPPING_TYPES"):
        classify(write_build(tmp_path, concords, cliques))


@pytest.mark.unit
def test_a_drug_cliques_dropped_gtopdb_key_edge_is_applied(tmp_path):
    """GtoPdb's concord supplies record->key edges directly, outside UniChem. When that is the only key of a Drug
    clique, write_compendium() drops it all the same: the edge was applied and the clique counts as keyed, so its
    xref to another keyed clique was refused rather than left unexplained."""
    concords = [
        (concord("GTOPDB"), "GTOPDB:1", KEY_A),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:2", KEY_B),
        (concord("DrugCentral"), "DrugCentral:1", "GTOPDB:1"),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:2"),
    ]
    cliques = {
        "GTOPDB:1": ("Drug", ["GTOPDB:1", "DrugCentral:1"]),
        "PUBCHEM.COMPOUND:2": ("SmallMolecule", ["PUBCHEM.COMPOUND:2", KEY_B]),
    }
    rows = {(b, s, o): (v, kd) for b, s, o, v, kd in classify_rows(write_build(tmp_path, concords, cliques))}

    assert rows[("GTOPDB", "GTOPDB:1", KEY_A)] == (APPLIED, True)
    assert rows[("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:2")] == (REFUSED_INCHIKEY, False)


# STRUCTURE CONCORDS (GtoPdb, #1206)


@pytest.mark.unit
def test_gtopdb_ligands_sharing_a_key_are_applied_once_gtopdb_is_a_structure_concord(tmp_path):
    """Since #1206 combine_unichem() gloms GtoPdb's concord unfiltered, so two ligands given one key (a radiolabelled
    ligand and its compound) were both applied, not dropped as an overused xref. A build has no UNICHEM_GTOPDB then."""
    concords = [(concord("GTOPDB"), "GTOPDB:1204", KEY_A), (concord("GTOPDB"), "GTOPDB:1247", KEY_A)]
    cliques = {"GTOPDB:1204": ("SmallMolecule", ["GTOPDB:1204", "GTOPDB:1247", KEY_A])}

    verdicts = classify(write_build(tmp_path, concords, cliques))

    assert verdicts[("GTOPDB", "GTOPDB:1204", KEY_A)] == APPLIED
    assert verdicts[("GTOPDB", "GTOPDB:1247", KEY_A)] == APPLIED


@pytest.mark.unit
def test_gtopdb_ligands_sharing_a_key_are_overused_in_a_build_that_still_has_unichems_copy(tmp_path):
    """A build with UNICHEM_GTOPDB predates #1206: GtoPdb's concord was read only by build_untyped_compendia(),
    whose overused filter dropped both ligands' edges to their shared key (UniChem's rows put them together)."""
    concords = [
        (concord("GTOPDB"), "GTOPDB:1204", KEY_A),
        (concord("GTOPDB"), "GTOPDB:1247", KEY_A),
        (unichem("GTOPDB"), "GTOPDB:1204", KEY_A),
        (unichem("GTOPDB"), "GTOPDB:1247", KEY_A),
    ]
    cliques = {"GTOPDB:1204": ("SmallMolecule", ["GTOPDB:1204", "GTOPDB:1247", KEY_A])}

    verdicts = classify(write_build(tmp_path, concords, cliques))

    assert verdicts[("GTOPDB", "GTOPDB:1204", KEY_A)] == FILTERED_OVERUSED
    assert verdicts[("UNICHEM_GTOPDB", "GTOPDB:1204", KEY_A)] == APPLIED


# OVERUSE BEFORE OUTPUT MEMBERSHIP


@pytest.mark.unit
def test_a_key_lost_to_the_overused_filter_is_reported_as_overused(tmp_path):
    """Two UNII records claiming one key lose both links to remove_overused_xrefs(), and the key is then written to
    no output. The filter is why the endpoint is absent, so both rows should be reported as overused."""
    concords = [
        (unichem("UNII"), "UNII:U1", KEY_A),
        (unichem("UNII"), "UNII:U2", KEY_A),
    ]
    cliques = {"UNII:U1": ("ChemicalEntity", ["UNII:U1"]), "UNII:U2": ("ChemicalEntity", ["UNII:U2"])}
    verdicts = classify(write_build(tmp_path, concords, cliques))

    assert verdicts[("UNICHEM_UNII", "UNII:U1", KEY_A)] == FILTERED_OVERUSED
    assert verdicts[("UNICHEM_UNII", "UNII:U2", KEY_A)] == FILTERED_OVERUSED


# #83 SPLITS WITHOUT A KEY EDGE


@pytest.mark.unit
def test_a_split_off_mixture_with_no_key_edge_is_rejoined_through_its_xref(tmp_path):
    """create_typed_sets() moves every MolecularMixture-typed member, including a CID that joined only through a ChEBI
    xref and has no UniChem row. With no key edge to find the parent by, the xref to the keyed SmallMolecule half
    should rejoin it, so the edge is applied rather than an unexplained crossing."""
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:3", KEY_C),
        (concord("CHEBI"), "CHEBI:3", "PUBCHEM.COMPOUND:3"),
        (concord("CHEBI"), "CHEBI:3", "PUBCHEM.COMPOUND:30"),
    ]
    cliques = {
        "PUBCHEM.COMPOUND:3": ("SmallMolecule", ["PUBCHEM.COMPOUND:3", KEY_C, "CHEBI:3"]),
        "PUBCHEM.COMPOUND:30": ("MolecularMixture", ["PUBCHEM.COMPOUND:30"]),
    }
    verdicts = classify(write_build(tmp_path, concords, cliques))

    assert verdicts[("CHEBI", "CHEBI:3", "PUBCHEM.COMPOUND:30")] == APPLIED


@pytest.mark.unit
def test_a_split_off_mixtures_key_edge_outranks_a_refused_xref(tmp_path):
    """A split-off CID whose UniChem key names its parent may also carry an xref the guard refused into a second keyed
    clique. The key edge should decide the parent, and the xref should stay a refusal rather than make the pre-split
    set look ambiguous."""
    concords = [
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:3", KEY_C),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:30", KEY_C),
        (unichem("PUBCHEM.COMPOUND"), "PUBCHEM.COMPOUND:4", KEY_B),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:30"),
        (concord("DrugCentral"), "DrugCentral:1", "PUBCHEM.COMPOUND:4"),
    ]
    cliques = {
        "PUBCHEM.COMPOUND:3": ("SmallMolecule", ["PUBCHEM.COMPOUND:3", KEY_C]),
        "PUBCHEM.COMPOUND:30": ("MolecularMixture", ["PUBCHEM.COMPOUND:30", "DrugCentral:1"]),
        "PUBCHEM.COMPOUND:4": ("SmallMolecule", ["PUBCHEM.COMPOUND:4", KEY_B]),
    }
    verdicts = classify(write_build(tmp_path, concords, cliques))

    assert verdicts[("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:30")] == APPLIED
    assert verdicts[("DrugCentral", "DrugCentral:1", "PUBCHEM.COMPOUND:4")] == REFUSED_INCHIKEY
