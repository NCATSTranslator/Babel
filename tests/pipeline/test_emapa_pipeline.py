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
def test_emapa_concord_is_written_and_well_formed(emapa_pipeline_outputs):
    """The EMAPA concord should be written, and every row it holds should be a valid triple.

    EMAPA asserts no outgoing xrefs in current UberGraph snapshots, so this file is expected
    to be empty (see docs/sources/EMAPA/mappings.md) -- the row assertions below are a guard
    for the day that changes, not the point of the test. What is asserted unconditionally is
    that the extraction path ran to completion and produced the file, which is what would
    break if the part_of traversal or the concord wiring regressed.
    """
    _ = emapa_pipeline_outputs["anatomy"]
    concord_path = _intermediate_concord_path("anatomy", "EMAPA")

    assert os.path.exists(concord_path), f"expected a concord file at {concord_path}"

    with open(concord_path) as infile:
        rows = [line.strip().split("\t") for line in infile if line.strip()]

    for row in rows:
        assert len(row) >= 3, f"concord row is not a triple: {row!r}"
        assert row[0].startswith("EMAPA:"), f"concord subject is not an EMAPA CURIE: {row!r}"
