"""Every pipeline that writes one compendium per Biolink type must write them through write_typed_compendia().

That helper (src/model/compendia.py, tested in tests/model/test_compendia.py) loads icRDF.tsv once and shares it
across outputs; a pipeline with its own write loop goes back to one ~3.9-million-row load per output. These tests
pin that each pipeline hands its typed sets and icRDF path to the helper. The chemical pipeline's version is
test_build_compendia_loads_icrdf_once_for_every_output in test_chemicals.py, which runs its real typing step.

Each pipeline's clique-building step is stubbed explicitly, so a change there can't break these tests and these
tests can't quietly start covering a different path.
"""

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
METADATA_YAMLS = ["metadata.yaml"]


def _stub_cliques_from_impact_report(module, monkeypatch):
    """anatomy and diseasephenotype build their cliques in compute_cliques_for_impact_report()."""
    monkeypatch.setattr(module, "compute_cliques_for_impact_report", lambda *args, **kwargs: ({}, {}))


def _stub_process_cliques(module, monkeypatch):
    """processactivitypathway builds its cliques inline; with no input files, only the config lookup runs."""
    monkeypatch.setattr(module, "unique_prefixes_from_config", lambda *args: {})


# DELEGATING TO write_typed_compendia


@pytest.mark.unit
@pytest.mark.parametrize(
    "module, stub_cliques, run, typed_sets",
    [
        pytest.param(
            anatomy,
            _stub_cliques_from_impact_report,
            lambda: anatomy.build_compendia([], METADATA_YAMLS, [], ICRDF),
            {ANATOMICAL_ENTITY: [["UBERON:1"]], CELL: [["CL:1"]]},
            id="anatomy",
        ),
        pytest.param(
            diseasephenotype,
            _stub_cliques_from_impact_report,
            lambda: diseasephenotype.build_compendium([], METADATA_YAMLS, [], None, None, ICRDF),
            {DISEASE: [["MONDO:1"]], PHENOTYPIC_FEATURE: [["HP:1"]]},
            id="diseasephenotype",
        ),
        pytest.param(
            processactivitypathway,
            _stub_process_cliques,
            lambda: processactivitypathway.build_compendia([], METADATA_YAMLS, [], ICRDF),
            {BIOLOGICAL_PROCESS: [["GO:1"]], MOLECULAR_ACTIVITY: [["GO:2"]]},
            id="processactivitypathway",
        ),
    ],
)
def test_pipeline_writes_every_output_through_write_typed_compendia(module, stub_cliques, run, typed_sets, monkeypatch):
    """Should pass all of its typed sets, its metadata YAMLs and its icRDF path to one write_typed_compendia call."""
    stub_cliques(module, monkeypatch)
    monkeypatch.setattr(module, "create_typed_sets", lambda *args: typed_sets)
    calls = []
    monkeypatch.setattr(module, "write_typed_compendia", lambda *args, **kwargs: calls.append((args, kwargs)))

    run()

    assert len(calls) == 1
    (args, _) = calls[0]
    assert args == (METADATA_YAMLS, typed_sets, ICRDF)
