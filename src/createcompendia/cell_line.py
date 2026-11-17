from src.babel_utils import glom, read_identifier_file, write_compendium
from src.categories import CELL_LINE


def build_compendia(ifile, metadata_yamls, icrdf_filename):
    """:identifiers: a list of files from which to read identifiers and optional categories"""
    dicts = {}
    types = {}
    print("loading", ifile)
    new_identifiers, new_types = read_identifier_file(ifile)
    # unique_prefixes=() because this pipeline loads ids files alone: every group is one identifier, so
    # glom() never merges anything and a restriction could not change the output. Not a config.yaml
    # setting for that reason (#882).
    glom(dicts, new_identifiers, unique_prefixes=())
    types.update(new_types)
    idsets = set([frozenset(x) for x in dicts.values()])
    baretype = CELL_LINE.split(":")[-1]
    write_compendium(metadata_yamls, idsets, f"{baretype}.txt", CELL_LINE, {}, icrdf_filename=icrdf_filename)
