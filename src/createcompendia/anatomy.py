from collections import defaultdict

import requests

import src.datahandlers.mesh as mesh
import src.datahandlers.obo as obo
import src.datahandlers.umls as umls
from src.babel_utils import get_prefixes, remove_overused_xrefs, write_compendium
from src.categories import ANATOMICAL_ENTITY, CELL, CELLULAR_COMPONENT, GROSS_ANATOMICAL_STRUCTURE
from src.metadata.provenance import write_concord_metadata
from src.model.cliques import glom_from_files
from src.prefixes import CL, EMAPA, FMA, GO, MESH, NCIT, SNOMEDCT, UBERON, UMLS, WIKIDATA
from src.ubergraph import HIERARCHY_PART_OF, UberGraph, build_sets
from src.util import Text, get_config, get_logger

logger = get_logger(__name__)

ANATOMY_OBO_SOURCES = {
    UBERON: {"root": f"{UBERON}:0001062", "type": ANATOMICAL_ENTITY},
    CL: {"root": f"{CL}:0000000", "type": CELL},
    GO: {"root": f"{GO}:0005575", "type": CELLULAR_COMPONENT},
    EMAPA: {"root": f"{EMAPA}:0", "type": ANATOMICAL_ENTITY},
}

# Roots of the EMAPA "organ" and "tissue" subtrees. Terms at or below these are typed as
# GrossAnatomicalStructure (see write_emapa_ids); everything else defaults to AnatomicalEntity.
EMAPA_ORGAN = f"{EMAPA}:35949"
EMAPA_TISSUE = f"{EMAPA}:35868"


def _write_ontology_ids(source_prefix, outfile):
    source = ANATOMY_OBO_SOURCES[source_prefix]
    write_obo_ids([(source["root"], source["type"])], outfile)


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


def write_obo_ids(irisandtypes, outfile, exclude=[]):
    order = [CELLULAR_COMPONENT, CELL, GROSS_ANATOMICAL_STRUCTURE, ANATOMICAL_ENTITY]
    obo.write_obo_ids(irisandtypes, outfile, order, exclude=[])


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


def write_uberon_ids(outfile):
    # Keep GrossAnatomicalStructure typing from the dedicated UBERON gross root.
    gross_id = f"{UBERON}:0010000"
    write_obo_ids(
        [
            (ANATOMY_OBO_SOURCES[UBERON]["root"], ANATOMY_OBO_SOURCES[UBERON]["type"]),
            (gross_id, GROSS_ANATOMICAL_STRUCTURE),
        ],
        outfile,
    )


