def normalize_sdf_tag(tag_line):
    """
    Normalize an SDF data-item tag line ('> <ChEBI ID>') to the key used to look it up.

    This is the single definition of that normalization: lowercased, spaces stripped, underscores
    kept, with `formulae` folded onto `formula`. Anything that reasons about which tags a file
    carries -- notably docs/sources/CHEBI/sdf_tags/audit_sdf_tags.py -- must call this rather than
    re-implement it, or it ends up measuring different keys than the parser actually uses.

    :param tag_line: A raw SDF tag line, e.g. '> <ChEBI ID>'.
    :return: The normalized key, e.g. 'chebiid'.
    """
    key = tag_line.replace(">", "").replace("<", "").strip().replace(" ", "").lower()
    return "formula" if key == "formulae" else key


def read_sdf(infile, interesting_keys):
    """Given an sdf file name and a set of normalized tag keys (see normalize_sdf_tag()) that we'd
    like to extract, return a dictionary going chebiid -> {properties} where the properties are
    chosen from the interesting keys"""
    with open(infile) as inf:
        chebisdf = inf.read()
    lines = chebisdf.split("\n")
    chunk = []
    chebi_props = {}
    for line in lines:
        if "$$$$" in line:
            chebi_id, chebi_dict = chebi_sdf_entry_to_dict(chunk, interesting_keys=interesting_keys)
            chebi_props[chebi_id] = chebi_dict
            chunk = []
        else:
            if line != "\n":
                line = line.strip("\n")
                chunk += [line]
    return chebi_props


def chebi_sdf_entry_to_dict(sdf_chunk, interesting_keys=frozenset()):
    """
    Converts each SDF entry to a dictionary keyed by the normalized tag names in interesting_keys.
    """
    final_dict = {}
    current_key = "mol_file"
    chebi_id = ""
    for line in sdf_chunk:
        if len(line):
            if ">" == line[0]:
                current_key = normalize_sdf_tag(line)
                if current_key in interesting_keys:
                    final_dict[current_key] = []
                continue
            if current_key == "chebiid":
                chebi_id = line
            if current_key in interesting_keys:
                final_dict[current_key].append(line)
    return (chebi_id, final_dict)
