import logging

import src.datahandlers.mesh as mesh
import src.datahandlers.umls as umls
from src.babel_utils import write_compendium
from src.categories import ORGANISM_TAXON
from src.metadata.provenance import write_concord_metadata
from src.model.cliques import glom_from_files
from src.prefixes import GTDB, MESH, NCBITAXON, UMLS
from src.util import LoggingUtil

logger = LoggingUtil.init_logging(__name__, level=logging.ERROR)


def write_mesh_ids(outfile):
    # Get the B tree,
    # B01	Eukaryota
    # B02	Archaea
    # B03	Bacteria
    # B04	Viruses
    # B05	Organism Forms
    meshmap = {f"B{str(i).zfill(2)}": ORGANISM_TAXON for i in range(1, 6)}
    # Also add anything from SCR_Chemical, if it doesn't have a tree map
    mesh.write_ids(meshmap, outfile, order=[ORGANISM_TAXON], extra_vocab={"SCR_Organism": ORGANISM_TAXON})


def write_umls_ids(mrsty, outfile):
    # UMLS categories that should be classified as taxa:
    # - A1.1.3: Eukaryote (https://uts.nlm.nih.gov/uts/umls/semantic-network/T204)
    # - A1.1.2: Bacterium (https://uts.nlm.nih.gov/uts/umls/semantic-network/T007)
    # - A1.1.3.3: Plant (https://uts.nlm.nih.gov/uts/umls/semantic-network/T002)
    # - A1.1.3.2: Fungus (https://uts.nlm.nih.gov/uts/umls/semantic-network/T004)
    # - A1.1.3.1.1.3: Fish (https://uts.nlm.nih.gov/uts/umls/semantic-network/T013)
    # - A1.1.3.1.1.2: Bird (https://uts.nlm.nih.gov/uts/umls/semantic-network/T012)
    # - A1.1.4: Virus (https://uts.nlm.nih.gov/uts/umls/semantic-network/T005)
    # - A1.1.3.1.1.4: Mammal (https://uts.nlm.nih.gov/uts/umls/semantic-network/T015)
    # - A1.1.3.1.1.5: Reptile (https://uts.nlm.nih.gov/uts/umls/semantic-network/T014)
    # - A1.1.3.1.1.1: Amphibian (https://uts.nlm.nih.gov/uts/umls/semantic-network/T011)
    # - A1.1.1: Archaeon (https://uts.nlm.nih.gov/uts/umls/semantic-network/T194)
    # - A1.1.3.1: Animal (https://uts.nlm.nih.gov/uts/umls/semantic-network/T008)
    # - A1.1: Organism (https://uts.nlm.nih.gov/uts/umls/semantic-network/T001)
    # - A1.1.3.1.1: Vertebrate (https://uts.nlm.nih.gov/uts/umls/semantic-network/T010)
    #
    # Not clear if these should be included, so left out for now:
    # - A1.1.3.1.1.4.1: Human (https://uts.nlm.nih.gov/uts/umls/semantic-network/T016)
    #   (presumably the human taxon is represented as _Homo sapiens_, which is http://id.nlm.nih.gov/mesh/D006801)

    umlsmap = {
        x: ORGANISM_TAXON
        for x in [
            "A1.1.3",
            "A1.1.2",
            "A1.1.3.3",
            "A1.1.3.2",
            "A1.1.3.1.1.3",
            "A1.1.3.1.1.2",
            "A1.1.4",
            "A1.1.3.1.1.4",
            "A1.1.3.1.1.5",
            "A1.1.3.1.1.1",
            "A1.1.1",
            "A1.1.3.1",
            "A1.1",
            "A1.1.3.1.1",
        ]
    }
    umls.write_umls_ids(mrsty, umlsmap, outfile)


def build_taxon_umls_relationships(mrconso, idfile, outfile, metadata_yaml):
    umls.build_sets(
        mrconso, idfile, outfile, {"MSH": MESH, "NCBITaxon": NCBITAXON}, provenance_metadata_yaml=metadata_yaml
    )


