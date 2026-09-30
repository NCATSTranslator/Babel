"""Unit tests for src/datahandlers/umls.py: the "a CUI follows its MeSH descriptor" rule that keeps a UMLS CUI,
its MeSH descriptor and its DrugBank partners in one pipeline's ids (issues #276, #308, #1123).

The MRSTY and MRCONSO rows are copied verbatim from UMLS 2026AA; each block names its CUI.
"""

import pytest

from src.categories import ANATOMICAL_ENTITY, CHEMICAL_ENTITY, ORGANISM_TAXON, PROTEIN
from src.createcompendia import gene, processactivitypathway
from src.datahandlers import umls

# C0242726 "Plant Roots": T002 Plant (taxon), descriptor D018517 in anatomy's A18 tree (#1123).
# C0000608 "Aminocaproic Acid": T116 (protein) + T121, descriptor D015119 in a chemical D-tree (#308).
# C0000005 "(131)I-Macroaggregated Albumin": T116, but its only MSH atoms are PEP/ET, so build_sets() never
#   concords it to D012711 and MeSH ownership must leave it alone.
MRSTY = (
    "C0242726|T002|A1.1.3.3|Plant|AT17675273||\n"
    "C0000608|T116|A1.4.1.2.1.7|Amino Acid, Peptide, or Protein|AT17641842|4096|\n"
    "C0000608|T121|A1.4.1.1.1|Pharmacologic Substance|AT17567390|4096|\n"
    "C0000005|T116|A1.4.1.2.1.7|Amino Acid, Peptide, or Protein|AT17648347||\n"
    "C0000005|T121|A1.4.1.1.1|Pharmacologic Substance|AT17575038||\n"
    "C0000005|T130|A1.4.1.1.4|Indicator, Reagent, or Diagnostic Aid|AT17634323||\n"
)

MRCONSO = (
    # C0242726: a Czech MH atom (must be ignored: not ENG), the English MH atom, and ET/PM atoms.
    "C0242726|CZE|P|L11818128|PF|S14691612|Y|A24275078||M0027763|D018517|MSHCZE|MH|D018517|kořeny rostlin|3|N||\n"
    "C0242726|ENG|P|L0315401|PF|S0396396|N|A0447154||M0027763|D018517|MSH|MH|D018517|Plant Roots|0|N||\n"
    "C0242726|ENG|P|L0315401|VO|S0396393|Y|A26677612||M0027763|D018517|MSH|ET|D018517|Plant Root|0|N||\n"
    "C0242726|ENG|P|L0315401|VW|S11094902|Y|A16992050||M0027763|D018517|MSH|PM|D018517|Roots, Plant|0|N||\n"
    # C0000608: the MH atom among PM/ET atoms.
    "C0000608|ENG|P|L0000608|VC|S0008731|Y|A0017463||M0023260|D015119|MSH|PM|D015119|6 Aminocaproic Acid|0|N||\n"
    "C0000608|ENG|S|L0002546|VC|S0013139|Y|A22790800||M0023260|D015119|MSH|MH|D015119|Aminocaproic Acid|0|N||\n"
    "C0000608|ENG|S|L0014638|PF|S0038520|Y|A26677291||M0023260|D015119|MSH|ET|D015119|epsilon-Aminocaproic Acid|0|N||\n"
    # C0000005: PEP and ET atoms only.
    "C0000005|ENG|P|L0000005|PF|S0007492|Y|A26634265||M0019694|D012711|MSH|PEP|D012711|(131)I-Macroaggregated Albumin|0|N||\n"
    "C0000005|ENG|S|L0270109|PF|S0007491|Y|A26634266||M0019694|D012711|MSH|ET|D012711|(131)I-MAA|0|N||\n"
)

# Semantic-type maps in the shape the pipelines use (subsets of taxon/anatomy/protein/chemicals.write_umls_ids).
TAXON_MAP = {"A1.1.3.3": ORGANISM_TAXON}
ANATOMY_MAP = {"A1.2": ANATOMICAL_ENTITY}
PROTEIN_MAP = {"A1.4.1.2.1.7": PROTEIN}
CHEMICAL_MAP = {"A1.4.1.1.1.1": CHEMICAL_ENTITY, "A1.4.1.2.1": CHEMICAL_ENTITY}
PROTEIN_STY_TREES = {"A1.4.1.2.1.7"}


