import gzip

import pytest

from src.datahandlers.ncbigene import (
    GENE_INFO_HEADER,
    pull_ncbigene_labels_synonyms_and_taxa,
    split_ncbigene_synonym_field,
)
from src.predicates import HAS_SYNONYM
from tests.conftest import (
    assert_descriptions_file_valid,
    assert_labels_file_valid,
    assert_synonyms_file_valid,
    assert_taxa_file_valid,
)


def write_gene_info(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as gene_info:
        gene_info.write("\t".join(GENE_INFO_HEADER) + "\n")
        for row in rows:
            gene_info.write("\t".join(row) + "\n")


# The verbatim Synonyms field of gene 828367 (CYP706A2) from gene_info.gz -- the row reported in
# issue #744. NCBI quoted the comma-containing alias as ''...'' and then turned its internal commas
# into pipes, so its pieces (cytochrome P450 / family 706 / polypeptide 2 / subfamily A) arrive as
# separate fragments, *interleaved* with the genuine aliases T12H17.100 and T12H17_100 and in no
# meaningful order. Note both a quoted and an unquoted copy of the first and last piece are present.
GENE_828367_SYNONYMS = (
    "''cytochrome P450|T12H17.100|T12H17_100|cytochrome P450|family 706|polypeptide 2|polypeptide 2''|subfamily A"
)
# The same value, intact, as gene_info.gz carries it in Full_name_from_nomenclature_authority /
# Other_designations / description -- the key to recognising the shredded pieces above (#932).
GENE_828367_FULL_NAME = "cytochrome P450, family 706, subfamily A, polypeptide 2"


@pytest.mark.unit
def test_split_ncbigene_synonym_field_skips_unbalanced_single_quote_fragments():
    """The ''-bearing marker fragments never escape, and genuine aliases are untouched.

    The quoted value itself is NOT reconstructable from this column: its pieces are interleaved
    with real aliases and reordered, so there is no span to rejoin. It does not need to be --
    the correct "cytochrome P450, family 706, subfamily A, polypeptide 2" is carried by the
    Full_name_from_nomenclature_authority / Other_designations columns instead (asserted in
    test_pull_ncbigene_labels_synonyms_and_taxa_skips_quote_fragments_for_828367 below).

    Without the `quoted_value` context the middle pieces of the shredded value (`family 706`,
    `subfamily A`) cannot be recognised, so they still come through; passing it drops them (#932,
    covered by the next test).
    """
    synonyms = split_ncbigene_synonym_field(GENE_828367_SYNONYMS)

    # The guarantee: no fragment carrying a '' marker is emitted.
    assert "''cytochrome P450" not in synonyms
    assert "polypeptide 2''" not in synonyms
    assert not any(s.startswith("''") for s in synonyms)

    # Genuine aliases in the same field survive.
    assert "T12H17.100" in synonyms
    assert "T12H17_100" in synonyms


@pytest.mark.unit
def test_split_ncbigene_synonym_field_drops_shredded_middle_pieces():
    """Given the intact value, the shredded value's middle pieces are dropped (issue #932).

    NCBI turned the commas of "cytochrome P450, family 706, subfamily A, polypeptide 2" into pipes,
    so its pieces arrive as fragments carrying no '' at all and indistinguishable from real aliases
    by shape. Passing the intact value from Full_name_from_nomenclature_authority identifies them.
    """
    synonyms = split_ncbigene_synonym_field(GENE_828367_SYNONYMS, GENE_828367_FULL_NAME)

    # The junk middle pieces are gone.
    assert synonyms.isdisjoint({"cytochrome P450", "family 706", "polypeptide 2", "subfamily A"})

    # Genuine aliases are untouched, and no '' marker escapes.
    assert synonyms == {"T12H17.100", "T12H17_100"}

    # Without an open marker there is no shredded value, so nothing is dropped even when the
    # fragments happen to match a piece of the full name.
    intact = split_ncbigene_synonym_field("cytochrome P450|T12H17.100", GENE_828367_FULL_NAME)
    assert intact == {"cytochrome P450", "T12H17.100"}


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
def test_split_ncbigene_synonym_field_keeps_middle_pieces_without_quoted_value():
    """An open marker with no `quoted_value` still drops the '' markers themselves, but the middle
    pieces (which carry no '' at all) can't be identified as junk without the intact value to
    compare against, so they pass through. This is the case where a row's
    Full_name_from_nomenclature_authority and Other_designations are both blank.
    """
    synonyms = split_ncbigene_synonym_field(GENE_828367_SYNONYMS)

    assert synonyms == {"T12H17.100", "T12H17_100", "cytochrome P450", "family 706", "polypeptide 2", "subfamily A"}


@pytest.mark.unit
def test_pull_ncbigene_labels_synonyms_and_taxa_skips_quote_fragments_for_828367(tmp_path):
    """End-to-end over the real issue #744 row: no ''-marker fragment reaches the synonyms file,
    and the comma-containing alias that NCBI mangled in the Synonyms column is still recovered in
    full -- not by reassembling the fragments, but because Full_name_from_nomenclature_authority
    and Other_designations carry it intact.
    """
    gene_info = tmp_path / "gene_info.gz"
    labels = tmp_path / "labels"
    synonyms = tmp_path / "synonyms"
    taxa = tmp_path / "taxa"
    descriptions = tmp_path / "descriptions"
    write_gene_info(
        gene_info,
        [
            # Verbatim row for gene 828367 from gene_info.gz (the issue #744 example).
            [
                "3702",
                "828367",
                "CYP706A2",
                "AT4G22710",
                GENE_828367_SYNONYMS,
                "Araport:AT4G22710|TAIR:AT4G22710",
                "4",
                "-",
                GENE_828367_FULL_NAME,
                "protein-coding",
                "CYP706A2",
                GENE_828367_FULL_NAME,
                "O",
                GENE_828367_FULL_NAME,
                "20260706",
                "-",
            ]
        ],
    )

    pull_ncbigene_labels_synonyms_and_taxa(str(gene_info), str(labels), str(synonyms), str(taxa), str(descriptions))

    synonym_rows = assert_synonyms_file_valid(str(synonyms))
    synonym_values = {row[2] for row in synonym_rows}
    assert "''cytochrome P450" not in synonym_values
    assert "polypeptide 2''" not in synonym_values
    assert not any(s.startswith("''") for s in synonym_values)
    assert ["NCBIGene:828367", "CYP706A2"] in assert_labels_file_valid(str(labels))
    assert ["NCBIGene:828367", "NCBITaxon:3702"] in assert_taxa_file_valid(str(taxa))
    assert ["NCBIGene:828367", GENE_828367_FULL_NAME] in assert_descriptions_file_valid(str(descriptions))

    # The mangled alias is recovered in full from Full_name_from_nomenclature_authority, not by
    # reassembling the Synonyms fragments.
    assert ["NCBIGene:828367", HAS_SYNONYM, GENE_828367_FULL_NAME] in synonym_rows

    # The shredded value's middle pieces do not reach the synonyms file (#932).
    assert synonym_values.isdisjoint({"cytochrome P450", "family 706", "polypeptide 2", "subfamily A"})

    # The gene's real aliases do.
    assert {"T12H17.100", "T12H17_100", "CYP706A2"} <= synonym_values


@pytest.mark.unit
def test_pull_ncbigene_labels_synonyms_and_taxa_falls_back_to_other_designations(tmp_path):
    """When Full_name_from_nomenclature_authority is blank, `quoted_value` falls back to
    Other_designations (ncbigene.py's `quoted_value = full_name or other_designations`) -- the
    shredded value's middle pieces are still dropped using that column instead.
    """
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
                "AT4G22710",
                GENE_828367_SYNONYMS,
                "Araport:AT4G22710|TAIR:AT4G22710",
                "4",
                "-",
                "-",  # Full_name_from_nomenclature_authority blank.
                "protein-coding",
                "-",
                "-",  # Full_name_from_nomenclature_authority blank.
                "-",
                GENE_828367_FULL_NAME,  # Other_designations carries the intact value instead.
                "20260706",
                "-",
            ]
        ],
    )

    pull_ncbigene_labels_synonyms_and_taxa(str(gene_info), str(labels), str(synonyms), str(taxa), str(descriptions))

    synonym_values = {row[2] for row in assert_synonyms_file_valid(str(synonyms))}
    # The shredded value's middle pieces are dropped via the Other_designations fallback.
    assert synonym_values.isdisjoint({"cytochrome P450", "family 706", "polypeptide 2", "subfamily A"})
    # The gene's real aliases, and the intact value from Other_designations itself, survive.
    assert {"T12H17.100", "T12H17_100", "CYP706A2", GENE_828367_FULL_NAME} <= synonym_values
