import re
from collections import Counter, defaultdict

import requests

import src.datahandlers.mesh as mesh
import src.datahandlers.obo as obo
import src.datahandlers.umls as umls
from src.babel_utils import (
    get_prefixes,
    read_badxrefs,
    remove_overused_xrefs,
    unique_prefixes_from_config,
)
from src.categories import ANATOMICAL_ENTITY, CELL, CELLULAR_COMPONENT, GROSS_ANATOMICAL_STRUCTURE
from src.metadata.provenance import write_concord_metadata
from src.model.cliques import glom_from_files
from src.model.compendia import write_typed_compendia
from src.prefixes import CL, EMAPA, FMA, GO, MESH, NCIT, PO, SNOMEDCT, UBERON, UMLS, WIKIDATA
from src.ubergraph import (
    ANNOTATION_EXACT_SYNONYM,
    ANNOTATION_LABEL,
    ANNOTATION_NCIT_FDA_UNII_CODE,
    ANNOTATION_NCIT_SEMANTIC_TYPE,
    HIERARCHY_PART_OF,
    UberGraph,
    build_sets,
)
from src.util import Text, get_logger, get_repo_root

logger = get_logger(__name__)

# Individually wrong xref pairs to drop, for cases where the target prefix is legitimate in general
# (MESH and GO really are anatomy xref targets) so ANATOMY_OBO_IGNORE_LIST cannot help. Unlike
# diseasephenotype's DEFAULT_BAD_XREFS this is a single file applied to every anatomy concord
# rather than a per-concord mapping: a pair names both of its CURIEs, so there is nothing for a
# per-concord key to disambiguate, and one file avoids the two-place-registration footgun described
# in docs/sources/AGENTS.md. See the file itself for why each pair is listed.
#
# Two consumers resolve this file: the real build, where the anatomy_compendia rule declares it as
# an input (so an edit re-triggers the rule) and passes the path in, and the source-impact report,
# which takes this default. The snakefile references this constant rather than repeating the
# literal, so there is one path and the report cannot drift from the build. Absolute, because the
# report CLI can be invoked from any directory.
ANATOMY_BAD_XREFS = str(get_repo_root() / "input_data/anatomy_badxrefs.txt")

# Which parts of each source ontology the anatomy pipeline takes, and as what Biolink type.
#
# "root" is the traversal root: the term whose descendants define the source's contribution, and
# the type every term below it gets by default. "subtype_roots" names the subtrees that override
# that default — UBERON's dedicated gross-anatomy branch, EMAPA's organ and tissue branches. A term
# at or below a subtype root takes the subtype's type; the subtype root itself is included.
# "exclude_roots" (optional) names subtrees left out altogether, each with the reason.
#
# This is meant to be the one place to look for "which parts of this ontology does anatomy take,
# and as what". MESH and UMLS are not here: they span many Biolink types and are keyed by tree
# number and semantic type rather than by a CURIE root, so they still carry their own maps in
# write_mesh_ids() and write_umls_ids(). Folding those in is the natural next step.
ANATOMY_OBO_SOURCES = {
    UBERON: {
        "root": f"{UBERON}:0001062",  # "anatomical entity"
        "type": ANATOMICAL_ENTITY,
        "subtype_roots": {f"{UBERON}:0010000": GROSS_ANATOMICAL_STRUCTURE},  # "anatomical structure"
    },
    CL: {"root": f"{CL}:0000000", "type": CELL, "subtype_roots": {}},  # "cell"
    GO: {"root": f"{GO}:0005575", "type": CELLULAR_COMPONENT, "subtype_roots": {}},  # "cellular_component"
    EMAPA: {
        "root": f"{EMAPA}:0",  # "anatomical structure"
        "type": ANATOMICAL_ENTITY,
        "subtype_roots": {
            f"{EMAPA}:35949": GROSS_ANATOMICAL_STRUCTURE,  # "organ"
            f"{EMAPA}:35868": GROSS_ANATOMICAL_STRUCTURE,  # "tissue"
        },
    },
    # The Plant Ontology's anatomy branch. Its other branch, PO:0009012 "plant structure development
    # stage", is not anatomy and is not taken. The default type is GrossAnatomicalStructure rather than
    # AnatomicalEntity because 1,311 of the root's 1,363 terms sit under PO:0009011 "plant structure"
    # (tissues, organs, whole plants), and because Biolink does not yet register PO for
    # AnatomicalEntity.
    PO: {
        "root": f"{PO}:0025131",  # "plant anatomical entity"
        "type": GROSS_ANATOMICAL_STRUCTURE,
        "subtype_roots": {f"{PO}:0009002": CELL},  # "plant cell"
        # Spaces and substances are neither gross structures nor cells, so their only correct type is
        # AnatomicalEntity, which Biolink does not register PO for: write_compendium() would drop
        # them. Left out until https://github.com/biolink/biolink-model/pull/1862 is in the Biolink
        # version config.yaml pins; then type them AnatomicalEntity through subtype_roots instead.
        "exclude_roots": [
            f"{PO}:0025117",  # "plant anatomical space" (35 terms)
            f"{PO}:0025161",  # "portion of plant substance" (16 terms)
        ],
    },
}

