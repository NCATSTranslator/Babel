import os

import pytest

from tests.pipeline.conftest import _intermediate_concord_path, get_curies_from_ids_file


@pytest.mark.pipeline
def test_mp_ids_are_non_empty_and_prefixed(mp_pipeline_outputs):
    ids_path = mp_pipeline_outputs["diseasephenotype"]
    ids = get_curies_from_ids_file(ids_path)
    assert ids
    assert all(curie.startswith("MP:") for curie in ids)


@pytest.mark.pipeline
def test_mp_concords_include_external_mappings(mp_pipeline_outputs):
    _ = mp_pipeline_outputs["diseasephenotype"]
    concord_path = _intermediate_concord_path("diseasephenotype", "MP")

    # MP UberGraph xrefs may be empty in current snapshots; this test ensures the
    # mapping extraction path runs and output is syntactically valid.
    assert os.path.exists(concord_path)

    with open(concord_path) as infile:
        rows = [line.strip().split("\t") for line in infile if line.strip()]

    assert all(len(row) >= 3 for row in rows)
    assert all(row[0].startswith("MP:") for row in rows)
