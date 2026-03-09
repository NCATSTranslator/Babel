import os
import re

import src.datahandlers.mesh as mesh
import src.datahandlers.obo as obo
import src.datahandlers.umls as umls
from src.babel_utils import Text, glom, read_identifier_file, write_compendium
from src.categories import PROTEIN
from src.metadata.provenance import write_concord_metadata
from src.prefixes import DRUGBANK, ENSEMBL, MESH, NCBITAXON, NCIT, PR, UNIPROTKB
from src.ubergraph import UberGraph
from src.util import get_logger, get_memory_usage_summary

logger = get_logger(__name__)


def extract_taxon_ids_from_uniprotkb(idmapping_filename, uniprotkb_taxa_filename):
    """Extract NCBIGene identifiers from the UniProtKB mapping file."""
    with open(idmapping_filename) as inf, open(uniprotkb_taxa_filename, "w") as outf:
        for line in inf:
            x = line.strip().split("\t")
            if x[1] == "NCBI_TaxID":
                if x[0] == "" or x[2] == "":
                    logger.warning(f"Line {x} is an NCBI_TaxID but has a blank UniProtKB ({x[0]}) or NCBITaxon ({x[2]}), skipping.")
                    continue
                outf.write(f"{UNIPROTKB}:{x[0]}\t{NCBITAXON}:{x[2]}\n")


def write_umls_ids(mrsty, outfile):
    umlsmap = {}
    umlsmap["A1.4.1.2.1.7"] = PROTEIN
    umls.write_umls_ids(mrsty, umlsmap, outfile)


def write_mesh_ids(outfile):
    # MeSH protein trees — these are terms excluded from the chemical compendium
    # (see chemicals.write_mesh_ids) that belong in the protein compendium instead.
    #
    # D12.776  Proteins (entire subtree)
    #
    # D05      Macromolecular Substances — only protein-related subtrees:
    #   D05.500  Multiprotein Complexes
    #   D05.875  Protein Aggregates
    #   (Excluded from both compendia: D05.750 Polymers, D05.937 Smart Materials,
    #    D05.374 Micelles — these are non-protein macromolecules.)
    #
    # D08      Enzymes and Coenzymes — only protein-related subtrees:
    #   D08.811  Enzymes
    #   D08.622  Enzyme Precursors
    #   D08.244  Cytochromes
    #   (Excluded from both compendia: D08.211 Coenzymes — these are small molecules.)
    #
    # TODO: A more comprehensive solution would be to define the chemical and protein
    # MeSH tree assignments in a single shared location (e.g. config.yaml or a dedicated
    # mapping module) so that both compendia are derived from the same source of truth.
    # This would prevent the current situation where the excluded trees in chemicals.py
    # and the included trees here must be kept in sync manually. Possible approaches:
    #   1. A shared dict mapping tree numbers to (compendium, category) pairs.
    #   2. A two-pass approach: first classify all MeSH terms, then partition into
    #      compendia based on the classification.
    #   3. Use the MeSH SCR "heading mapped to" relationships more aggressively to
    #      infer types for SCR terms that lack tree numbers (e.g. SCR proteins that
    #      MeSH maps to venom descriptors rather than protein descriptors).
    meshmap = {
        "D12.776": PROTEIN,  # Proteins
        "D05.500": PROTEIN,  # Multiprotein Complexes
        "D05.875": PROTEIN,  # Protein Aggregates
        "D08.811": PROTEIN,  # Enzymes
        "D08.622": PROTEIN,  # Enzyme Precursors
        "D08.244": PROTEIN,  # Cytochromes
    }
    # Also include SCR_Chemical terms mapped to protein descriptor trees.
    # We use scr_include_trees to only keep SCR terms mapped to the protein-related
    # trees (D12.776, D05, D08). This is the inverse of scr_exclude_trees used in
    # chemicals.write_mesh_ids(). We use the broader D05 and D08 here (not just the
    # protein subtrees) because any SCR mapped to D05 or D08 is more likely a protein
    # than a non-protein macromolecule.
    scr_protein_trees = ["D12.776", "D05", "D08"]
    mesh.write_ids(
        meshmap,
        outfile,
        order=[PROTEIN],
        extra_vocab={"SCR_Chemical": PROTEIN},
        scr_include_trees=scr_protein_trees,
    )