# Which NCIt terms are plant anatomy. NCIt files plant parts under "Plant Part", a branch of
# "Plant-based Natural Product" that holds FDA's vocabulary for naming the part of a plant a botanical
# drug is made from. It mixes 576 terms of two kinds: structures ("Bark", "Sepal", "Flower Bud") and
# materials ("Acer rubrum Pollen", "Oat", "Psyllium Husk"). No sub-branch separates them, but two of
# NCIt's own annotations do: a material carries an FDA UNII (FDA has registered it as a substance),
# and a structure has Semantic_Type "Plant". Taking the terms with no UNII and type "Plant" selects
# 71. docs/sources/PO/mappings.md compares that with a term-by-term curation of the branch.
NCIT_PLANT_PART_ROOT = f"{NCIT}:C79611"  # "Plant Part"
NCIT_PLANT_SEMANTIC_TYPE = "Plant"


def _obo_id_roots(prefix):
    """Return the ``[(root CURIE, biolink type)]`` list :func:`write_obo_ids` takes for one source.

    The source's own root first, then its subtype roots sorted by CURIE. Order does not decide
    typing — ``write_obo_ids`` resolves an overlap through its ``order`` precedence list — but
    sorting keeps the ids file byte-identical between runs.
    """
    source = ANATOMY_OBO_SOURCES[prefix]
    return [(source["root"], source["type"]), *sorted(source["subtype_roots"].items())]


def remove_overused_xrefs_dict(kv):
    """Given a dict of iri->list of xrefs, look through them for xrefs that are in more than one list.
    Remove those anywhere they occur, as they will only lead to pain further on."""
    used_xrefs = set()
    overused_xrefs = set()
    for k, v in kv.items():
        for x in v:
            if x in used_xrefs:
                overused_xrefs.add(x)
            used_xrefs.add(x)
    print(f"There are {len(overused_xrefs)} overused xrefs")
    for k, v in kv.items():
        kv[k] = list(set(v).difference(overused_xrefs))


def write_obo_ids(irisandtypes, outfile, exclude=()):
    order = [CELLULAR_COMPONENT, CELL, GROSS_ANATOMICAL_STRUCTURE, ANATOMICAL_ENTITY]
    obo.write_obo_ids(irisandtypes, outfile, order, exclude=exclude)


def write_ncit_ids(outfile):
    # For NCIT, there are some branches of the subhiearrchy that we don't want, like this one for genomic locus
    anatomy_id = f"{NCIT}:C12219"
    cell_id = f"{NCIT}:C12508"
    component_id = f"{NCIT}:C34070"
    genomic_location_id = f"{NCIT}:C64389"
    chromosome_band_id = f"{NCIT}:C13432"
    macromolecular_structure_id = f"{NCIT}:C14134"  # protein domains
    ostomy_site_id = f"{NCIT}:C122638"
    chromosome_structure_id = f"{NCIT}:C13377"
    anatomic_site_id = f"{NCIT}:C13717"  # the site of procedures like injections etc
    write_obo_ids(
        [(anatomy_id, ANATOMICAL_ENTITY), (cell_id, CELL), (component_id, CELLULAR_COMPONENT)],
        outfile,
        exclude=[
            genomic_location_id,
            chromosome_band_id,
            macromolecular_structure_id,
            ostomy_site_id,
            chromosome_structure_id,
            anatomic_site_id,
        ],
    )

    # Plant parts are a separate branch, selected by annotation rather than by subtree. They are typed
    # AnatomicalEntity, like the rest of NCIt's anatomy: a term that joins a PO clique takes PO's
    # more specific type there (classify_anatomy_clique()).
    with open(outfile) as inf:
        already_written = {line.split("\t")[0] for line in inf}
    with open(outfile, "a") as outf:
        for curie in sorted(set(fetch_ncit_plant_parts()) - already_written):
            outf.write(f"{curie}\t{ANATOMICAL_ENTITY}\n")


def fetch_ncit_plant_parts():
    """Return ``{curie: label}`` for the NCIt "Plant Part" terms that are plant structures.

    A term qualifies when NCIt gives it Semantic_Type "Plant" and no FDA UNII code; see the comment on
    NCIT_PLANT_PART_ROOT for why those two annotations separate structures from materials. Queries
    UberGraph.
    """
    annotations = UberGraph().get_subclass_annotations(
        NCIT_PLANT_PART_ROOT, [ANNOTATION_LABEL, ANNOTATION_NCIT_SEMANTIC_TYPE, ANNOTATION_NCIT_FDA_UNII_CODE]
    )
    plant_parts = {}
    for curie, values in annotations.items():
        if (
            values[ANNOTATION_NCIT_FDA_UNII_CODE]
            or NCIT_PLANT_SEMANTIC_TYPE not in values[ANNOTATION_NCIT_SEMANTIC_TYPE]
        ):
            continue
        labels = sorted(values[ANNOTATION_LABEL])
        if len(labels) != 1:
            raise RuntimeError(f"Expected exactly one label for NCIt plant part {curie}, got {labels}.")
        plant_parts[curie] = labels[0]
    if not plant_parts:
        raise RuntimeError(
            f"No plant parts found under {NCIT_PLANT_PART_ROOT}: has UberGraph dropped NCIt's annotations?"
        )
    return plant_parts


