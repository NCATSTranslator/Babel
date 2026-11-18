"""Tests for write_typed_compendia(), the one-compendium-per-Biolink-type loop shared by several pipelines."""

import os

import pytest

import src.model.compendia as compendia
from src.categories import DISEASE, DRUG, PHENOTYPIC_FEATURE, SMALL_MOLECULE
from src.model.compendia import write_typed_compendia


class RecordingFactory:
    """Stands in for InformationContentFactory: records the file it was built from, loads nothing."""

    instances = []

    def __init__(self, ic_file):
        self.ic_file = ic_file
        RecordingFactory.instances.append(self)


@pytest.fixture
def recorded(monkeypatch):
    """Replace the factory and write_compendium in src.model.compendia; return (factories, writes)."""
    RecordingFactory.instances = []
    writes = []
    monkeypatch.setattr(compendia, "InformationContentFactory", RecordingFactory)
    monkeypatch.setattr(compendia, "write_compendium", lambda *args, **kwargs: writes.append((args, kwargs)))
    return RecordingFactory.instances, writes


# SHARING ONE FACTORY


@pytest.mark.unit
def test_every_output_shares_one_factory_loaded_from_icrdf_filename(recorded, tmp_path):
    """Should load icRDF.tsv once and pass that factory to every write, built from the same file.

    write_compendium() raises unless realpath(ic_factory.ic_file) == realpath(icrdf_filename), so the
    factory's own file is checked here, not only the filename passed alongside it.
    """
    factories, writes = recorded
    icrdf = str(tmp_path / "icRDF.tsv")

    write_typed_compendia(["meta.yaml"], {DISEASE: [["MONDO:1"]], PHENOTYPIC_FEATURE: [["HP:1"]]}, icrdf)

    assert len(factories) == 1
    assert os.path.realpath(factories[0].ic_file) == os.path.realpath(icrdf)
    assert len(writes) == 2
    for _, kwargs in writes:
        assert kwargs["ic_factory"] is factories[0]
        assert kwargs["icrdf_filename"] == icrdf


# WHAT EACH OUTPUT GETS


@pytest.mark.unit
def test_each_output_is_named_and_typed_after_its_biolink_class(recorded):
    """Should write <BareType>.txt with node_type set to the full biolink: class, and the class's own cliques."""
    _, writes = recorded

    write_typed_compendia(["meta.yaml"], {DISEASE: [["MONDO:1"]], PHENOTYPIC_FEATURE: [["HP:1"]]}, "icRDF.tsv")

    assert [args for args, _ in writes] == [
        (["meta.yaml"], [["MONDO:1"]], "Disease.txt", DISEASE, {}),
        (["meta.yaml"], [["HP:1"]], "PhenotypicFeature.txt", PHENOTYPIC_FEATURE, {}),
    ]


@pytest.mark.unit
def test_extra_prefixes_are_chosen_per_biolink_class(recorded):
    """Should ask extra_prefixes_for() once per class, since extra_prefixes is a per-class allowlist."""
    _, writes = recorded

    write_typed_compendia(
        [],
        {DRUG: [["RXCUI:1"]], SMALL_MOLECULE: [["CHEBI:1"]]},
        "icRDF.tsv",
        extra_prefixes_for=lambda biotype: ["MESH"] if biotype == DRUG else ["RXCUI"],
    )

    assert {args[3]: kwargs["extra_prefixes"] for args, kwargs in writes} == {
        DRUG: ["MESH"],
        SMALL_MOLECULE: ["RXCUI"],
    }


@pytest.mark.unit
def test_no_extra_prefixes_by_default_and_other_kwargs_pass_through(recorded):
    """Should leave extra_prefixes as write_compendium's default and forward any other keyword unchanged."""
    _, writes = recorded

    write_typed_compendia([], {DISEASE: [["MONDO:1"]]}, "icRDF.tsv", properties_jsonl_gz_files=["p.jsonl.gz"])

    (_, kwargs) = writes[0]
    assert kwargs["extra_prefixes"] is None
    assert kwargs["properties_jsonl_gz_files"] == ["p.jsonl.gz"]


# EMPTY OR MISSING INPUT


@pytest.mark.unit
def test_empty_typed_sets_load_nothing(recorded):
    """Should neither read icRDF.tsv nor write anything when there is nothing to write."""
    factories, writes = recorded

    write_typed_compendia([], {}, "icRDF.tsv")

    assert factories == []
    assert writes == []


@pytest.mark.unit
@pytest.mark.parametrize("icrdf_filename", [None, ""])
@pytest.mark.parametrize("typed_sets", [{}, {DISEASE: [["MONDO:1"]]}], ids=["empty", "non-empty"])
def test_missing_icrdf_filename_is_named_before_anything_loads(recorded, icrdf_filename, typed_sets):
    """Should raise the RuntimeError naming the missing argument, not an error from open(), and load nothing.

    Checked even with no typed sets: a rule that forgot to declare icRDF.tsv is miswired regardless.
    """
    factories, writes = recorded

    with pytest.raises(RuntimeError, match="icrdf_filename"):
        write_typed_compendia([], typed_sets, icrdf_filename)

    assert factories == []
    assert writes == []
