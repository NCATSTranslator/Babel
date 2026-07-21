"""Unit tests for src.createcompendia.chemicals.

Covers write_unichem_concords()'s handling of UniChem compound IDs that already embed their source
prefix (e.g. the CHEBI source stores "CHEBI:12345" rather than a bare "12345"), which previously
produced invalid "CHEBI:CHEBI:12345" CURIEs across the chemical compendia; and make_chebi_relations()'s
reading of the ChEBI SDF, whose tags ChEBI renames between releases.
"""

import gzip
import json
from pathlib import Path

import pytest

from src import categories
from src.categories import (
    CHEMICAL_ENTITY,
    CHEMICAL_MIXTURE,
    COMPLEX_MOLECULAR_MIXTURE,
    DRUG,
    FOOD,
    MOLECULAR_MIXTURE,
    POLYPEPTIDE,
    SMALL_MOLECULE,
)
from src.createcompendia.chemicals import create_typed_sets, make_chebi_relations, write_unichem_concords
from src.datahandlers.unichem import UNICHEM_REFERENCE_TSV_HEADER, UNICHEM_STRUCT_TSV_HEADER
from src.datahandlers.unichem import data_sources as unichem_data_sources
from src.predicates import HAS_ALTERNATIVE_ID
from src.prefixes import CHEBI, KEGGCOMPOUND, PUBCHEMCOMPOUND
from src.util import get_config

# Derive CHEBI's UniChem source ID from the authoritative dict rather than hardcoding it.
CHEBI_SRC_ID = next(k for k, v in unichem_data_sources.items() if v == CHEBI)


def _bare_rows_for_other_sources():
    """One bare-ID row per non-CHEBI source.

    write_unichem_concords() raises if any configured source produces no entries,
    so a focused test still has to feed every source at least one row.
    """
    return [("1", src_id, "100") for src_id in unichem_data_sources if src_id != CHEBI_SRC_ID]


def _write_struct(path):
    """Write a minimal gzipped UniChem structure file with one UCI→InChIKey row."""
    with gzip.open(path, "wt") as out:
        out.write(UNICHEM_STRUCT_TSV_HEADER)
        out.write("1\tInChI=1S/H2O/h1H2\tXLYOFNOQVPJJNP-UHFFFAOYSA-N\n")


def _write_ref(path, rows):
    """Write a UniChem reference file; rows are (uci, src_id, compound_id) tuples (assignment is always '1')."""
    with open(path, "w") as out:
        out.write(UNICHEM_REFERENCE_TSV_HEADER)
        for uci, src_id, compound_id in rows:
            out.write(f"{uci}\t{src_id}\t{compound_id}\t1\n")


@pytest.mark.unit
def test_write_unichem_concords_strips_embedded_chebi_prefix(tmp_path):
    """A CHEBI compound ID stored as 'CHEBI:12345' must yield CHEBI:12345, not CHEBI:CHEBI:12345."""
    struct = tmp_path / "structure.tsv.gz"
    ref = tmp_path / "reference.tsv"
    _write_struct(struct)
    _write_ref(ref, [("1", CHEBI_SRC_ID, "CHEBI:12345"), *_bare_rows_for_other_sources()])

    write_unichem_concords(str(struct), str(ref), str(tmp_path))

    content = (tmp_path / f"UNICHEM_{CHEBI}").read_text()
    assert "CHEBI:12345\t" in content
    assert "CHEBI:CHEBI" not in content


@pytest.mark.unit
def test_write_unichem_concords_raises_on_unexpected_embedded_prefix(tmp_path):
    """A CHEBI row carrying a foreign embedded prefix is a format change worth a loud failure."""
    struct = tmp_path / "structure.tsv.gz"
    ref = tmp_path / "reference.tsv"
    _write_struct(struct)
    _write_ref(ref, [("1", CHEBI_SRC_ID, "FOO:9")])

    with pytest.raises(ValueError, match="unexpected embedded prefix"):
        write_unichem_concords(str(struct), str(ref), str(tmp_path))


@pytest.mark.unit
def test_write_unichem_concords_raises_when_source_produces_no_entries(tmp_path):
    """Any configured source that contributes zero rows should raise RuntimeError."""
    struct = tmp_path / "structure.tsv.gz"
    ref = tmp_path / "reference.tsv"
    _write_struct(struct)
    # Feed rows for every source except CHEBI — CHEBI should trigger the empty-source guard.
    rows = [("1", src_id, "100") for src_id in unichem_data_sources if src_id != CHEBI_SRC_ID]
    _write_ref(ref, rows)

    with pytest.raises(RuntimeError, match="no entries for the following sources"):
        write_unichem_concords(str(struct), str(ref), str(tmp_path))