def write_po_ids(outfile):
    """Write the Plant Ontology's anatomy terms: plant cells as biolink:Cell, every other plant structure
    as biolink:GrossAnatomicalStructure. ANATOMY_OBO_SOURCES says which branches are left out and why."""
    write_obo_ids(_obo_id_roots(PO), outfile, exclude=ANATOMY_OBO_SOURCES[PO]["exclude_roots"])


def write_uberon_ids(outfile):
    write_obo_ids(_obo_id_roots(UBERON), outfile)


def write_cl_ids(outfile):
    write_obo_ids(_obo_id_roots(CL), outfile)


def _emapa_descendants(uber, root):
    """Return the set of EMAPA-prefixed CURIEs reachable from ``root`` in UberGraph.

    EMAPA is a part_of partonomy, not an rdfs:subClassOf hierarchy, so we union the
    part_of closure (the bulk of the structure) with the subClassOf closure (the few
    is_a links). ``get_subclasses_of`` queries the redundant graph, so each call returns
    the full transitive closure under its predicate. The ``root`` itself is not included.
    """
    found = set()
    for term in uber.get_subclasses_of(root, hierarchy_predicate=HIERARCHY_PART_OF) + uber.get_subclasses_of(root):
        curie = term["descendent"]
        if curie.startswith(f"{EMAPA}:"):
            found.add(curie)
    return found


def write_emapa_ids(outfile):
    """Collect EMAPA anatomy identifiers from UberGraph and assign each a biolink type.

    EMAPA is a part_of partonomy, not an rdfs:subClassOf hierarchy, so it cannot be
    collected with write_obo_ids() the way UBERON/GO/CL are — a subClassOf walk from
    the EMAPA root reaches only a handful of terms. We walk part_of from the root instead
    (plus the few is_a links), and keep every EMAPA-prefixed term.

    Biolink typing rule (one type per CURIE, written in column 2 of the ids file): terms at or
    below one of EMAPA's ``subtype_roots`` take that subtree's type, everything else takes the
    source's default ``type``. Both come from ANATOMY_OBO_SOURCES, so the branches this source
    splits on are declared in one place rather than here — today that is EMAPA:35949 "organ" and
    EMAPA:35868 "tissue" as biolink:GrossAnatomicalStructure, over a biolink:AnatomicalEntity
    default. This is the partonomy equivalent of UBERON's gross-branch override, which
    write_obo_ids() applies through its ``order`` precedence list.

    Both types survive write_compendium(): EMAPA is registered as an id_prefix for
    biolink:AnatomicalEntity and biolink:GrossAnatomicalStructure in the Biolink Model
    version this build uses. If a future version drops either registration, gross-typed
    EMAPA CURIEs would start being silently dropped, and the source-impact report's
    survival columns are what would catch it.
    """
    source = ANATOMY_OBO_SOURCES[EMAPA]
    uber = UberGraph()
    curies = {source["root"]} | _emapa_descendants(uber, source["root"])
    # Each subtype root's own subtree overrides the default type. Sorted so that if two subtype
    # roots ever overlap with *different* types, which one wins is at least reproducible; today
    # both EMAPA subtrees are GrossAnatomicalStructure, so the case does not arise.
    subtypes = {}
    for subtype_root, subtype in sorted(source["subtype_roots"].items()):
        for curie in {subtype_root} | _emapa_descendants(uber, subtype_root):
            subtypes[curie] = subtype
    with open(outfile, "w") as idfile:
        for curie in sorted(curies):
            idfile.write(f"{curie}\t{subtypes.get(curie, source['type'])}\n")


def write_go_ids(outfile):
    write_obo_ids(_obo_id_roots(GO), outfile)


def write_mesh_ids(outfile, mesh_registry):
    """Write the anatomy ids/MESH. Records with an NCBI Taxon registry number in mesh_registry (rule
    get_mesh_registry's TSV) are left to taxon, whatever tree they are in; mesh.write_ids() decides that (#1240).
    """
    meshmap = {f"A{str(i).zfill(2)}": ANATOMICAL_ENTITY for i in range(1, 21)}
    meshmap["A11"] = CELL
    meshmap["A11.284"] = CELLULAR_COMPONENT
    mesh.write_ids(meshmap, outfile, pipeline="anatomy", mesh_registry=mesh_registry)


