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


def split_ncbigene_synonym_field(value):
    """
    Split a pipe-delimited NCBIGene synonym field into standalone synonym strings.

    Some NCBIGene aliases contain '' around comma-containing text, and those '' quotes
    are not real synonym content. When the quoted text has already been split
    by NCBI into pipe-delimited fragments, the leading/trailing fragments
    (for example: ''cytochrome P450) are not valid synonyms and should not be added.
    """
    synonyms = set()
    for raw_synonym in value.split("|"):
        synonym = raw_synonym.strip()
        if not synonym:
            continue
        starts_quoted = synonym.startswith("''")
        ends_quoted = synonym.endswith("''")
        if starts_quoted and ends_quoted:
            synonym = synonym[2:-2].strip()
        elif starts_quoted or ends_quoted:
            continue
        if synonym:
            synonyms.add(synonym)
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
            syns = split_ncbigene_synonym_field(
                get_ncbigene_field(row, header, "Full_name_from_nomenclature_authority")
            )
            syns.update(split_ncbigene_synonym_field(get_ncbigene_field(row, header, "Synonyms")))
            syns.update(split_ncbigene_synonym_field(get_ncbigene_field(row, header, "Other_designations")))
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
