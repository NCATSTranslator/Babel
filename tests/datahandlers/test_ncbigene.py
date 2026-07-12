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


# The verbatim gene 828367 (CYP706A2) fields from gene_info.gz -- the row reported in issue #744.
# Named here only because the end-to-end tests below thread them through several columns of a
# 16-column row and then assert on them; the split_ncbigene_synonym_field cases in SPLIT_CASES spell
# them out in full instead, so each case can be read on its own.
GENE_828367_SYNONYMS = (
    "''cytochrome P450|T12H17.100|T12H17_100|cytochrome P450|family 706|polypeptide 2|polypeptide 2''|subfamily A"
)
GENE_828367_FULL_NAME = "cytochrome P450, family 706, subfamily A, polypeptide 2"


# Every case is (Synonyms field, full_name, exactly the synonyms that should come out), written out
# in full so the shredded field and the intact value can be read side by side: `full_name` is
# "cytochrome P450, family 706, subfamily A, polypeptide 2", and you can see its comma-pieces
# scattered through the Synonyms field, interleaved with the genuine aliases T12H17.100 and
# T12H17_100 that must survive.
#
# Assertions are exact-set, not "contains", so a case pins the whole output and a new error case is
# one entry rather than a new test function. Add to this table when a new NCBI quoting shape turns
# up -- characterize it against the real gene_info.gz first (see docs/sources/NCBIGene/quoting/).
SPLIT_CASES = [
    # The verbatim gene 828367 (CYP706A2) row from gene_info.gz -- the one reported in issue #744.
    # Note both a quoted and an unquoted copy of the first and last piece are present.
    pytest.param(
        "''cytochrome P450|T12H17.100|T12H17_100|cytochrome P450|family 706|polypeptide 2|polypeptide 2''|subfamily A",
        "cytochrome P450, family 706, subfamily A, polypeptide 2",
        {"T12H17.100", "T12H17_100"},
        id="shredded-value-with-full-name-drops-markers-and-middle-pieces",
    ),
    # The same field with no full_name to compare against (a row whose
    # Full_name_from_nomenclature_authority and Other_designations are both blank). The ''-marked
    # ends still go, but the middle pieces carry no '' at all and cannot be identified as junk
    # without the intact value -- so they survive. This is the #932 limitation, not a bug.
    pytest.param(
        "''cytochrome P450|T12H17.100|T12H17_100|cytochrome P450|family 706|polypeptide 2|polypeptide 2''|subfamily A",
        "",
        {"T12H17.100", "T12H17_100", "cytochrome P450", "family 706", "polypeptide 2", "subfamily A"},
        id="shredded-value-without-full-name-keeps-middle-pieces",
    ),
    # No open marker => nothing was shredded into this field, so every fragment is a real alias --
    # even "cytochrome P450", which does equal a comma-piece of the full name. Guards the #932 fix
    # against over-reaching.
    pytest.param(
        "cytochrome P450|T12H17.100",
        "cytochrome P450, family 706, subfamily A, polypeptide 2",
        {"cytochrome P450", "T12H17.100"},
        id="no-open-marker-keeps-fragments-matching-full-name-pieces",
    ),
    # A trailing '' with no matching open marker is genuine double-prime nomenclature, not an
    # artifact -- see docs/sources/NCBIGene/quoting/double_prime_report.md.
    pytest.param(
        "U2B''|U2 small nuclear ribonucleoprotein B",
        "",
        {"U2B''", "U2 small nuclear ribonucleoprotein B"},
        id="double-prime-symbol-kept",
    ),
    pytest.param(
        "RNA polymerase subunit beta''",
        "",
        {"RNA polymerase subunit beta''"},
        id="standalone-double-prime-designation-kept",
    ),
    # Open marker present, so the trailing '' IS a close marker: both ends go, nothing is left.
    pytest.param(
        "''cytochrome P450|polypeptide 2''",
        "",
        set(),
        id="open-and-close-markers-both-dropped",
    ),
    # A self-contained ''...'' value is unwrapped rather than dropped.
    pytest.param(
        "''cytochrome P450, family 706''|T12H17.100",
        "",
        {"cytochrome P450, family 706", "T12H17.100"},
        id="balanced-quotes-unwrapped",
    ),
    # The no-'' fast path.
    pytest.param(
        "CYP706A2|T12H17.100",
        "cytochrome P450, family 706, subfamily A, polypeptide 2",
        {"CYP706A2", "T12H17.100"},
        id="field-without-any-quotes-passes-through",
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(("synonyms_field", "full_name", "expected"), SPLIT_CASES)
def test_split_ncbigene_synonym_field(synonyms_field, full_name, expected):
    """Each case pins the exact set of synonyms a Synonyms field should produce.

    The two behaviors under test, both established by characterizing the whole gene_info.gz (see
    docs/sources/NCBIGene/quoting/): a fragment is a #744 artifact only when it is a leading open
    marker or a trailing close marker in a field that also has an open marker (so genuine
    double-prime nomenclature survives), and the shredded value's middle pieces are #932 junk,
    identifiable only against the intact value in `full_name`.
    """
    assert split_ncbigene_synonym_field(synonyms_field, full_name) == expected


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
    """When Full_name_from_nomenclature_authority is blank, the `full_name` argument falls back to
    Other_designations (ncbigene.py passes `full_name or other_designations`) -- the shredded
    value's middle pieces are still dropped using that column instead.
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