def write_umls_ids(mrsty, outfile, *, mesh_ownership=None):
    """Select the UMLS CUIs the anatomy pipeline claims by semantic type.

    ``mesh_ownership`` (the umls_mesh_ownership rule's output) makes a CUI follow its MeSH descriptor
    (umls.apply_mesh_ownership): a CUI another pipeline owns is dropped here and a CUI this pipeline owns is added.
    """
    # UMLS categories:
    # A1.2 Anatomical Structure
    # A1.2.1 Embryonic Structure
    # A1.2.3 Fully Formed Anatomical Structure
    # A1.2.3.1 Body Part, Organ, or Organ Component
    # A1.2.3.2 Tissue
    # A1.2.3.3 Cell
    # A1.2.3.4 Cell Component
    # A2.1.4.1 Body System
    # A2.1.5.1 Body Space or Junction
    # A2.1.5.2 Body Location or Region
    umlsmap = {
        x: ANATOMICAL_ENTITY for x in ["A1.2", "A1.2.1", "A1.2.3.1", "A1.2.3.2", "A2.1.4.1", "A2.1.5.1", "A2.1.5.2"]
    }
    umlsmap["A1.2.3.3"] = CELL
    umlsmap["A1.2.3.4"] = CELLULAR_COMPONENT
    umls.write_umls_ids(
        mrsty,
        umlsmap,
        outfile,
        mesh_ownership=mesh_ownership,
        pipeline="anatomy",
    )


# Ignore list notes:
# The BTO and BAMs and HTTP (braininfo) identifiers promote over-glommed nodes
# FMA is a specific problem where in CL they use FMA xref to mean 'part of'
# CALOHA is a specific problem where in CL they use FMA xref to mean 'part of'
# GOC is a specific problem where in CL they use FMA xref to mean 'part of'
# wikipedia.en is a specific problem where in CL they use FMA xref to mean 'part of'
# NIF_Subcellular leads to a weird mashup between a GO term and a bunch of other stuff.
# CL only shows up as an xref once in uberon, and it's a mistake.  It doesn't show up in anything else.
# GO only shows up as an xref once in uberon, and it's a mistake.  It doesn't show up in anything else.
# PMID is just wrong
# Target prefixes never written to an anatomy OBO concord: citations (PMID), ontologies Babel
# does not ingest for anatomy (BTO, BAMS, FMA, CALOHA, OPENCYC, NIF_SUBCELLULAR), bare URLs
# (HTTP, WIKIPEDIA.EN), provenance annotations (GOC), and CL/GO, whose cliques are built from
# their own roots rather than from a cross-reference. Matched against Text.get_prefix_or_none(),
# which upper-cases, so every entry must be upper-case.
ANATOMY_OBO_IGNORE_LIST = [
    "PMID",
    "BTO",
    "BAMS",
    "FMA",
    "CALOHA",
    "GOC",
    "WIKIPEDIA.EN",
    "CL",
    "GO",
    "NIF_SUBCELLULAR",
    "HTTP",
    "OPENCYC",
]


def build_emapa_obo_relationships(concordfiles):
    """Write EMAPA's xref concords into ``concordfiles`` (a {prefix: open file} mapping).

    EMAPA is a part_of partonomy, not an is_a hierarchy, so its xref concords must be
    collected by walking part_of rather than rdfs:subClassOf; a subClassOf walk reaches
    only two terms.

    This exists as its own function so that the real build and the EMAPA pipeline test
    fixture issue the identical call. Both write to the same intermediate concord path, so
    a fixture that dropped ``hierarchy_predicate`` or ``ignore_list`` would leave a
    degenerate or unfiltered file that a later Snakemake run would treat as up to date.
    """
    build_sets(
        ANATOMY_OBO_SOURCES[EMAPA]["root"],
        concordfiles,
        "xref",
        ignore_list=ANATOMY_OBO_IGNORE_LIST,
        hierarchy_predicate=HIERARCHY_PART_OF,
    )


def build_anatomy_obo_relationships(outdir, metadata_yamls):
    # Create the equivalence pairs
    with (
        open(f"{outdir}/{UBERON}", "w") as uberon,
        open(f"{outdir}/{GO}", "w") as go,
        open(f"{outdir}/{CL}", "w") as cl,
        open(f"{outdir}/{EMAPA}", "w") as emapa,
    ):
        source_to_concord = {UBERON: uberon, GO: go, CL: cl, EMAPA: emapa}
        for source_prefix in [UBERON, GO]:
            build_sets(
                ANATOMY_OBO_SOURCES[source_prefix]["root"],
                source_to_concord,
                "xref",
                ignore_list=ANATOMY_OBO_IGNORE_LIST,
            )
        build_emapa_obo_relationships(source_to_concord)
        # CL is now being handled by Wikidata (build_wikidata_cell_relationships), so we can probably remove it from here.

    # Write out metadata.
    for metadata_name in [UBERON, GO, CL, EMAPA]:
        write_concord_metadata(
            metadata_yamls[metadata_name],
            name="build_anatomy_obo_relationships()",
            sources=[
                {"type": "UberGraph", "name": "UBERON"},
                {"type": "UberGraph", "name": "GO"},
                {"type": "UberGraph", "name": "CL"},
                {"type": "UberGraph", "name": "EMAPA"},
            ],
            description=(
                "get_subclasses_and_xrefs() of "
                f"{ANATOMY_OBO_SOURCES[UBERON]['root']}, "
                f"{ANATOMY_OBO_SOURCES[GO]['root']}, and "
                f"{ANATOMY_OBO_SOURCES[EMAPA]['root']}"
            ),
            concord_filename=f"{outdir}/{metadata_name}",
        )