@pytest.fixture
def rrf(tmp_path):
    (tmp_path / "MRSTY.RRF").write_text(MRSTY)
    (tmp_path / "MRCONSO.RRF").write_text(MRCONSO)
    return tmp_path


def mesh_ids(tmp_path, name, rows):
    """Write an ids/MESH-style file (CURIE<tab>type per row) and return its path."""
    path = tmp_path / f"MESH_{name}"
    path.write_text("".join(f"{curie}\t{biolink_type}\n" for curie, biolink_type in rows))
    return str(path)


def read_ids(path):
    return dict(line.rstrip("\n").split("\t") for line in open(path) if line.strip())


def run(rrf, category_map, own, foreign, **kwargs):
    out = rrf / "UMLS"
    umls.write_umls_ids(
        str(rrf / "MRSTY.RRF"),
        category_map,
        str(out),
        mrconso=str(rrf / "MRCONSO.RRF"),
        own_mesh_ids_files=own,
        foreign_mesh_ids_files=foreign,
        **kwargs,
    )
    return read_ids(out)


# READING MRCONSO


@pytest.mark.unit
def test_read_cui_to_mesh_descriptors_uses_concord_atoms_only(rrf):
    """Only English MH/NM/HT/QAB atoms should map a CUI to a descriptor, so C0000005 (PEP/ET only) is absent and
    the Czech MH atom for C0242726 is ignored."""
    assert umls.read_cui_to_mesh_descriptors(str(rrf / "MRCONSO.RRF")) == {
        "UMLS:C0242726": {"MESH:D018517"},
        "UMLS:C0000608": {"MESH:D015119"},
    }


@pytest.mark.unit
def test_read_cui_to_mesh_descriptors_skips_suppressed_atoms(tmp_path):
    """An obsolete (SUPPRESS=O) MH atom should not map its CUI, just as check_mrconso_line() drops it for build_sets()."""
    row = "C0242726|ENG|P|L0315401|PF|S0396396|N|A0447154||M0027763|D018517|MSH|MH|D018517|Plant Roots|0|O||\n"
    (tmp_path / "MRCONSO.RRF").write_text(row)
    assert umls.read_cui_to_mesh_descriptors(str(tmp_path / "MRCONSO.RRF")) == {}


@pytest.mark.unit
def test_build_sets_shares_the_concord_term_types():
    """build_sets() and read_cui_to_mesh_descriptors() must agree on which MeSH atoms count, or a CUI could be
    re-homed for a descriptor it is never concorded to (or vice versa)."""
    assert umls.MESH_CONCORD_TTYS == frozenset({"MH", "NM", "HT", "QAB"})


# MESH OWNERSHIP


@pytest.mark.unit
def test_cui_dropped_when_only_another_pipeline_claims_its_descriptor(rrf, tmp_path):
    """Taxon selects C0242726 by T002, but D018517 is only in anatomy's MeSH ids, so taxon should not claim it."""
    own = [mesh_ids(tmp_path, "taxon", [])]
    foreign = [mesh_ids(tmp_path, "anatomy", [("MESH:D018517", ANATOMICAL_ENTITY)])]
    assert run(rrf, TAXON_MAP, own, foreign) == {}


@pytest.mark.unit
def test_cui_added_to_the_pipeline_that_claims_its_descriptor(rrf, tmp_path):
    """Anatomy's semantic types never select a T002 CUI, but it claims D018517, so it should claim C0242726
    typed as that descriptor."""
    own = [mesh_ids(tmp_path, "anatomy", [("MESH:D018517", ANATOMICAL_ENTITY)])]
    foreign = [mesh_ids(tmp_path, "taxon", [])]
    assert run(rrf, ANATOMY_MAP, own, foreign) == {"UMLS:C0242726": ANATOMICAL_ENTITY}