def write_cl_ids(outfile):
    _write_ontology_ids(CL, outfile)


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

    Biolink typing rule (one type per CURIE, written in column 2 of the ids file):

    - Terms at or below EMAPA:35949 "organ" or EMAPA:35868 "tissue" are typed as
      biolink:GrossAnatomicalStructure. The two roots are themselves gross structures, so
      they are included.
    - Every other EMAPA term defaults to biolink:AnatomicalEntity.

    Gross typing takes precedence on overlap, matching the precedence in write_obo_ids()
    (the ``order`` list ranks GrossAnatomicalStructure above AnatomicalEntity) and UBERON's
    gross-branch override in write_uberon_ids().

    NOTE: EMAPA is not (yet) one of GrossAnatomicalStructure's id_prefixes in the Biolink
    Model, so EMAPA terms typed as gross are dropped by write_compendium() until EMAPA is
    registered for that class. The source-impact report flags this; see
    docs/AddingNewSources.md.
    """
    root = ANATOMY_OBO_SOURCES[EMAPA]["root"]
    uber = UberGraph()
    curies = {root} | _emapa_descendants(uber, root)
    gross_curies = {EMAPA_ORGAN, EMAPA_TISSUE} | _emapa_descendants(uber, EMAPA_ORGAN) | _emapa_descendants(uber, EMAPA_TISSUE)
    with open(outfile, "w") as idfile:
        for curie in sorted(curies):
            biolink_type = GROSS_ANATOMICAL_STRUCTURE if curie in gross_curies else ANATOMICAL_ENTITY
            idfile.write(f"{curie}\t{biolink_type}\n")


def write_go_ids(outfile):
    _write_ontology_ids(GO, outfile)


def write_mesh_ids(outfile):
    meshmap = {f"A{str(i).zfill(2)}": ANATOMICAL_ENTITY for i in range(1, 21)}
    meshmap["A11"] = CELL
    meshmap["A11.284"] = CELLULAR_COMPONENT
    mesh.write_ids(meshmap, outfile)


def write_umls_ids(mrsty, outfile):
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
    umls.write_umls_ids(mrsty, umlsmap, outfile)


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
def build_anatomy_obo_relationships(outdir, metadata_yamls):
    ignore_list = [
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
    # Create the equivalence pairs
    with (
        open(f"{outdir}/{UBERON}", "w") as uberon,
        open(f"{outdir}/{GO}", "w") as go,
        open(f"{outdir}/{CL}", "w") as cl,
        open(f"{outdir}/{EMAPA}", "w") as emapa,
    ):
        source_to_concord = {UBERON: uberon, GO: go, CL: cl, EMAPA: emapa}
        for source_prefix in [UBERON, GO]:
            build_sets(ANATOMY_OBO_SOURCES[source_prefix]["root"], source_to_concord, "xref", ignore_list=ignore_list)
        # EMAPA is a part_of partonomy, not an is_a hierarchy, so its xref concords must
        # be collected by walking part_of rather than rdfs:subClassOf.
        build_sets(
            ANATOMY_OBO_SOURCES[EMAPA]["root"],
            source_to_concord,
            "xref",
            ignore_list=ignore_list,
            hierarchy_predicate=HIERARCHY_PART_OF,
        )
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


def build_wikidata_cell_relationships(outdir, metadata_yaml):
    # This sparql returns all the wikidata items that have a UMLS identifier and a CL identifier
    sparql = """PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wdtn: <http://www.wikidata.org/prop/direct-normalized/>
        SELECT * WHERE {
          ?wd wdtn:P7963 ?cl .
          ?wd wdt:P2892 ?umls .
        }"""
    frink_wikidata_url = "https://frink.apps.renci.org/federation/sparql"
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


def compute_cliques_for_impact_report(concordances, identifiers, excluded_sources=()):
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
    :returns: (dicts, types) where dicts is the glom dict-of-sets and types maps CURIE
        to its declared biolink type
    """
    return glom_from_files(
        concordances,
        identifiers,
        unique_prefixes=get_config()["anatomy_unique_prefixes"],
        concord_pair_filter=_anatomy_concord_pair_filter,
        overused_xref_remover=lambda pairs, infile: remove_overused_xrefs(pairs),
        excluded_sources=excluded_sources,
    )


def build_compendia(concordances, metadata_yamls, identifiers, icrdf_filename):
    """:concordances: a list of files from which to read relationships
    :identifiers: a list of files from which to read identifiers and optional categories"""
    dicts, types = compute_cliques_for_impact_report(concordances, identifiers)
    typed_sets = create_typed_sets(set([frozenset(x) for x in dicts.values()]), types)
    for biotype, sets in typed_sets.items():
        baretype = biotype.split(":")[-1]
        write_compendium(metadata_yamls, sets, f"{baretype}.txt", biotype, {}, icrdf_filename=icrdf_filename)


def classify_anatomy_clique(equivalent_ids, types):
    """Pick a biolink type for one anatomy clique using the same precedence as
    ``create_typed_sets``: trust GO/CL/UBERON/EMAPA in that order, then fall back to a
    majority vote over the declared types of the clique's members, breaking ties by
    most-specific type.

    Returns the biolink type string (e.g. ``"biolink:AnatomicalEntity"``) or ``None``
    if no member of the clique has any declared type.
    """
    order = [CELLULAR_COMPONENT, CELL, GROSS_ANATOMICAL_STRUCTURE, ANATOMICAL_ENTITY]
    prefixes = get_prefixes(equivalent_ids)
    for prefix in [GO, CL, UBERON, EMAPA]:
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
