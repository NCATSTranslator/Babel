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


@pytest.mark.unit
def test_split_ncbigene_synonym_field_skips_unbalanced_single_quote_fragments():
    """The ''-bearing marker fragments never escape, and genuine aliases are untouched.

    The quoted value itself is NOT reconstructable from this column: its pieces are interleaved
    with real aliases and reordered, so there is no span to rejoin. It does not need to be --
    the correct "cytochrome P450, family 706, subfamily A, polypeptide 2" is carried by the
    Full_name_from_nomenclature_authority / Other_designations columns instead (asserted in
    test_pull_ncbigene_labels_synonyms_and_taxa_skips_quote_fragments_for_828367 below).

    Known limitation: the bare comma-pieces (`family 706`, `subfamily A`, ...) do still come through
    as standalone synonyms here. They are junk, but they are not malformed. Pinned below so that
    fixing them trips this test rather than passing silently.
    """
    synonyms = split_ncbigene_synonym_field(GENE_828367_SYNONYMS)

    # The guarantee: no fragment carrying a '' marker is emitted.
    assert "''cytochrome P450" not in synonyms
    assert "polypeptide 2''" not in synonyms
    assert not any(s.startswith("''") for s in synonyms)

    # Genuine aliases in the same field survive.
    assert "T12H17.100" in synonyms
    assert "T12H17_100" in synonyms

    # Pins CURRENT, KNOWN-IMPERFECT behavior, not a guarantee we want to keep: the comma-pieces of
    # the quoted value are emitted as standalone synonyms. Issue #932
    # (https://github.com/NCATSTranslator/Babel/issues/932) proposes dropping them by matching them
    # against the row's Full_name. When that lands, invert this assertion -- do not "repair" the
    # test by deleting it.
    assert {"cytochrome P450", "family 706", "polypeptide 2", "subfamily A"} <= synonyms


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
                "cytochrome P450, family 706, subfamily A, polypeptide 2",
                "protein-coding",
                "CYP706A2",
                "cytochrome P450, family 706, subfamily A, polypeptide 2",
                "O",
                "cytochrome P450, family 706, subfamily A, polypeptide 2",
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
    assert [
        "NCBIGene:828367",
        "cytochrome P450, family 706, subfamily A, polypeptide 2",
    ] in assert_descriptions_file_valid(str(descriptions))

    # The mangled alias is recovered in full from Full_name_from_nomenclature_authority, not by
    # reassembling the Synonyms fragments.
    assert ["NCBIGene:828367", HAS_SYNONYM, "cytochrome P450, family 706, subfamily A, polypeptide 2"] in synonym_rows

    # Pins CURRENT, KNOWN-IMPERFECT behavior: the junk comma-pieces still reach the synonyms file.
    # See issue #932 (https://github.com/NCATSTranslator/Babel/issues/932); invert when it lands.
    assert {"cytochrome P450", "family 706", "polypeptide 2", "subfamily A"} <= synonym_values
