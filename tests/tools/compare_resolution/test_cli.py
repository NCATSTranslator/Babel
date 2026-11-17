"""Tests for babel-compare-resolution, the normalization comparison behind it, and the Babel Explorer links it makes.

The unit tests replace the services with the unedited dev responses in ``data/`` (see its README), which show
the #1206 regression: ``GTOPDB:5688`` sits with the stereo-unspecified ``CHEBI:91405``, not the drug
``CHEBI:66919``. One network test queries dev itself.
"""

import json
import pathlib
import urllib.parse

import pytest
import requests
import yaml

from src.model.inchikeys import InchikeyRelation
from src.reports import normalization_comparison as nc
from src.tools.compare_resolution import cli
from src.utils import translator_services as ts

DATA = pathlib.Path(__file__).parent / "data"
CURIES = ["CHEBI:66919", "CHEBI:91405", "GTOPDB:5688", "NOTAPREFIX:1"]


def _load(name):
    return json.loads((DATA / name).read_text())


@pytest.fixture
def fake_services(monkeypatch):
    """Serve the saved dev responses in place of the network, recording which URLs were asked."""
    calls = []

    def normalized_nodes(url, curies, conflate=True, drug_chemical_conflate=False):
        calls.append(("nodenorm", url))
        response = _load(f"dev_ruxolitinib_dc_{str(drug_chemical_conflate).lower()}.json")
        return {c: response.get(c) for c in curies}

    def name_lookup(url, name, limit=20):
        calls.append(("nameres", url))
        return _load("dev_lookup_ruxolitinib.json") if name == "ruxolitinib" else []

    def babel_version(url):
        return _load("dev_status.json")["babel_version"]

    monkeypatch.setattr(cli, "fetch_normalized_nodes", normalized_nodes)
    monkeypatch.setattr(cli, "fetch_name_lookup", name_lookup)
    monkeypatch.setattr(cli, "fetch_babel_version", babel_version)
    return calls


# BABEL EXPLORER LINKS


@pytest.mark.unit
def test_explorer_url_puts_state_in_the_fragment():
    """Should put each CURIE and target in the fragment, in order, with the CURIE colon escaped."""
    url = ts.babel_explorer_url(["CHEBI:50275", "CHEBI:77260"], targets=("dev", "ci", "prod", "test"))
    # The exact link gaurav gave as the format to use (Babel#559's comparison, without GTOPDB:5488).
    assert url == (
        "https://translatorsri.github.io/babel-explorer/nodenorm/#curie=CHEBI%3A50275&curie=CHEBI%3A77260"
        "&target=dev&target=ci&target=prod&target=test"
    )


@pytest.mark.unit
def test_explorer_url_writes_only_options_turned_off():
    """Should write an option only when it is False, since Babel Explorer defaults every option to on."""
    url = ts.babel_explorer_url(["CHEBI:9168"], targets=("dev",), drug_chemical_conflate=False, conflate=True)
    fragment = urllib.parse.parse_qs(urllib.parse.urlparse(url).fragment)
    assert fragment == {"curie": ["CHEBI:9168"], "target": ["dev"], "drug_chemical_conflate": ["false"]}


@pytest.mark.unit
@pytest.mark.parametrize("kwargs", [{"targets": ("staging",)}, {"individual_types": False}])
def test_explorer_url_rejects_unknown_targets_and_options(kwargs):
    """Should raise rather than build a link Babel Explorer would silently ignore part of."""
    with pytest.raises(ValueError):
        ts.babel_explorer_url(["CHEBI:9168"], **kwargs)


# COMPARISON


@pytest.mark.unit
def test_summarize_instance_reads_the_cliques():
    """Should find GTOPDB:5688 in the stereo-less clique, and CHEBI:66919 growing under DrugChemical conflation."""
    result = nc.summarize_instance(
        "dev", "2026jul22", CURIES, _load("dev_ruxolitinib_dc_false.json"), _load("dev_ruxolitinib_dc_true.json")
    )
    assert result.unconflated["GTOPDB:5688"].leader == "CHEBI:91405"
    assert result.unconflated["CHEBI:91405"].inchikeys == ("INCHIKEY:HFNKQEVNSGCOJV-UHFFFAOYSA-N",)
    assert "GTOPDB:5688" in result.unconflated["CHEBI:91405"].highlighted
    assert result.unconflated["NOTAPREFIX:1"] is None
    assert result.conflated["CHEBI:66919"].size > result.unconflated["CHEBI:66919"].size
    cliques = nc.distinct_cliques(result.unconflated)
    assert [c.leader for c in cliques] == ["CHEBI:66919", "CHEBI:91405"]
    assert nc.relate_cliques(*cliques) == InchikeyRelation.ONE_STEREO_UNSPECIFIED


@pytest.mark.unit
def test_same_label_curies_matches_whole_labels_only():
    """Should keep 'Ruxolitinib' and 'ruxolitinib' but not 'ruxolitinib phosphate' or 'RUXOLITINIB, (S)-'."""
    hits = _load("dev_lookup_ruxolitinib.json")
    assert nc.same_label_curies(hits, "ruxolitinib") == ["CHEBI:66919", "CHEBI:91405"]