def write_pr_ids(outfile):
    protein_id = f"{PR}:000000001"
    obo.write_obo_ids([(protein_id, PROTEIN)], outfile, [PROTEIN])


def write_ensembl_protein_ids(ensembl_dir, outfile):
    """Loop over all the ensembl species.  Find any protein-coding gene"""
    with open(outfile, "w") as outf:
        # find all the ensembl directories
        dirlisting = os.listdir(ensembl_dir)
        for dl in dirlisting:
            dlpath = os.path.join(ensembl_dir, dl)
            if os.path.isdir(dlpath):
                infname = os.path.join(dlpath, "BioMart.tsv")
                print(f"write_ensembl_ids for input filename {infname}")
                if os.path.exists(infname):
                    # open each ensembl file, find the id column, and put it in the output
                    with open(infname) as inf:
                        wrote = set()
                        h = inf.readline()
                        x = h[:-1].split("\t")
                        protein_column = x.index("Protein stable ID")
                        for line in inf:
                            x = line[:-1].split("\t")
                            if x[protein_column] == "":
                                continue
                            pid = f"{ENSEMBL}:{x[protein_column]}"
                            # The pid is not unique, so don't write the same one over again
                            if pid in wrote:
                                continue
                            wrote.add(pid)
                            outf.write(f"{pid}\n")


def build_pr_uniprot_relationships(outfile, ignore_list=[], metadata_yaml=None):
    """Given an IRI create a list of sets.  Each set is a set of equivalent LabeledIDs, and there
    is a set for each subclass of the input iri.  Write these lists to concord files, indexed by the prefix"""
    iri = "PR:000000001"
    uber = UberGraph()
    pro_res = uber.get_subclasses_and_xrefs(iri)
    with open(outfile, "w") as concfile:
        for k, v in pro_res.items():
            for x in v:
                if Text.get_prefix_or_none(x) not in ignore_list:
                    if k.startswith("PR"):
                        concfile.write(f"{k}\txref\t{x}\n")

    if metadata_yaml:
        write_concord_metadata(
            metadata_yaml,
            name="build_pr_uniprot_relationships()",
            description=f"Extracts {PR} xrefs from UberGraph after getting subclasses and xrefs of {iri}, ignoring {ignore_list}.",
            sources=[
                {
                    "type": "UberGraph",
                    "name": "UberGraph",
                }
            ],
            concord_filename=outfile,
        )


def build_protein_uniprotkb_ensemble_relationships(infile, outfile, metadata_yaml):
    with open(infile) as inf, open(outfile, "w") as outf:
        for line in inf:
            x = line.strip().split()
            if x[1] == "Ensembl_PRO":
                uniprot_id = f"{UNIPROTKB}:{x[0]}"
                ensembl_id = f"{ENSEMBL}:{x[2]}"
                outf.write(f"{uniprot_id}\teq\t{ensembl_id}\n")

                # If the ENSEMBL ID is a version string (e.g. ENSEMBL:ENSP00000263368.3),
                # then we should indicate that this is identical to the non-versioned string
                # as well.
                # See https://github.com/TranslatorSRI/Babel/issues/72 for details.
                res = re.match(r"^([A-Z]+\d+)\.\d+", x[2])
                if res:
                    ensembl_id_without_version = res.group(1)
                    outf.write(f"{ensembl_id}\teq\t{ENSEMBL}:{ensembl_id_without_version}\n")

    write_concord_metadata(
        metadata_yaml,
        name="build_protein_uniprotkb_ensemble_relationships()",
        description=f"Extracts {UNIPROTKB}-to-{ENSEMBL} relationships from the ENSEMBL id-mapping file ({infile}) file.",
        sources=[
            {
                "name": "ENSEMBL",
                "filename": infile,
            }
        ],
        concord_filename=outfile,
    )