def build_relationships(outfile, mesh_ids, metadata_yaml):
    regis = mesh.pull_mesh_registry()
    # with open(mesh_ids) as inf:
    # lines = inf.read().strip().split("\n")
    # all_mesh_taxa = set([x.split("\t")[0] for x in lines])
    with open(outfile, "w") as outf:
        for meshid, reg in regis:
            # The mesh->ncbi are in mesh as registration numbers that start with a "tx"
            if reg.startswith("txid"):
                ncbi_id = f"{NCBITAXON}:{reg[4:]}"
                outf.write(f"{meshid}\txref\t{ncbi_id}\n")
        # June 7, 2021.  We have previously found that not all mesh/ncbi links are in the mesh.nt
        # but as of today, it appears that they ARE all in there, so we are not hitting eutil any more (thank goodness)
        # left = list(all_mesh_taxa.difference( set([x[0] for x in regis]) ))
        # eutil.lookup(left)

    write_concord_metadata(
        metadata_yaml,
        name="build_relationships()",
        description="Builds relationships between MeSH and NCBI Taxon from the MeSH registry.",
        sources=[
            {
                "type": "MeSH",
                "name": "MeSH Registry",
                "url": "ftp://ftp.nlm.nih.gov/online/mesh/rdf/mesh.nt.gz",
            }
        ],
        concord_filename=outfile,
    )


def compute_cliques_for_impact_report(concordances, identifiers, excluded_sources=()):
    """Load taxon identifier and concord files and return the union-find clique state
    without writing compendia.

    Thin wrapper over :func:`src.model.cliques.glom_from_files` supplying taxon's
    unique-prefix hook (NCBITaxon/MESH/UMLS/GTDB -- GTDB is unique so two GTDB species
    sharing one NCBI taxid are never merged into one clique; the GTDB<->NCBI mapping is
    many-to-one, see ``src/datahandlers/gtdb.py``). ``build_compendia`` calls this too, so
    the source-impact report's reglom uses the same code path as the real build.

    The source-impact report CLI calls this twice -- once with the new source's files
    excluded, once with everything -- to compute a before/after diff.

    :param concordances: list of paths to concord files
    :param identifiers: list of paths to ids files
    :param excluded_sources: set of source basenames to skip (the "before-new-source" state)
    :returns: ``(dicts, types)`` where dicts is the glom dict-of-sets and types maps CURIE
        to its declared biolink type
    """
    return glom_from_files(
        concordances,
        identifiers,
        unique_prefixes=[NCBITAXON, MESH, UMLS, GTDB],
        excluded_sources=excluded_sources,
    )


def build_compendia(concordances, metadata_yamls, identifiers, icrdf_filename):
    """:concordances: a list of files from which to read relationships
    :identifiers: a list of files from which to read identifiers and optional categories"""
    dicts, _ = compute_cliques_for_impact_report(concordances, identifiers)
    gene_sets = set([frozenset(x) for x in dicts.values()])
    baretype = ORGANISM_TAXON.split(":")[-1]
    # GTDB is not in the Biolink Model's organism-taxon id_prefixes ([NCBITaxon, MESH, UMLS]), so it must
    # be passed via extra_prefixes or write_compendium silently drops every GTDB CURIE.
    write_compendium(
        metadata_yamls,
        gene_sets,
        f"{baretype}.txt",
        ORGANISM_TAXON,
        {},
        extra_prefixes=[GTDB],
        icrdf_filename=icrdf_filename,
    )


def classify_taxon_clique(equivalent_ids, types):
    """Pick a biolink type for one taxon clique.

    Every taxon identifier is declared ``biolink:OrganismTaxon`` (the taxon pipeline emits a
    single compendium, ``OrganismTaxon.txt``), so return that if any member of the clique
    carries a declared type, else ``None`` (the clique cannot be typed and is dropped).
    Used by ``create_typed_sets`` and the source-impact report's ``clique_classifier`` hook
    so both label cliques identically.
    """
    for eid in equivalent_ids:
        if eid in types:
            return ORGANISM_TAXON
    return None