@pytest.mark.unit
def test_shared_identifiers_flags_a_member_of_two_cliques():
    """Should report an identifier two cliques both carry, as when two compendia claim one (#308)."""
    a = nc.CliqueSummary("CHEBI:64356", "Pregabalin", "", 3, (), (), ("CHEBI:64356", "MESH:D000069583"))
    b = nc.CliqueSummary("UMLS:C0657912", "pregabalin", "", 2, (), (), ("UMLS:C0657912", "MESH:D000069583"))
    assert nc.shared_identifiers([a, b]) == {"MESH:D000069583": ["CHEBI:64356", "UMLS:C0657912"]}


@pytest.mark.unit
def test_instance_disagreements_ignores_unreachable_instances():
    """Should list a CURIE whose leader differs between reachable instances, and skip one that errored."""
    summary = nc.CliqueSummary("CHEBI:66919", "", "", 1, (), ())
    other = nc.CliqueSummary("CHEBI:91405", "", "", 1, (), ())
    instances = [
        nc.InstanceResult("dev", unconflated={"GTOPDB:5688": other}),
        nc.InstanceResult("test", unconflated={"GTOPDB:5688": summary}),
        nc.InstanceResult("prod", error="timed out"),
    ]
    assert nc.instance_disagreements(instances, ["GTOPDB:5688"]) == {
        "GTOPDB:5688": {"dev": "CHEBI:91405", "test": "CHEBI:66919"}
    }


@pytest.mark.unit
def test_draft_babel_tests_is_valid_yaml_in_babel_validation_shape():
    """Should produce a block that parses to the same structure babel-validation reads from an issue."""
    block = nc.draft_babel_tests(
        [["GTOPDB:5688", "CHEBI:66919"]], [["CHEBI:66919", "CHEBI:91405"]], ["CHEBI:66919", "CHEBI:91405"]
    )
    assert yaml.safe_load(block) == {
        "babel_tests": {
            "ResolvesWith": [["GTOPDB:5688", "CHEBI:66919"]],
            "DoesNotResolveWith": [["CHEBI:66919", "CHEBI:91405"]],
            "Resolves": [["CHEBI:66919", "CHEBI:91405"]],
        }
    }


# CLI


@pytest.mark.unit
def test_cli_report(fake_services, capsys):
    """Should report each instance's cliques, the relation, the Explorer link and a draft test block."""
    assert cli.main([*CURIES, "--target", "dev", "--same", "GTOPDB:5688,CHEBI:66919"]) == 0
    out = capsys.readouterr().out
    assert "## dev (Babel 2026jul22)" in out
    assert "| `NOTAPREFIX:1` | does not normalize |" in out
    assert "`CHEBI:66919` and `CHEBI:91405`: same skeleton; one has no stereo layer" in out
    assert "babel-explorer/nodenorm/#curie=CHEBI%3A66919" in out
    assert "    - ['GTOPDB:5688', 'CHEBI:66919']" in out
    # NOTAPREFIX:1 resolves nowhere, so it gets no Resolves guard.
    assert "    - ['CHEBI:66919', 'CHEBI:91405', 'GTOPDB:5688']" in out
    assert ("nodenorm", ts.NODENORM_INSTANCES["dev"]) in fake_services


@pytest.mark.unit
def test_cli_name_adds_same_label_hits(fake_services, capsys, tmp_path):
    """Should add the NameRes hits labelled with --name, and write to --out when given."""
    out_file = tmp_path / "report.md"
    assert cli.main(["--name", "ruxolitinib", "--out", str(out_file)]) == 0
    report = out_file.read_text()
    assert "How 2 CURIEs normalize" in report
    assert ("nameres", ts.NAMERES_INSTANCES["dev"]) in fake_services
    assert capsys.readouterr().out == ""


@pytest.mark.unit
def test_cli_reports_an_unreachable_instance(fake_services, monkeypatch, capsys):
    """Should report an instance it can't reach and carry on with the others."""

    def failing_version(url):
        if url == ts.NODENORM_INSTANCES["test"]:
            raise requests.ConnectionError("no route to host")
        return "2026jul22"

    monkeypatch.setattr(cli, "fetch_babel_version", failing_version)
    assert cli.main(["CHEBI:66919", "--target", "dev", "--target", "test"]) == 0
    out = capsys.readouterr().out
    assert "Could not query this instance: no route to host" in out
    assert "## dev (Babel 2026jul22)" in out


@pytest.mark.unit
def test_cli_rejects_a_one_curie_group(fake_services):
    """Should refuse a --same group with one CURIE, which can't assert anything."""
    with pytest.raises(ValueError):
        cli.main(["--same", "CHEBI:66919"])


# NETWORK


@pytest.mark.network
def test_dev_serves_ruxolitinib():
    """Should normalize CHEBI:66919 on dev NodeNorm and report a Babel version."""
    url = ts.NODENORM_INSTANCES["dev"]
    assert ts.fetch_babel_version(url)
    assert ts.fetch_normalized_nodes(url, ["CHEBI:66919"])["CHEBI:66919"]["id"]["identifier"] == "CHEBI:66919"
