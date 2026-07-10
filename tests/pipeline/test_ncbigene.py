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


@pytest.mark.pipeline
@pytest.mark.slow
def test_ncbigene_synonyms_have_no_stray_quote_fragments(ncbigene_pipeline_outputs):
    """No emitted synonym should start or end with '' — the guarantee of split_ncbigene_synonym_field.

    This is the real-data regression check for issue #744: malformed quoted alias fragments
    like ''cytochrome P450 must never reach the synonyms file.  Streams the whole file so the
    check covers every gene, not just a fixture row.
    """
    found_ncbigene = False
    offenders = []
    with open(ncbigene_pipeline_outputs["synonyms"]) as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            assert len(cols) == 3, f"Expected 3 columns, got {len(cols)}: {cols}"
            if cols[0].startswith("NCBIGene:"):
                found_ncbigene = True
            synonym = cols[2]
            if synonym.startswith("''") or synonym.endswith("''"):
                offenders.append(line.rstrip("\n"))
                if len(offenders) >= 10:
                    break

    assert found_ncbigene, "No NCBIGene: CURIEs found in synonyms"
    assert not offenders, f"Found synonyms with stray '' fragments (issue #744): {offenders}"
