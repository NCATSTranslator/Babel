import os

import pytest

from src.createcompendia import diseasephenotype
from tests.pipeline.conftest import _intermediate_concord_path, get_curies_from_ids_file


@pytest.mark.pipeline
def test_mp_ids_are_non_empty_and_prefixed(mp_pipeline_outputs):
    ids_path = mp_pipeline_outputs["diseasephenotype"]
    ids = get_curies_from_ids_file(ids_path)
    assert ids
    assert all(curie.startswith("MP:") for curie in ids)


@pytest.mark.pipeline
def test_mp_concords_include_external_mappings(mp_pipeline_outputs):
    """The live MP concord should be syntactically valid and carry only allowlisted xref targets.

    MP declares oboInOwl:hasDbXref against anatomy (MA/FMA/CL), processes (GO), registry codes
    (Fyler), citations (PMID) and bare URLs, none of which are equivalences. Asserting the target
    prefixes against MP_XREF_ALLOWED_PREFIXES here is what catches an upstream MP release that
    starts emitting a new namespace, and would have caught a concord built without the allowlist.
    """
    _ = mp_pipeline_outputs["diseasephenotype"]
    concord_path = _intermediate_concord_path("diseasephenotype", "MP")

    assert os.path.exists(concord_path)

    with open(concord_path) as infile:
        rows = [line.strip().split("\t") for line in infile if line.strip()]

    assert rows, "MP contributes xrefs to at least MGI; an empty concord means the query broke"
    assert all(len(row) >= 3 for row in rows)
    assert all(row[0].startswith("MP:") for row in rows)

    # Text.get_prefix_or_none() upper-cases, which is what build_sets filters on.
    allowed = {prefix.upper() for prefix in diseasephenotype.MP_XREF_ALLOWED_PREFIXES}
    target_prefixes = {row[2].split(":", 1)[0].upper() for row in rows}
    assert target_prefixes <= allowed, f"MP concord has non-allowlisted targets: {target_prefixes - allowed}"