@pytest.mark.unit
def test_cui_kept_when_both_pipelines_claim_its_descriptor(rrf, tmp_path):
    """A descriptor cross-listed in both pipelines' MeSH ids decides nothing: the semantic types stand, so
    taxon keeps C0242726 and anatomy does not add it (that would recreate the duplicate)."""
    taxon_mesh = mesh_ids(tmp_path, "taxon", [("MESH:D018517", ORGANISM_TAXON)])
    anatomy_mesh = mesh_ids(tmp_path, "anatomy", [("MESH:D018517", ANATOMICAL_ENTITY)])
    assert run(rrf, TAXON_MAP, [taxon_mesh], [anatomy_mesh]) == {"UMLS:C0242726": ORGANISM_TAXON}
    assert run(rrf, ANATOMY_MAP, [anatomy_mesh], [taxon_mesh]) == {}


@pytest.mark.unit
def test_cui_kept_when_nobody_claims_its_descriptor(rrf, tmp_path):
    """A descriptor in a tree no pipeline ingests leaves the CUI where its semantic types put it."""
    assert run(rrf, TAXON_MAP, [mesh_ids(tmp_path, "taxon", [])], [mesh_ids(tmp_path, "anatomy", [])]) == {
        "UMLS:C0242726": ORGANISM_TAXON
    }


@pytest.mark.unit
def test_t116_cui_with_chemical_descriptor_moves_from_protein_to_chemicals(rrf, tmp_path):
    """C0000608 is T116 so protein selects it and chemicals' blocklist removes it; because D015119 is a chemical
    descriptor, protein should drop it and chemicals should re-admit it typed ChemicalEntity (#308)."""
    protein_mesh = mesh_ids(tmp_path, "protein", [])
    chemicals_mesh = mesh_ids(tmp_path, "chemicals", [("MESH:D015119", CHEMICAL_ENTITY)])
    assert run(rrf, PROTEIN_MAP, [protein_mesh], [chemicals_mesh]) == {"UMLS:C0000005": PROTEIN}
    assert run(
        rrf, CHEMICAL_MAP, [chemicals_mesh], [protein_mesh], blocklist_umls_semantic_type_tree=PROTEIN_STY_TREES
    ) == {"UMLS:C0000608": CHEMICAL_ENTITY}


@pytest.mark.unit
def test_cui_with_entry_term_atoms_only_is_untouched(rrf, tmp_path):
    """C0000005 maps to D012711 only through PEP/ET atoms, which build_sets() ignores, so even a chemical claim on
    D012711 should neither drop it from protein nor add it to chemicals."""
    protein_mesh = mesh_ids(tmp_path, "protein", [])
    chemicals_mesh = mesh_ids(tmp_path, "chemicals", [("MESH:D012711", CHEMICAL_ENTITY)])
    assert "UMLS:C0000005" in run(rrf, PROTEIN_MAP, [protein_mesh], [chemicals_mesh])
    assert "UMLS:C0000005" not in run(
        rrf, CHEMICAL_MAP, [chemicals_mesh], [protein_mesh], blocklist_umls_semantic_type_tree=PROTEIN_STY_TREES
    )


@pytest.mark.unit
def test_blocklisted_cui_is_never_added(rrf, tmp_path):
    """A CUI on the pipeline's explicit blocklist (disease's badumls) should stay out even if its descriptor is owned."""
    own = [mesh_ids(tmp_path, "anatomy", [("MESH:D018517", ANATOMICAL_ENTITY)])]
    assert run(rrf, ANATOMY_MAP, own, [], blocklist_umls_ids={"C0242726"}) == {}


@pytest.mark.unit
def test_mesh_ownership_arguments_are_all_or_none(rrf):
    """Passing only some of mrconso/own/foreign should raise rather than silently skip the rule."""
    with pytest.raises(ValueError):
        umls.write_umls_ids(str(rrf / "MRSTY.RRF"), TAXON_MAP, str(rrf / "UMLS"), mrconso=str(rrf / "MRCONSO.RRF"))


