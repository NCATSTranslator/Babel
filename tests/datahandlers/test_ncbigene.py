import gzip

import pytest

from src.datahandlers.ncbigene import pull_ncbigene_labels_synonyms_and_taxa, split_ncbigene_synonym_field
from src.predicates import HAS_SYNONYM
from tests.conftest import (
    assert_descriptions_file_valid,
    assert_labels_file_valid,
    assert_synonyms_file_valid,
    assert_taxa_file_valid,
)

NCBIGENE_HEADER = [
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


def write_gene_info(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as gene_info:
        gene_info.write("\t".join(NCBIGENE_HEADER) + "\n")
        for row in rows:
            gene_info.write("\t".join(row) + "\n")


@pytest.mark.unit
def test_split_ncbigene_synonym_field_skips_unbalanced_single_quote_fragments():
    synonyms = split_ncbigene_synonym_field(
        "AT4G22710|''cytochrome P450|T12H17.100|T12H17_100|cytochrome P450, family 706, polypeptide 2|polypeptide 2''|subfamily A"
    )

    assert "''cytochrome P450" not in synonyms
    assert "polypeptide 2''" not in synonyms
    assert "cytochrome P450, family 706, polypeptide 2" in synonyms
    assert "T12H17.100" in synonyms


@pytest.mark.unit
def test_split_ncbigene_synonym_field_keeps_double_prime_without_open_marker():
    """A trailing '' with no matching open marker is genuine double-prime nomenclature, kept.

    See docs/sources/NCBIGene/quoting/double_prime_report.md: real values such as U2B'' and
    "RNA polymerase subunit beta''" end in '' and must survive, unlike the #744 span fragments.
    """
    # Symbol-style double-prime alongside a normal synonym: no open marker anywhere, so U2B'' stays.
    synonyms = split_ncbigene_synonym_field("U2B''|U2 small nuclear ribonucleoprotein B")
    assert "U2B''" in synonyms
    assert "U2 small nuclear ribonucleoprotein B" in synonyms

    # A standalone double-prime designation.
    assert "RNA polymerase subunit beta''" in split_ncbigene_synonym_field("RNA polymerase subunit beta''")

    # But a trailing '' that IS a close marker (its field has a leading open marker) is still dropped.
    dropped = split_ncbigene_synonym_field("''cytochrome P450|polypeptide 2''")
    assert dropped == set()


@pytest.mark.unit
def test_pull_ncbigene_labels_synonyms_and_taxa_skips_quote_fragments_for_828367(tmp_path):
    gene_info = tmp_path / "gene_info.gz"
    labels = tmp_path / "labels"
    synonyms = tmp_path / "synonyms"
    taxa = tmp_path / "taxa"
    descriptions = tmp_path / "descriptions"
    write_gene_info(
        gene_info,
        [
            [
                "3702",
                "828367",
                "CYP706A2",
                "-",
                "AT4G22710|''cytochrome P450|T12H17.100|T12H17_100|cytochrome P450, family 706, polypeptide 2|polypeptide 2''|subfamily A",
                "-",
                "4",
                "-",
                "cytochrome P450, family 706, subfamily A, polypeptide 2",
                "protein-coding",
                "CYP706A2",
                "cytochrome P450, family 706, subfamily A, polypeptide 2",
                "Official",
                "cytochrome P450, family 706, subfamily A, polypeptide 2",
                "20250601",
                "-",
            ]
        ],
    )

    pull_ncbigene_labels_synonyms_and_taxa(str(gene_info), str(labels), str(synonyms), str(taxa), str(descriptions))

    synonym_rows = assert_synonyms_file_valid(str(synonyms))
    synonym_values = {row[2] for row in synonym_rows}
    assert "''cytochrome P450" not in synonym_values
    assert "polypeptide 2''" not in synonym_values
    assert ["NCBIGene:828367", "CYP706A2"] in assert_labels_file_valid(str(labels))
    assert ["NCBIGene:828367", "NCBITaxon:3702"] in assert_taxa_file_valid(str(taxa))
    assert [
        "NCBIGene:828367",
        "cytochrome P450, family 706, subfamily A, polypeptide 2",
    ] in assert_descriptions_file_valid(str(descriptions))
    assert ["NCBIGene:828367", HAS_SYNONYM, "cytochrome P450, family 706, subfamily A, polypeptide 2"] in synonym_rows