# How normalize_plant_part_name() turns a plural word into its singular: the first suffix that matches
# is replaced. Crude on purpose. It only has to send a name and its plural to the same key
# ("Plant Leaves" and "leaf", "Seeds" and "seed", "Plant Stomata" and "stoma"); "epidermis" becoming
# "epidermi" is harmless because both vocabularies get the same treatment.
PLANT_PART_SINGULAR_SUFFIXES = (("leaves", "leaf"), ("ies", "y"), ("ata", "a"), ("ae", "a"), ("es", "e"), ("s", ""))
_PLANT_WORD = re.compile(r"\bplants?\b")
_NOT_A_LETTER = re.compile(r"[^a-z]+")

# Anatomy ontologies that describe animals only. Neither has a plant term, so a cross-reference from
# one of them to a MeSH Plant Structures descriptor is a homonym, not an equivalence: UBERON:0010008
# "placental cotyledon" cites MESH:D018548 "Cotyledon" (the seed leaf), and UBERON:0000312 "inner
# cambium layer of periosteum" cites MESH:D058506 "Cambium". Those two merged a plant structure into an
# animal clique, and the PO term for it followed (#1272). GO and CL are not listed: a cellular component
# such as GO:0090406 "pollen tube" really is the MeSH plant structure.
ANIMAL_ANATOMY_PREFIXES = frozenset({UBERON, EMAPA})

# The predicate written to concords/PO, so the provenance metadata says how each pair was found.
PO_LABEL_MATCH_PREDICATE = "label_match"
# The MeSH tree whose descriptor names are matched against PO.
MESH_PLANT_STRUCTURES_TREE = "A18"  # "Plant Structures"


def normalize_plant_part_name(name):
    """Reduce a plant-part name to the key match_plant_part_names() compares.

    Lower-cases, drops the word "plant" (MeSH and NCIt say "Plant Leaves", "Bulb, Plant" where PO says
    "leaf", "bulb"), drops punctuation, and singularizes each word longer than three letters with
    PLANT_PART_SINGULAR_SUFFIXES. Word order is kept.
    """
    words = []
    for word in _NOT_A_LETTER.sub(" ", _PLANT_WORD.sub(" ", name.lower())).split():
        if len(word) > 3:
            for suffix, singular in PLANT_PART_SINGULAR_SUFFIXES:
                if word.endswith(suffix):
                    word = word[: -len(suffix)] + singular
                    break
        words.append(word)
    return " ".join(words)


def match_plant_part_names(po_names, vocabulary_names):
    """Pair terms of one plant-part vocabulary with Plant Ontology terms of the same name.

    :param po_names: ``{PO CURIE: iterable of names}``, each term's label and exact synonyms
    :param vocabulary_names: ``{CURIE: preferred name}`` for one vocabulary (MeSH A18, or NCIt plant parts)
    :returns: ``{vocabulary CURIE: PO CURIE}``, one-to-one

    Names are compared after normalize_plant_part_name(). A pair is kept only when it is unambiguous
    both ways: a vocabulary term whose name fits two PO terms is left unmatched, and so is every
    vocabulary term claiming a PO term that another one claims too. Nothing picks a winner.

    Only a vocabulary's preferred name is used, never its entry terms or synonyms: MeSH lists parts as
    entry terms of the whole ("Anther, Plant" and "Petal, Plant" under "Flowers"), so matching them
    would map the whole to its parts.

    This is safe only because both sides are plant vocabularies. Against all of anatomy the same
    comparison pairs PO "root" with "tooth root" and PO "placenta" with the animal organ, which is why
    the callers pass MeSH's Plant Structures tree and NCIt's plant parts and nothing wider.
    """
    po_by_name = defaultdict(set)
    for po_curie, names in po_names.items():
        for name in names:
            key = normalize_plant_part_name(name)
            if key:
                po_by_name[key].add(po_curie)
    candidates = {}
    for curie, name in vocabulary_names.items():
        matches = po_by_name.get(normalize_plant_part_name(name), ())
        if len(matches) == 1:
            candidates[curie] = next(iter(matches))
    claims = Counter(candidates.values())
    return {curie: po_curie for curie, po_curie in candidates.items() if claims[po_curie] == 1}


def fetch_po_names(po_curies):
    """Return ``{PO CURIE: set of names}`` (label plus English exact synonyms) for ``po_curies``, from UberGraph."""
    annotations = UberGraph().get_subclass_annotations(
        ANATOMY_OBO_SOURCES[PO]["root"], [ANNOTATION_LABEL, ANNOTATION_EXACT_SYNONYM]
    )
    po_names = {}
    for curie in po_curies:
        synonyms = {obo.clean_po_synonym(synonym) for synonym in annotations[curie][ANNOTATION_EXACT_SYNONYM]}
        po_names[curie] = annotations[curie][ANNOTATION_LABEL] | (synonyms - {None})
    return po_names


