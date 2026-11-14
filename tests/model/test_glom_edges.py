"""Unit tests for src/model/glom_edges.py: reconstructing what glom() did with each chemical concord edge.

The builds here are synthetic: each is the smallest set of cliques and concord rows that exercises one path through
the classification (applied, InChIKey refusal, overused filter, the #83 split, CUI ownership) or one way the model
can fail to describe a build.
"""

import duckdb
import pytest

from src.createcompendia.chemicals import UNICHEM_OVERUSED_XREF_PREFIXES
from src.model.glom_edges import (
    APPLIED,
    ENDPOINT_ABSENT,
    FILTERED_OVERUSED,
    FILTERED_OWNED_ELSEWHERE,
    REFUSED_INCHIKEY,
    classify_chemical_glom_edges,
)
from src.util import get_config
from tests.model.chemical_build_fixture import concord, unichem, write_build

KEY_A = "INCHIKEY:AAAAAAAAAAAAAA-UHFFFAOYSA-N"
KEY_B = "INCHIKEY:BBBBBBBBBBBBBB-UHFFFAOYSA-N"
KEY_C = "INCHIKEY:CCCCCCCCCCCCCC-UHFFFAOYSA-N"


def classify(root, owned_elsewhere=(), bad_pairs=()):
    """Run classify_chemical_glom_edges over a fixture build; return {(base, subj, obj): verdict}."""
    con = duckdb.connect()
    types = [o.removesuffix(".txt") for o in get_config()["chemical_outputs"]]
    classify_chemical_glom_edges(
        con,
        f"{root}/duckdb/Concord.parquet",
        [f"{root}/duckdb/parquet/filename={t}/Edge.parquet" for t in types],
        get_config()["chemical_concords"],
        UNICHEM_OVERUSED_XREF_PREFIXES,
        owned_elsewhere,
        bad_pairs,
    )
    return {(b, s, o): v for b, s, o, v in con.sql("SELECT base, subj, obj, verdict FROM glom_edge").fetchall()}


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
    from src.model.glom_edges import FILTERED_BADXREF

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
