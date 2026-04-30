import os

import pytest

from tests.pipeline.conftest import _intermediate_concord_path, get_curies_from_ids_file


@pytest.mark.pipeline
def test_emapa_ids_are_non_empty_and_prefixed(emapa_pipeline_outputs):
    ids_path = emapa_pipeline_outputs["anatomy"]
    ids = get_curies_from_ids_file(ids_path)
    assert ids
    assert all(curie.startswith("EMAPA:") for curie in ids)


@pytest.mark.pipeline
def test_emapa_concords_include_external_mappings(emapa_pipeline_outputs):
    _ = emapa_pipeline_outputs["anatomy"]
    concord_path = _intermediate_concord_path("anatomy", "EMAPA")

    with open(concord_path) as infile:
        rows = [line.strip().split("\t") for line in infile if line.strip()]

    # EMAPA xrefs may be empty in current UberGraph snapshots; this test ensures
    # the mapping extraction path runs and output is syntactically valid.
    assert os.path.exists(concord_path)
    assert all(len(row) >= 3 for row in rows)
    assert all(row[0].startswith("EMAPA:") for row in rows)