def _read_id_column(idfile):
    with open(idfile) as inf:
        return {line.split("\t")[0] for line in inf if line.strip()}


def read_plant_structure_ids(mesh_plant_structures, mesh_ownership):
    """Return the MeSH Plant Structures descriptors anatomy holds, plus the UMLS CUIs that follow them.

    :param mesh_plant_structures: the file build_po_label_relationships() writes, or None (an empty set)
    :param mesh_ownership: the umls_mesh_ownership rule's file, which says which CUI follows which
        descriptor; None adds no CUIs
    """
    if mesh_plant_structures is None:
        return frozenset()
    descriptors = _read_id_column(mesh_plant_structures)
    cuis = set()
    if mesh_ownership is not None:
        cuis = {
            cui
            for cui, (_, descriptor, _) in umls.read_mesh_ownership(mesh_ownership).items()
            if descriptor in descriptors
        }
    return frozenset(descriptors | cuis)


def joins_animal_anatomy_to_plant_structure(subject, obj, plant_structure_ids):
    """True for a concord pair linking an ANIMAL_ANATOMY_PREFIXES term to a plant structure, which the
    anatomy build skips; see the comment on ANIMAL_ANATOMY_PREFIXES."""
    for curie, other in ((subject, obj), (obj, subject)):
        if other in plant_structure_ids and curie.split(":")[0] in ANIMAL_ANATOMY_PREFIXES:
            return True
    return False


def build_po_label_relationships(
    po_ids, mesh_ids, ncit_ids, outfile, metadata_yaml, mesh_plant_structures, mesh_nt=None
):
    """Write concords/PO: Plant Ontology terms paired by name with MeSH plant structures and NCIt plant parts.

    No source Babel reads maps PO to anything: PO's own xrefs are citations and image links, NCIt's
    plant parts have no xrefs at all, and UMLS has no PO source (docs/sources/PO/mappings.md has the
    search). Without this concord PO would sit beside the MeSH and NCIt cliques for "Xylem", "Pollen"
    and "Bark" instead of joining them. match_plant_part_names() is the rule and says why it is safe.

    Each side is limited to what the anatomy ids files hold (``po_ids``, ``mesh_ids``, ``ncit_ids``), so
    the concord cannot bring in a term another rule left out: a PO branch excluded in
    ANATOMY_OBO_SOURCES, or a MeSH record taxon owns.

    Also writes ``mesh_plant_structures``, the anatomy MeSH descriptors in the Plant Structures tree
    (``CURIE<tab>name``), for read_plant_structure_ids(). It is written here because this is the one
    anatomy rule that already has mesh.nt loaded to ask which descriptors those are.

    :param mesh_nt: path to mesh.nt; None reads babel_downloads/MESH/mesh.nt
    """
    po_names = fetch_po_names(_read_id_column(po_ids))
    anatomy_mesh = _read_id_column(mesh_ids)
    anatomy_ncit = _read_id_column(ncit_ids)
    mesh_names = {
        curie: name
        for curie, name in mesh.Mesh(mesh_nt).get_labels_in_tree(MESH_PLANT_STRUCTURES_TREE).items()
        if curie in anatomy_mesh
    }
    with open(mesh_plant_structures, "w") as outf:
        for curie, name in sorted(mesh_names.items()):
            outf.write(f"{curie}\t{name}\n")
    ncit_names = {curie: name for curie, name in fetch_ncit_plant_parts().items() if curie in anatomy_ncit}
    pairs = []
    for vocabulary_names in (mesh_names, ncit_names):
        pairs += [(po_curie, curie) for curie, po_curie in match_plant_part_names(po_names, vocabulary_names).items()]
    with open(outfile, "w") as outf:
        for po_curie, curie in sorted(pairs):
            outf.write(f"{po_curie}\t{PO_LABEL_MATCH_PREDICATE}\t{curie}\n")
    write_concord_metadata(
        metadata_yaml,
        name="build_po_label_relationships()",
        sources=[
            {"type": "UberGraph", "name": "PO"},
            {"type": "UberGraph", "name": "NCIT"},
            {"type": "MESH", "name": f"MeSH tree {MESH_PLANT_STRUCTURES_TREE}"},
        ],
        description=(
            f"Name matches between the label and exact synonyms of PO terms under {ANATOMY_OBO_SOURCES[PO]['root']} "
            f"and the preferred names of MeSH tree {MESH_PLANT_STRUCTURES_TREE} descriptors and of NCIt plant parts "
            f"under {NCIT_PLANT_PART_ROOT}; see match_plant_part_names()."
        ),
        concord_filename=outfile,
    )