@pytest.mark.unit
def test_without_mesh_arguments_semantic_types_alone_decide(rrf):
    """The rule is optional: the classic call writes exactly what the category map selects."""
    out = rrf / "UMLS"
    umls.write_umls_ids(str(rrf / "MRSTY.RRF"), PROTEIN_MAP, str(out))
    assert read_ids(out) == {"UMLS:C0000608": PROTEIN, "UMLS:C0000005": PROTEIN}


# DROP-ONLY PIPELINES (no ids/MESH of their own)

# C0004372 "Autolysis": T043 Cell Function, which the process pipeline selects, but its descriptor D001329 is in
# MeSH's C23 tree, which the disease pipeline claims.
PROCESS_MRSTY = "C0004372|T043|B2.2.1.1.3|Cell Function|AT265805073||\n"
PROCESS_MRCONSO = "C0004372|ENG|P|L0004372|PF|S0016981|Y|A0028052||M0001990|D001329|MSH|MH|D001329|Autolysis|0|N||\n"

# C1413234 "CD68 gene": T028 Gene or Genome, which the gene pipeline selects, but UMLS also gives it the MeSH
# descriptor D000097382, which the protein pipeline claims.
GENE_MRSTY = "C1413234|T028|A1.2.3.5|Gene or Genome|AT40051042||\n"
GENE_MRCONSO = (
    "C1413234|ENG|P|L5135306|PF|S5868440|N|A20787987||HGNC:1693||HGNC|MTH_ACR|HGNC:1693|CD68 gene|0|N||\n"
    "C1413234|ENG|S|L6387821|PF|S22528022|Y|A35665631||M000763930|D000097382|MSH|MH|D000097382|CD68 Molecule|0|N||\n"
)


@pytest.mark.unit
def test_process_drops_cui_whose_descriptor_a_mesh_owning_pipeline_claims(tmp_path):
    """The process pipeline writes no ids/MESH, so it can only drop: C0004372 should leave process when disease
    claims D001329, and stay when nobody does or when the rule is off."""
    (tmp_path / "MRSTY.RRF").write_text(PROCESS_MRSTY)
    (tmp_path / "MRCONSO.RRF").write_text(PROCESS_MRCONSO)
    out = tmp_path / "UMLS"
    mrsty, mrconso = str(tmp_path / "MRSTY.RRF"), str(tmp_path / "MRCONSO.RRF")
    claimed = mesh_ids(tmp_path, "disease", [("MESH:D001329", "biolink:PhenotypicFeature")])
    unclaimed = mesh_ids(tmp_path, "anatomy", [])

    processactivitypathway.write_umls_ids(mrsty, str(out), mrconso=mrconso, foreign_mesh_ids_files=[claimed])
    assert read_ids(out) == {}
    processactivitypathway.write_umls_ids(mrsty, str(out), mrconso=mrconso, foreign_mesh_ids_files=[unclaimed])
    assert read_ids(out) == {"UMLS:C0004372": "biolink:BiologicalProcess"}
    processactivitypathway.write_umls_ids(mrsty, str(out))
    assert read_ids(out) == {"UMLS:C0004372": "biolink:BiologicalProcess"}


@pytest.mark.unit
def test_gene_drops_cui_whose_descriptor_a_mesh_owning_pipeline_claims(tmp_path):
    """The gene pipeline has its own writer and no ids/MESH: C1413234 should leave gene when protein claims
    D000097382, and stay when the rule is off."""
    (tmp_path / "MRSTY.RRF").write_text(GENE_MRSTY)
    (tmp_path / "MRCONSO.RRF").write_text(GENE_MRCONSO)
    out = tmp_path / "UMLS"
    mrsty, mrconso = str(tmp_path / "MRSTY.RRF"), str(tmp_path / "MRCONSO.RRF")
    claimed = mesh_ids(tmp_path, "protein", [("MESH:D000097382", PROTEIN)])

    gene.write_umls_ids(mrconso, mrsty, str(out), foreign_mesh_ids_files=[claimed])
    assert read_ids(out) == {}
    gene.write_umls_ids(mrconso, mrsty, str(out))
    assert read_ids(out) == {"UMLS:C1413234": "biolink:Gene"}
