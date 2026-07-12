import gzip

from src.babel_utils import pull_via_urllib
from src.predicates import HAS_SYNONYM

# The full 16-column gene_info.gz layout. See https://ftp.ncbi.nlm.nih.gov/gene/DATA/README.
GENE_INFO_HEADER = [
    "#tax_id",
    "GeneID",
    "Symbol",
    "LocusTag",
    "Synonyms",
    "dbXrefs",
    "chromosome",
    "map_location",
    "description",
    "type_of_gene",
    "Symbol_from_nomenclature_authority",
    "Full_name_from_nomenclature_authority",
    "Nomenclature_status",
    "Other_designations",
    "Modification_date",
    "Feature_type",
]


def pull_ncbigene(filenames):
    for fn in filenames:
        pull_via_urllib("https://ftp.ncbi.nlm.nih.gov/gene/DATA/", fn, decompress=False, subpath="NCBIGene")


def get_ncbigene_field(row, header, field_name):
    """
    A helper function for returning the value of a field in gene_info.gz by name.
    The value is `-` if no value is present, so we need to convert that into an empty string.

    :param r: A row from gene_info.gz.
    :param field_name: A field name in the header of gene_info.gz.
    :return: The value in this column in this row, otherwise the empty string ('').
    """
    index = header.index(field_name)
    value = row[index].strip()
    if value == "-":
        return ""
    return value


def is_open_marker(starts_quoted, ends_quoted):
    """True if a pipe-fragment's quote flags mark it as a #744 open marker.

    An open marker starts with '' but does not also end with '' (that would be a self-contained
    ''...'' value). Shared between split_ncbigene_synonym_field and
    docs/sources/NCBIGene/quoting/double_prime_report.py so the two can't drift apart on what
    counts as an artifact vs. genuine double-prime nomenclature.
    """
    return starts_quoted and not ends_quoted


def split_ncbigene_synonym_field(value, quoted_value=""):
    """
    Split a pipe-delimited NCBIGene synonym field into standalone synonym strings.

    NCBI wraps some comma-containing values in ''...'' and then turns that value's internal commas
    into '|' -- the column's own delimiter -- so the value arrives shredded into pipe-fragments
    (issue #744). The first carries a leading '' and the last a trailing '' (''cytochrome P450 ...
    polypeptide 2''); both are dropped.

    A *trailing* '' by itself, however, is usually legitimate double-prime nomenclature -- real
    values such as U2B'', "RNA polymerase subunit beta''", and "...6''-O-malonyltransferase" end in
    '' and must be kept. An empirical scan of gene_info.gz (see
    docs/sources/NCBIGene/quoting/double_prime_report.md) found ~25,000 genuine double-prime values
    versus only a few hundred shredded values, and confirmed that a *leading* '' never begins a
    genuine name. So a fragment is treated as an artifact only when it is a leading open marker, or
    a trailing close marker in a field that also contains such an open marker.

    That leaves the value's *middle* pieces, which carry no '' at all and are indistinguishable from
    real aliases by shape alone: `family 706`, `subfamily A`, `MET`, even a bare `3`. They are junk
    (issue #932). Pass the row's Full_name_from_nomenclature_authority (or Other_designations) as
    `quoted_value` and they are dropped: it holds the same value intact and correctly
    comma-formatted, so its comma-pieces are exactly the fragments to remove. The value itself still
    reaches the synonyms from its own column, so nothing is lost. Only applied when the field
    actually contains an open marker -- absent one, no value was shredded into it and every fragment
    is a real alias.
    """
    fragments = [
        (fragment, fragment.startswith("''"), fragment.endswith("''"))
        for fragment in (f.strip() for f in value.split("|"))
    ]
    # An open marker starts with '' but does not also end with '' (that would be a self-contained
    # ''...'' value). Its presence means a comma-containing value was shredded into this field, so
    # the matching trailing close marker -- and the value's middle pieces -- are artifacts too.
    has_open_marker = any(is_open_marker(starts_quoted, ends_quoted) for _, starts_quoted, ends_quoted in fragments)
    shredded_pieces = set()
    if has_open_marker and quoted_value:
        shredded_pieces = {piece.strip() for piece in quoted_value.split(",") if piece.strip()}

    synonyms = set()
    for fragment, starts_quoted, ends_quoted in fragments:
        if not fragment:
            continue
        if starts_quoted and ends_quoted:
            # A fully ''...''-wrapped single value: unwrap it.
            stripped = fragment[2:-2].strip()
            if stripped:
                synonyms.add(stripped)
            continue
        if starts_quoted:
            # Leading '' = open marker of a #744 shredded value -> drop.
            continue
        if ends_quoted and has_open_marker:
            # Trailing '' in a shredded field = close marker -> drop. Without an open marker, a
            # trailing '' is genuine double-prime nomenclature and is kept below.
            continue
        if fragment in shredded_pieces:
            # A middle piece of the shredded value (#932) -> drop.
            continue
        synonyms.add(fragment)
    return synonyms


