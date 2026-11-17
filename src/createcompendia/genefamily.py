from src.babel_utils import glom, read_identifier_file, write_compendium
from src.categories import GENE_FAMILY


def build_compendia(identifiers, metadata_yamls, icrdf_filename):
    """:concordances: a list of files from which to read relationships
    :identifiers: a list of files from which to read identifiers and optional categories"""
    dicts = {}
    types = {}
    for ifile in identifiers:
        print("loading", ifile)
        new_identifiers, new_types = read_identifier_file(ifile)
        # unique_prefixes=() because this pipeline loads ids files alone: every group is one identifier, so
        # glom() never merges anything and a restriction could not change the output. Not a config.yaml
        # setting for that reason (#882).
        glom(dicts, new_identifiers, unique_prefixes=())
        types.update(new_types)
    genefam_sets = set([frozenset(x) for x in dicts.values()])
    baretype = GENE_FAMILY.split(":")[-1]
    write_compendium(metadata_yamls, genefam_sets, f"{baretype}.txt", GENE_FAMILY, {}, icrdf_filename=icrdf_filename)