# ----
# FOOD-AND-EXTRACT TYPE VOTE (issues #828, #935)
# ----


@pytest.mark.unit
def test_create_typed_sets_types_a_structureless_food_clique_as_food():
    """A clique whose only evidence is a DRUGBANK food CURIE, and whose members are all
    biolink:ChemicalEntity, should be typed biolink:Food and keep every member (incl. RXCUI).
    This is the #828/#918 behaviour that must survive the change to a vote."""
    trout = frozenset({"DRUGBANK:DB10626", "UMLS:C2725895", "RXCUI:882482"})
    # ChemicalEntity is what these cliques vote today; Food outranks it, so the evidence wins.
    types = {"UMLS:C2725895": CHEMICAL_ENTITY}

    typed = create_typed_sets({trout}, types, food_types={"DRUGBANK:DB10626": FOOD})

    assert trout in typed[FOOD]
    assert all(trout not in sets for t, sets in typed.items() if t != FOOD)


@pytest.mark.unit
def test_create_typed_sets_does_not_demote_a_small_molecule_to_food():
    """Food evidence must NOT retype a clique that votes for a structure-bearing type (issue #935).

    This is the D-glucose clique from the babel-1.18 build, which the old clique-level override
    typed biolink:Food. DRUGBANK:DB09341 "Dextrose, unspecified form" is a structureless DrugBank
    food row that gloms into the real D-glucose clique via its UMLS/RxNorm concords; the clique
    votes SmallMolecule, which outranks Food, so it must stay a SmallMolecule -- with the food
    CURIE still a member.
    """
    glucose = frozenset(
        {
            "CHEBI:17234",
            "PUBCHEM.COMPOUND:107526",
            "DRUGBANK:DB01914",
            "DRUGBANK:DB09341",
            "MESH:D005947",
            "UMLS:C0017725",
            "RXCUI:4850",
        }
    )
    types = {
        "PUBCHEM.COMPOUND:107526": SMALL_MOLECULE,
        "CHEBI:17234": CHEMICAL_ENTITY,
        "DRUGBANK:DB01914": CHEMICAL_ENTITY,
        "MESH:D005947": CHEMICAL_ENTITY,
    }

    typed = create_typed_sets({glucose}, types, food_types={"DRUGBANK:DB09341": FOOD})

    assert glucose in typed[SMALL_MOLECULE]
    assert glucose not in typed[FOOD]


@pytest.mark.unit
def test_create_typed_sets_types_an_extract_as_a_complex_molecular_mixture():
    """A DRUGBANK allergen extract with ComplexMolecularMixture evidence lands there, not in Food:
    ComplexMolecularMixture outranks Food, so an extract stays an extract."""
    pollen = frozenset({"DRUGBANK:DB10351", "UMLS:C2684343"})

    typed = create_typed_sets({pollen}, {}, food_types={"DRUGBANK:DB10351": COMPLEX_MOLECULAR_MIXTURE})

    assert pollen in typed[COMPLEX_MOLECULAR_MIXTURE]
    assert pollen not in typed[FOOD]


@pytest.mark.unit
def test_a_split_cliques_halves_vote_on_their_own_food_evidence():
    """When a clique is split into a MolecularMixture and a SmallMolecule half (issue #83), each half
    must be typed by the evidence *it* holds, not by the whole pre-split clique's.

    ComplexMolecularMixture outranks MolecularMixture (but not SmallMolecule), so an extract CURIE
    that lands in the small molecule half — where it correctly loses the vote — would otherwise
    still retype the *mixture* half it isn't even a member of.
    """
    clique = frozenset({"PUBCHEM.COMPOUND:962", "PUBCHEM.COMPOUND:22247451", "DRUGBANK:DB10351"})
    types = {
        "PUBCHEM.COMPOUND:962": SMALL_MOLECULE,
        "PUBCHEM.COMPOUND:22247451": MOLECULAR_MIXTURE,
    }

    typed = create_typed_sets({clique}, types, food_types={"DRUGBANK:DB10351": COMPLEX_MOLECULAR_MIXTURE})

    # The extract CURIE is in the small-molecule half, so the mixture half never sees the evidence.
    assert frozenset({"PUBCHEM.COMPOUND:22247451"}) in typed[MOLECULAR_MIXTURE]
    # ...and in its own half SmallMolecule outranks it, so it loses there too.
    assert frozenset({"PUBCHEM.COMPOUND:962", "DRUGBANK:DB10351"}) in typed[SMALL_MOLECULE]
    assert not typed[COMPLEX_MOLECULAR_MIXTURE]


