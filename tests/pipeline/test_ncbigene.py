"""Pipeline tests for the NCBIGene data handler.

Downloads the full gene_info.gz (>1 GB compressed) and runs
pull_ncbigene_labels_synonyms_and_taxa over every row, so these tests are marked both
`pipeline` and `slow` and are skipped by default.  Run with:
    uv run pytest tests/pipeline/test_ncbigene.py --pipeline --no-cov -v

The synonyms file has tens of millions of rows, so the fix-specific checks stream it
line by line rather than loading it into memory via assert_synonyms_file_valid.
"""

import pytest

from tests.conftest import (
    assert_descriptions_file_valid,
    assert_labels_file_valid,
    assert_taxa_file_valid,
)


@pytest.mark.pipeline
@pytest.mark.slow
def test_ncbigene_labels_file_valid(ncbigene_pipeline_outputs):
    rows = assert_labels_file_valid(ncbigene_pipeline_outputs["labels"])
    assert any(r[0].startswith("NCBIGene:") for r in rows), "No NCBIGene: CURIEs found in labels"


@pytest.mark.pipeline
@pytest.mark.slow
def test_ncbigene_taxa_file_valid(ncbigene_pipeline_outputs):
    rows = assert_taxa_file_valid(ncbigene_pipeline_outputs["taxa"])
    assert any(r[0].startswith("NCBIGene:") for r in rows), "No NCBIGene: CURIEs found in taxa"


@pytest.mark.pipeline
@pytest.mark.slow
def test_ncbigene_descriptions_file_valid(ncbigene_pipeline_outputs):
    rows = assert_descriptions_file_valid(ncbigene_pipeline_outputs["descriptions"])
    assert any(r[0].startswith("NCBIGene:") for r in rows), "No NCBIGene: CURIEs found in descriptions"


# The exact fragment strings from the issue #744 example row (gene 828367): a comma-containing
# alias that NCBI wrapped in '' and then pipe-split, leaving these dangling half-quoted pieces.
ISSUE_744_ARTIFACTS = {"''cytochrome P450", "polypeptide 2''"}

# The same gene's *middle* pieces (issue #932). These carry no '' and are indistinguishable from
# real aliases by shape, so only the intact Full_name value identifies them as junk.
ISSUE_932_GENE = "NCBIGene:828367"
ISSUE_932_SHREDDED_PIECES = {"cytochrome P450", "family 706", "polypeptide 2", "subfamily A"}


@pytest.mark.pipeline
@pytest.mark.slow
def test_ncbigene_synonyms_have_no_leading_quote_fragments(ncbigene_pipeline_outputs):
    """No emitted synonym may START with '' — the guarantee of split_ncbigene_synonym_field.

    A leading '' is always the opening of a ''...''-quoted alias that NCBI split across pipe
    fields (issue #744), so a fragment like ''cytochrome P450 must never reach the synonyms file.
    A TRAILING '' is NOT checked: it is legitimate "double-prime" gene nomenclature — real symbols
    such as U2B'', ycf1'', and nrdB'' end in '' and are added straight from the Symbol column.

    Also asserts the two exact fragment strings from the issue's example row are absent, which
    covers the trailing-fragment case (polypeptide 2'') that the leading-only rule cannot.
    Streams the whole file so the check covers every gene, not just a fixture row.
    """
    found_ncbigene = False
    leading_offenders = []
    artifact_offenders = []
    shredded_offenders = []
    issue_932_gene_synonyms = set()
    with open(ncbigene_pipeline_outputs["synonyms"]) as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            assert len(cols) == 3, f"Expected 3 columns, got {len(cols)}: {cols}"
            if cols[0].startswith("NCBIGene:"):
                found_ncbigene = True
            synonym = cols[2]
            if synonym.startswith("''") and len(leading_offenders) < 10:
                leading_offenders.append(line.rstrip("\n"))
            if synonym in ISSUE_744_ARTIFACTS and len(artifact_offenders) < 10:
                artifact_offenders.append(line.rstrip("\n"))
            if cols[0] == ISSUE_932_GENE:
                issue_932_gene_synonyms.add(synonym)
                if synonym in ISSUE_932_SHREDDED_PIECES and len(shredded_offenders) < 10:
                    shredded_offenders.append(line.rstrip("\n"))

    assert found_ncbigene, "No NCBIGene: CURIEs found in synonyms"
    assert not leading_offenders, f"Found synonyms starting with '' (issue #744): {leading_offenders}"
    assert not artifact_offenders, f"Found exact issue #744 fragment strings as synonyms: {artifact_offenders}"

    # Issue #932: the shredded value's middle pieces must not survive, but the value itself must —
    # it comes from Full_name_from_nomenclature_authority, not from reassembling the fragments.
    assert issue_932_gene_synonyms, f"{ISSUE_932_GENE} has no synonyms at all"
    assert not shredded_offenders, f"Found shredded middle pieces as synonyms (issue #932): {shredded_offenders}"
    assert "cytochrome P450, family 706, subfamily A, polypeptide 2" in issue_932_gene_synonyms