def build_wikidata_cell_relationships(outdir, metadata_yaml):
    # This sparql returns all the wikidata items that have a UMLS identifier and a CL identifier
    sparql = """PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wdtn: <http://www.wikidata.org/prop/direct-normalized/>
        SELECT * WHERE {
          ?wd wdtn:P7963 ?cl .
          ?wd wdt:P2892 ?umls .
        }"""
    frink_wikidata_url = "https://apps.okn.us/federation/sparql"
    response = requests.post(frink_wikidata_url, data={"query": sparql})
    if not response.ok:
        raise RuntimeError(f"Could not query {frink_wikidata_url}: {response.status_code} {response.reason}")
    try:
        results = response.json()
    except Exception as e:
        raise RuntimeError(
            f"Could not parse {frink_wikidata_url}: {e} raised when parsing response {response.content}."
        )
    rows = results["results"]["bindings"]
    # If one wikidata entry has either more than one CL or more than one UMLS, then we end up with problems
    # (It could also be possible that the same CL is on more than one wikidata entry, but haven't seen that yet)
    # Loop over the rows, transform each row into curies, and filter out any wikidata entry that occurs more than once.
    # Double check that the UMLS and CL are unique.  Then write out the now-unique UMLS/CL mappings
    counts = defaultdict(int)
    pairs = []
    for row in rows:
        umls_curie = f"{UMLS}:{row['umls']['value']}"
        # wd_curie = f"{WIKIDATA}:{row['wd']['value']}"
        cl_curie = Text.obo_to_curie(row["cl"]["value"])
        pairs.append((umls_curie, cl_curie))
        counts[umls_curie] += 1
        counts[cl_curie] += 1
    with open(f"{outdir}/{WIKIDATA}", "w") as wd:
        for pair in pairs:
            if (counts[pair[0]] == 1) and (counts[pair[1]] == 1):
                wd.write(f"{pair[0]}\teq\t{pair[1]}\n")
            else:
                print(f"Pair {pair} is not unique {counts[pair[0]]} {counts[pair[1]]}")

    # Write out metadata
    write_concord_metadata(
        metadata_yaml,
        name="build_wikidata_cell_relationships()",
        sources=[{"type": "Frink", "name": "Frink Direct Normalized Graph via SPARQL"}],
        description='wd:P7963 ("Cell Ontology ID") and wd:P2892 ("UMLS CUI") from Wikidata',
        concord_filename=f"{outdir}/{WIKIDATA}",
    )


def build_anatomy_umls_relationships(mrconso, idfile, outfile, umls_metadata):
    umls.build_sets(
        mrconso,
        idfile,
        outfile,
        {"SNOMEDCT_US": SNOMEDCT, "MSH": MESH, "NCI": NCIT, "GO": GO, "FMA": FMA},
        provenance_metadata_yaml=umls_metadata,
    )


def _make_anatomy_concord_pair_filter(bad_pairs, owned_elsewhere=frozenset(), plant_structure_ids=frozenset()):
    """Build the ``(parts, infile, dicts) -> bool`` hook glom_from_files applies to every pair.

    ``bad_pairs`` is a set of frozensets, so a listed pair is dropped whichever way round the
    concord happens to write it. It is captured in a closure because the hook runs once per
    concord row and the file must not be re-read that many times. ``owned_elsewhere`` is
    umls.read_cuis_owned_elsewhere(): a pair naming one of those CUIs is dropped too.
    ``plant_structure_ids`` is read_plant_structure_ids(): a pair linking one of those to an
    animal-only ontology is dropped (joins_animal_anatomy_to_plant_structure()).
    """

    def _filter(parts, infile, dicts):
        if umls.names_cui_owned_elsewhere(parts[0], parts[2], owned_elsewhere):
            return False
        if joins_animal_anatomy_to_plant_structure(parts[0], parts[2], plant_structure_ids):
            logger.info("Skipping %s from %s: an animal anatomy term cannot be a plant structure", parts, infile)
            return False
        if frozenset((parts[0], parts[2])) in bad_pairs:
            logger.debug("Skipping bad xref pair %s from %s (see %s)", parts, infile, ANATOMY_BAD_XREFS)
            return False
        return _anatomy_concord_pair_filter(parts, infile, dicts)

    return _filter


def _anatomy_concord_pair_filter(parts, infile, dicts):
    """Drop UMLS<->GO concord pairs unless both CURIEs are already in the clique state.

    UMLS includes obsolete GO terms we don't want to add, so we limit UMLS<->GO concords
    to terms that are already in ``dicts``. This is ONLY for the UMLS/GO combination — we
    trust the other concords to retrieve decent identifiers. Returns True to keep the pair.
    """
    bs = frozenset([UMLS, GO])
    prefixes = frozenset(xi.split(":")[0] for xi in parts[0:3:2])  # leave out the predicate
    if prefixes != bs:
        return True
    for xi in (parts[0], parts[2]):
        if xi not in dicts:
            logger.debug(
                "Skipping pair %s from %s: terms with prefixes %s are skipped unless they are already in the concords.",
                parts,
                infile,
                bs,
            )
            return False
    return True


