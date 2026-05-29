import logging

import src.datahandlers.mesh as mesh
import src.datahandlers.umls as umls
from src.babel_utils import glom, read_identifier_file, write_compendium
from src.categories import ORGANISM_TAXON
from src.datahandlers.umls import semantic_types as ust
from src.metadata.provenance import write_concord_metadata
from src.prefixes import MESH, NCBITAXON, UMLS
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
    # The UMLS semantic-type -> Biolink-class assignments for taxa live in the central registry
    # src/datahandlers/umls/semantic_types.py (UMLS_TYPE_MAP, compendium="taxon"). Note that Human
    # (A1.1.3.1.1.4.1, T016) is intentionally left out there -- the human taxon is represented via
    # MeSH (http://id.nlm.nih.gov/mesh/D006801) instead.
    umls.write_umls_ids(mrsty, ust.category_map_for("taxon"), outfile)


def build_taxon_umls_relationships(mrconso, idfile, outfile, metadata_yaml):
    umls.build_sets(mrconso, idfile, outfile, {"MSH": MESH, "NCBITaxon": NCBITAXON}, provenance_metadata_yaml=metadata_yaml)


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


def build_compendia(concordances, metadata_yamls, identifiers, icrdf_filename):
    """:concordances: a list of files from which to read relationships
    :identifiers: a list of files from which to read identifiers and optional categories"""
    dicts = {}
    types = {}
    uniques = [NCBITAXON, MESH, UMLS]
    for ifile in identifiers:
        print("loading", ifile)
        new_identifiers, new_types = read_identifier_file(ifile)
        glom(dicts, new_identifiers, unique_prefixes=uniques)
        types.update(new_types)
    for infile in concordances:
        print(infile)
        print("loading", infile)
        pairs = []
        with open(infile) as inf:
            for line in inf:
                x = line.strip().split("\t")
                pairs.append(set([x[0], x[2]]))
        glom(dicts, pairs, unique_prefixes=uniques)
    gene_sets = set([frozenset(x) for x in dicts.values()])
    baretype = ORGANISM_TAXON.split(":")[-1]
    # We need to use extra_prefixes since UMLS is not listed as an identifier prefix at
    # https://biolink.github.io/biolink-model/docs/OrganismTaxon.html
    write_compendium(metadata_yamls, gene_sets, f"{baretype}.txt", ORGANISM_TAXON, {}, icrdf_filename=icrdf_filename)