@pytest.mark.unit
def test_food_evidence_beats_a_drug_vote():
    """PINS KNOWN-IMPERFECT BEHAVIOUR (issue #935). chemical_type_order ranks biolink:Drug last, below
    biolink:Food, so a clique that votes Drug and also carries food evidence is typed Food. That is
    mildly wrong -- a drug formulation is not a food -- but it is accepted rather than special-cased:
    it does not occur in any build so far (no clique carrying food evidence holds a Drug member), and
    Drug is last for good reason (see config.yaml: chemical_type_order).

    INVERT this assertion, don't delete it, if the tradeoff is ever revisited -- i.e. if Food starts
    appearing where a drug formulation belongs and Drug is promoted above Food.
    """
    formulation = frozenset({"DRUGBANK:DB09341", "RXCUI:4850"})
    types = {"RXCUI:4850": DRUG}

    typed = create_typed_sets({formulation}, types, food_types={"DRUGBANK:DB09341": FOOD})

    assert formulation in typed[FOOD]
    assert formulation not in typed[DRUG]


@pytest.mark.unit
def test_chemical_type_order_is_well_formed():
    """Every entry in config.yaml's chemical_type_order should be a known src/categories.py constant,
    with no duplicates. create_typed_sets() calls order.index() on every type it sees, so a typo or a
    missing entry is a ValueError tens of millions of cliques into a build."""
    order = get_config()["chemical_type_order"]
    known = {value for name, value in vars(categories).items() if name.isupper() and isinstance(value, str)}

    assert len(order) == len(set(order)), "chemical_type_order contains duplicates"
    assert set(order) <= known, f"unknown Biolink types in chemical_type_order: {set(order) - known}"


@pytest.mark.unit
def test_chemical_type_order_ranks_food_below_structure_bearing_types():
    """Food must rank below every structure-bearing type and above ChemicalEntity (issue #935).

    This is the property that keeps food evidence from demoting a defined molecule, and it is what
    the babel-1.18 D-glucose bug came down to. ComplexMolecularMixture must also outrank Food so an
    extract stays an extract when NCIt also calls the concept a food, and ChemicalMixture likewise:
    a mixture asserts a composition that a whole food does not."""
    order = get_config()["chemical_type_order"]

    for structural in (
        SMALL_MOLECULE,
        MOLECULAR_MIXTURE,
        POLYPEPTIDE,
        COMPLEX_MOLECULAR_MIXTURE,
        CHEMICAL_MIXTURE,
    ):
        assert order.index(structural) < order.index(FOOD), f"{structural} must outrank {FOOD}"
    assert order.index(FOOD) < order.index(CHEMICAL_ENTITY), f"{FOOD} must outrank {CHEMICAL_ENTITY}"


@pytest.mark.unit
def test_create_typed_sets_leaves_a_clique_without_food_evidence_untouched():
    """A clique holding none of the food/extract CURIEs should keep its normal voted type
    (no food_types leakage across cliques)."""
    normal = frozenset({"CHEBI:15377", "PUBCHEM.COMPOUND:962"})
    types = {"CHEBI:15377": SMALL_MOLECULE, "PUBCHEM.COMPOUND:962": SMALL_MOLECULE}

    typed = create_typed_sets({normal}, types, food_types={"DRUGBANK:DB10626": FOOD})

    assert normal in typed[SMALL_MOLECULE]
    assert normal not in typed[FOOD]


# MAKE_CHEBI_RELATIONS / CHEBI SDF TAG NAMES

# tests/data/chebi_abacavir.sdf is the CHEBI:421707 "abacavir" entry copied verbatim out of
# babel_downloads/CHEBI/ChEBI_complete.sdf as downloaded for babel-1.18. It is the single record
# that motivated this fix, and it happens to carry every tag make_chebi_relations() reads, so one
# entry exercises all of CHEBI_SDF_KEYS. Re-derive it by extracting the chunk whose "> <ChEBI ID>"
# tag holds CHEBI:421707.
ABACAVIR_SDF = Path(__file__).parent.parent / "data" / "chebi_abacavir.sdf"

# The empty database_accession.tsv that make_chebi_relations() also takes: header only, so these
# tests measure the SDF half alone.
DBX_HEADER = "ID\tCOMPOUND_ID\tSOURCE\tTYPE\tACCESSION_NUMBER\n"