def pull_ncbigene_labels_synonyms_and_taxa(
    gene_info_filename, labels_filename, synonyms_filename, taxa_filename, descriptions_filename
):
    """
    Extract labels, synonyms, and taxonomic data for genes from the NCBIGene "gene_info.gz" file
    and write them into separate files. The function processes the input file by skipping rows
    with certain unwanted gene types and writing relevant data to output files for gene labels,
    synonyms, and taxonomy associations. Only rows conforming to the required gene type are processed.

    The output files include:
    1. Label file: Gene IDs mapped to their canonical labels (symbols).
    2. Synonym file: Gene IDs mapped to associated synonyms.
    3. Taxa file: Gene IDs mapped to their corresponding taxonomy identifiers.

    :raises AssertionError: If the file headers in "gene_info.gz" do not match the expected format.
    :raises RuntimeError: If a synonym value of `-` is encountered in the output, indicating unexpected
        processing behavior in the input file.

    :return: None
    """

    # File format described here: https://ftp.ncbi.nlm.nih.gov/gene/DATA/README
    bad_gene_types = {"biological-region", "other", "unknown"}
    with (
        gzip.open(gene_info_filename, "r") as inf,
        open(labels_filename, "w") as labelfile,
        open(synonyms_filename, "w") as synfile,
        open(taxa_filename, "w") as taxafile,
        open(descriptions_filename, "w") as descriptionfile,
    ):
        # Make sure the gene_info.gz columns haven't changed from under us.
        header = inf.readline().decode("utf-8").strip().split("\t")
        assert header == GENE_INFO_HEADER

        for line in inf:
            sline = line.decode("utf-8")
            row = sline.strip().split("\t")
            gene_id = f"NCBIGene:{get_ncbigene_field(row, header, 'GeneID')}"
            gene_type = get_ncbigene_field(row, header, "type_of_gene")
            if gene_type in bad_gene_types:
                continue
            taxafile.write(f"{gene_id}\tNCBITaxon:{get_ncbigene_field(row, header, '#tax_id')}\n")

            # Write out all the synonyms.
            full_name = get_ncbigene_field(row, header, "Full_name_from_nomenclature_authority")
            other_designations = get_ncbigene_field(row, header, "Other_designations")
            # Whichever column holds the value intact is the key to un-shredding the Synonyms column
            # when NCBI has mangled that same value into it (#932). Every shredded field found in
            # gene_info.gz is in Synonyms, so only that call needs the context.
            quoted_value = full_name or other_designations
            syns = split_ncbigene_synonym_field(full_name)
            syns.update(split_ncbigene_synonym_field(get_ncbigene_field(row, header, "Synonyms"), quoted_value))
            syns.update(split_ncbigene_synonym_field(other_designations))
            # syns.add(get_ncbigene_field(row, header, "description"))
            syns.add(get_ncbigene_field(row, header, "Symbol_from_nomenclature_authority"))
            syns.add(get_ncbigene_field(row, header, "Symbol"))
            for syn in syns:
                # Skip empty synonym.
                if syn.strip() == "" or syn.strip() == "-":
                    continue

                # gene_info.gz uses `-` to indicate a blank field -- if we're seeing that here, that means
                # we've misread the file somehow!
                if syn == "-":
                    raise RuntimeError("Synonym '-' should not be present in NCBIGene output!")

                synfile.write(f"{gene_id}\t{HAS_SYNONYM}\t{syn}\n")

            # Figure out the label. We would ideally go with:
            #   {Symbol_from_nomenclature_authority || Symbol}: {Full_name_from_nomenclature_authority}
            # But falling back cleanly. As per https://github.com/NCATSTranslator/Babel/issues/429
            best_symbol = get_ncbigene_field(row, header, "Symbol_from_nomenclature_authority")
            if not best_symbol:
                # Fallback to the "Symbol" field.
                best_symbol = get_ncbigene_field(row, header, "Symbol")
            if not best_symbol and len(syns) > 0:
                # Fallback to the first synonym.
                best_symbol = syns[0]

            labelfile.write(f"{gene_id}\t{best_symbol}\n")

            # Write a description file for this description record.
            description = get_ncbigene_field(row, header, "description")
            descriptionfile.write(f"{gene_id}\t{description}\n")
