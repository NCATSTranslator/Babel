"""Every pipeline that writes several compendia in one rule must load icRDF.tsv once, not per output.

icRDF.tsv is ~3.9 million rows, and write_compendium() re-reads it unless the caller passes an
``ic_factory`` (see its docstring for why this is not a module-level cache). The chemical pipeline's
version of this test is in test_chemicals.py; these cover the other pipelines that write one
compendium per Biolink type from a single loop.
"""

from unittest.mock import patch

import pytest

import src.createcompendia.anatomy as anatomy
import src.createcompendia.diseasephenotype as diseasephenotype
import src.createcompendia.processactivitypathway as processactivitypathway
from src.categories import (
    ANATOMICAL_ENTITY,
    BIOLOGICAL_PROCESS,
    CELL,
    DISEASE,
    MOLECULAR_ACTIVITY,
    PHENOTYPIC_FEATURE,
)

ICRDF = "babel_downloads/icRDF.tsv"


def _run_anatomy():
    anatomy.build_compendia([], [], [], ICRDF)


def _run_diseasephenotype():
    diseasephenotype.build_compendium([], [], [], None, None, ICRDF)


def _run_processactivitypathway():
    processactivitypathway.build_compendia([], [], [], ICRDF)


# SHARING ONE FACTORY


@pytest.mark.unit
@pytest.mark.parametrize(
    "module, run, typed_sets",
    [
        pytest.param(anatomy, _run_anatomy, {ANATOMICAL_ENTITY: [["UBERON:1"]], CELL: [["CL:1"]]}, id="anatomy"),
        pytest.param(
            diseasephenotype,
            _run_diseasephenotype,
            {DISEASE: [["MONDO:1"]], PHENOTYPIC_FEATURE: [["HP:1"]]},
            id="diseasephenotype",
        ),
        pytest.param(
            processactivitypathway,
            _run_processactivitypathway,
            {BIOLOGICAL_PROCESS: [["GO:1"]], MOLECULAR_ACTIVITY: [["GO:2"]]},
            id="processactivitypathway",
        ),
    ],
)
def test_every_output_shares_one_information_content_factory(module, run, typed_sets):
    """Should build one InformationContentFactory from icrdf_filename and pass it to every write_compendium call."""
    factories = []

    def record_factory(ic_file):
        factories.append(ic_file)
        return object()

    patches = [
        patch.object(module, "create_typed_sets", return_value=typed_sets),
        patch.object(module, "InformationContentFactory", side_effect=record_factory),
        patch.object(module, "write_compendium"),
    ]
    if hasattr(module, "compute_cliques_for_impact_report"):
        patches.append(patch.object(module, "compute_cliques_for_impact_report", return_value=({}, {})))
    started = [p.start() for p in patches]
    try:
        run()
    finally:
        for p in patches:
            p.stop()
    mock_write = started[2]

    assert factories == [ICRDF]
    assert mock_write.call_count == len(typed_sets)
    shared = {id(call.kwargs["ic_factory"]) for call in mock_write.call_args_list}
    assert len(shared) == 1
    assert all(call.kwargs["icrdf_filename"] == ICRDF for call in mock_write.call_args_list)