def _run_make_chebi_relations(tmp_path, sdf=ABACAVIR_SDF, dbx_contents=DBX_HEADER):
    """Run make_chebi_relations() over a fixture SDF, returning (concord lines, Property dicts)."""
    dbx = tmp_path / "database_accession.tsv"
    dbx.write_text(dbx_contents)
    concord = tmp_path / "CHEBI"
    propfile = tmp_path / "props.jsonl.gz"

    make_chebi_relations(
        str(sdf), str(dbx), str(concord), propfile_gz=str(propfile), metadata_yaml=str(tmp_path / "metadata.yaml")
    )

    with gzip.open(propfile, "rt") as inf:
        props = [json.loads(line) for line in inf]
    return concord.read_text().splitlines(), props


@pytest.mark.unit
def test_make_chebi_relations_emits_secondary_chebi_ids(tmp_path):
    """Every ID in a SECONDARY_ID tag should become a hasAlternativeId property on the primary CURIE.

    ChEBI packs them semicolon-delimited onto one line, so a parser that treats the line as a single
    value emits one nonsense CURIE instead of five real ones. CHEBI:520984 is the secondary ID that
    stopped normalizing in babel-1.18 when this ingest broke.
    """
    _, props = _run_make_chebi_relations(tmp_path)

    secondary_ids = {p["value"] for p in props if p["predicate"] == HAS_ALTERNATIVE_ID}
    assert secondary_ids == {"CHEBI:193608", "CHEBI:441792", "CHEBI:2360", "CHEBI:525912", "CHEBI:520984"}
    assert {p["curie"] for p in props} == {"CHEBI:421707"}


@pytest.mark.unit
def test_make_chebi_relations_emits_kegg_and_pubchem_xrefs(tmp_path):
    """The SDF's KEGG COMPOUND and PubChem *Compound* links should both become concord xrefs.

    PubChem is the regression-prone one: ChEBI split a single "PubChem Database Links" tag into
    separate Compound and Substance tags, and only the Compound side belongs in the concord.
    """
    concord_lines, _ = _run_make_chebi_relations(tmp_path)

    assert f"CHEBI:421707\txref\t{KEGGCOMPOUND}:C07624" in concord_lines
    assert f"CHEBI:421707\txref\t{PUBCHEMCOMPOUND}:441300" in concord_lines
    # 85612588 is this entry's "PubChem Substance Database Links" value; a substance ID must never be
    # picked up as a compound.
    assert not any(f"{PUBCHEMCOMPOUND}:85612588" in line for line in concord_lines)


@pytest.mark.unit
def test_make_chebi_relations_splits_multivalue_tags(tmp_path):
    """A semicolon-delimited tag value should never survive into a CURIE.

    Before the fix, a multi-value KEGG line produced "KEGG.COMPOUND:C00001;C00002", which matches
    nothing downstream and was invisible because it still looked like a populated concord.
    """
    concord_lines, props = _run_make_chebi_relations(tmp_path)

    assert not any(";" in line for line in concord_lines)
    assert not any(";" in p["value"] for p in props)


@pytest.mark.unit
def test_make_chebi_relations_raises_when_chebi_renames_a_tag(tmp_path):
    """A renamed SDF tag should fail the build, naming the tag, rather than silently emitting nothing.

    This is the check that babel-1.18 lacked: `Secondary ChEBI ID` became `SECONDARY_ID`, every
    secondary identifier vanished from the release, and nothing complained.
    """
    renamed = tmp_path / "renamed.sdf"
    renamed.write_text(ABACAVIR_SDF.read_text().replace("> <SECONDARY_ID>", "> <Secondary ChEBI ID>"))

    with pytest.raises(ValueError, match="secondary_id"):
        _run_make_chebi_relations(tmp_path, sdf=renamed)


@pytest.mark.unit
def test_make_chebi_relations_raises_when_an_output_would_be_empty(tmp_path):
    """An SDF carrying every expected tag but yielding no secondary IDs should still fail.

    The tag-name check can't catch a value-format change, a truncated download, or any other reason
    the ingest goes quiet, so the counts are checked independently before the outputs are accepted.
    """
    emptied = tmp_path / "emptied.sdf"
    emptied.write_text(
        ABACAVIR_SDF.read_text().replace("CHEBI:193608;CHEBI:441792;CHEBI:2360;CHEBI:525912;CHEBI:520984", " ")
    )

    with pytest.raises(ValueError, match="No CHEBI secondary IDs"):
        _run_make_chebi_relations(tmp_path, sdf=emptied)