def compute_cliques_for_impact_report(
    concordances, identifiers, excluded_sources=(), badxrefs=None, *, mesh_ownership=None, mesh_plant_structures=None
):
    """Load anatomy identifier and concord files and return the union-find clique state
    without writing compendia.

    Thin wrapper over :func:`src.model.cliques.glom_from_files` supplying
    anatomy's hooks (unique prefixes, the UMLS<->GO pair filter, and overused-xref
    removal). ``build_compendia`` calls this too, so the source-impact report's reglom
    uses the same code path as the real build.

    The source-impact report CLI calls this twice — once with the new source's files
    excluded, once with everything — to compute a before/after diff.

    :param concordances: list of paths to concord files
    :param identifiers: list of paths to ids files
    :param excluded_sources: set of source names (file basenames) to skip; used to compute
        the "before-new-source" state for the impact report
    :param badxrefs: path to a bad-xrefs file; defaults to ``ANATOMY_BAD_XREFS``. Pass an
        empty string to disable the filter (used by tests).
    :param mesh_ownership: the umls_mesh_ownership rule's file; concord pairs naming a CUI another
        pipeline owns are skipped (umls.read_cuis_owned_elsewhere). None skips nothing.
    :param mesh_plant_structures: build_po_label_relationships()'s list of MeSH plant structures;
        concord pairs linking one (or its CUI) to an animal-only ontology are skipped. None skips nothing.
    :returns: (dicts, types) where dicts is the glom dict-of-sets and types maps CURIE
        to its declared biolink type
    """
    if badxrefs is None:
        badxrefs = ANATOMY_BAD_XREFS
    bad_pairs = {frozenset(pair) for pair in read_badxrefs(badxrefs)} if badxrefs else set()
    logger.info("Loaded %d bad xref pair(s) from %s", len(bad_pairs), badxrefs or "(disabled)")
    return glom_from_files(
        concordances,
        identifiers,
        unique_prefixes=unique_prefixes_from_config("anatomy_unique_prefixes"),
        concord_pair_filter=_make_anatomy_concord_pair_filter(
            bad_pairs,
            umls.read_cuis_owned_elsewhere(mesh_ownership, "anatomy"),
            read_plant_structure_ids(mesh_plant_structures, mesh_ownership),
        ),
        overused_xref_remover=lambda pairs, infile: remove_overused_xrefs(pairs),
        excluded_sources=excluded_sources,
    )


def build_compendia(
    concordances,
    metadata_yamls,
    identifiers,
    icrdf_filename,
    badxrefs=None,
    mesh_ownership=None,
    mesh_plant_structures=None,
):
    """:concordances: a list of files from which to read relationships
    :identifiers: a list of files from which to read identifiers and optional categories
    :badxrefs: path to a bad-xrefs file; defaults to ``ANATOMY_BAD_XREFS``
    :mesh_ownership: the umls_mesh_ownership rule's file (see compute_cliques_for_impact_report)
    :mesh_plant_structures: build_po_label_relationships()'s file (see compute_cliques_for_impact_report)"""
    dicts, types = compute_cliques_for_impact_report(
        concordances,
        identifiers,
        badxrefs=badxrefs,
        mesh_ownership=mesh_ownership,
        mesh_plant_structures=mesh_plant_structures,
    )
    typed_sets = create_typed_sets(set([frozenset(x) for x in dicts.values()]), types)
    write_typed_compendia(metadata_yamls, typed_sets, icrdf_filename)


def classify_anatomy_clique(equivalent_ids, types):
    """Pick a biolink type for one anatomy clique using the same precedence as
    ``create_typed_sets``: trust GO/CL/UBERON/EMAPA/PO in that order, then fall back to a
    majority vote over the declared types of the clique's members, breaking ties by
    most-specific type.

    Returns the biolink type string (e.g. ``"biolink:AnatomicalEntity"``) or ``None``
    if no member of the clique has any declared type.
    """
    order = [CELLULAR_COMPONENT, CELL, GROSS_ANATOMICAL_STRUCTURE, ANATOMICAL_ENTITY]
    prefixes = get_prefixes(equivalent_ids)
    for prefix in [GO, CL, UBERON, EMAPA, PO]:
        if prefix in prefixes and prefixes[prefix][0] in types:
            return types[prefixes[prefix][0]]
    typecounts = defaultdict(int)
    for eid in equivalent_ids:
        if eid in types:
            typecounts[types[eid]] += 1
    if not typecounts:
        return None
    if len(typecounts) == 1:
        return next(iter(typecounts.keys()))
    otypes = [(-c, order.index(t), t) for t, c in typecounts.items()]
    otypes.sort()
    return otypes[0][2]


def create_typed_sets(eqsets, types):
    """Given a set of sets of equivalent identifiers, we want to type each one into
    being either a disease or a phenotypic feature.  Or something else, that we may want to
    chuck out here.
    Current rules: If it has GO trust the GO's type
                   If it has a CL trust the CL's type
                   If it has an UBERON trust the UBERON's type
    After that, check the types dict to see if we know anything.
    """
    typed_sets = defaultdict(set)
    for equivalent_ids in eqsets:
        t = classify_anatomy_clique(equivalent_ids, types)
        if t is None:
            raise RuntimeError(
                f"Cannot assign a biolink type to anatomy clique {equivalent_ids}: no member CURIE has a declared type."
            )
        typed_sets[t].add(equivalent_ids)
    return typed_sets