def build_ncit_uniprot_relationships(infile, outfile, metadata_yaml):
    with open(infile) as inf, open(outfile, "w") as outf:
        for line in inf:
            # These lines are sometimes empty (I think because the
            # input file can have DOS line endings). If so, we can
            # skip those.
            stripped_line = line.strip()
            if stripped_line == "":
                logger.info(f"Skipping empty line in {infile}")
                continue
            x = stripped_line.split()
            ncit_id = f"{NCIT}:{x[0]}"
            uniprot_id = f"{UNIPROTKB}:{x[1]}"
            outf.write(f"{ncit_id}\teq\t{uniprot_id}\n")

    write_concord_metadata(
        metadata_yaml,
        name="build_ncit_uniprot_relationships()",
        description=f"Extracts {NCIT}-to-{UNIPROTKB} relationships from the NCIt-SwissProt_Mapping file ({infile}).",
        sources=[
            {
                "name": "NCIt-SwissProt Mapping file",
                "filename": infile,
            }
        ],
        concord_filename=outfile,
    )


def build_umls_ncit_relationships(mrconso, idfile, outfile, metadata_yaml):
    umls.build_sets(mrconso, idfile, outfile, {"NCI": NCIT}, provenance_metadata_yaml=metadata_yaml)


def build_umls_relationships(mrconso, idfile, outfile, metadata_yaml):
    # The corresponding code in chemicals also includes (1) {'RXNORM': RXCUI}, and (2) we also pull in RxNorm to
    # provide the inverse concords (i.e. RxNorm -> MESH and DRUGBANK). Doing so will probably fix some RXCUI IDs,
    # but assigning RXCUI to proteins seems like a bridge too far for me.
    #
    # TODO: we should probably add some kind of filtering so we don't include concords that point to chemicals rather
    # than proteins, which could result in duplicates (if the same ID is picked up in both chemicals and proteins).
    umls.build_sets(mrconso, idfile, outfile, {"MSH": MESH, "DRUGBANK": DRUGBANK}, provenance_metadata_yaml=metadata_yaml)


def build_protein_compendia(concordances, metadata_yamls, identifiers, icrdf_filename):
    """:concordances: a list of files from which to read relationships
    :identifiers: a list of files from which to read identifiers and optional categories"""
    dicts = {}
    types = {}
    uniques = [UNIPROTKB, PR]
    logger.info(f"Started building protein compendia ({concordances}, {metadata_yamls}, {identifiers}, {icrdf_filename}) with uniques {uniques}")
    for ifile in identifiers:
        logger.info(f"Loading identifier file {ifile}")
        new_identifiers, new_types = read_identifier_file(ifile)
        glom(dicts, new_identifiers, unique_prefixes=uniques)
        types.update(new_types)
        logger.info(f"Loaded identifier file {ifile}: {get_memory_usage_summary()}")
    logger.info(f"Finished loading identifiers, memory usage: {get_memory_usage_summary()}")
    for infile in concordances:
        logger.info(f"Loading concordance file {infile}")
        pairs = []
        with open(infile) as inf:
            for line_index, line in enumerate(inf):
                if line_index % 1000000 == 0:
                    logger.info(f"Loading concordance file {infile}: line {line_index:,}")
                x = line.strip().split("\t")
                pairs.append(set([x[0], x[2]]))
        # print("glomming", infile) # This takes a while, but doesn't add much to the memory
        glom(dicts, pairs, unique_prefixes=uniques)
        logger.info(f"Loaded concordance file {infile}: {get_memory_usage_summary()}")
    logger.info(f"Finished loading concordances, memory usage: {get_memory_usage_summary()}")
    logger.info("Building gene sets")
    gene_sets = set([frozenset(x) for x in dicts.values()])
    logger.info(f"Gene sets built, memory usage: {get_memory_usage_summary()}")
    # Try to preserve some memory here.
    dicts.clear()

    # Memory usage falls at some point; maybe here?
    # TODO: might be a good idea to write all of this out in one step and
    # only then generate the compendium from those input files.

    baretype = PROTEIN.split(":")[-1]
    logger.info(f"Writing compendium for {baretype}, memory usage: {get_memory_usage_summary()}")
    write_compendium(metadata_yamls, gene_sets, f"{baretype}.txt", PROTEIN, {}, extra_prefixes=[DRUGBANK], icrdf_filename=icrdf_filename)
    logger.info(f"Wrote compendium for {baretype}, memory usage: {get_memory_usage_summary()}")
