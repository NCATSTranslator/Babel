"""Tests for the helpers shared across the Snakemake files (src/snakefiles/util.py).

The config/rule drift check tests load small Snakefiles through the Snakemake API (in-process, ~0.1s each) rather
than faking the workflow object, so that output matching is Snakemake's own: wildcard outputs, path modifiers and so on.
"""

import json

import pytest
from snakemake.api import SnakemakeApi
from snakemake.exceptions import WorkflowError
from snakemake.settings.types import ConfigSettings, OutputSettings, ResourceSettings

from src.snakefiles.util import (
    ID_PREFIX_LISTS,
    duckdb_memory_limit_mb,
    get_all_synonyms_with_drugchemicalconflated,
    get_sapbert_training_synonyms,
)
from src.util import get_config, get_repo_root


@pytest.mark.unit
@pytest.mark.parametrize(
    "mem_mb,expected",
    [
        # Snakemake parses a rule's mem= with decimal suffixes, so mem="128G" reaches us as
        # mem_mb=128000, not 131072. These are the values the pipeline actually passes in.
        (128000, 96000),  # mem="128G" * 0.75
        (512000, 384000),  # mem="512G" * 0.75
        (1001, 750),  # a non-round allocation truncates rather than rounding up
    ],
)
def test_duckdb_memory_limit_mb(mem_mb, expected):
    """Should take resources.mem_mb (a plain int) and return `fraction` of it in MB, truncated.

    Not resources.mem: Snakemake stores every sized resource as mem_mb internally and re-exposes
    `mem` through humanfriendly formatting for display, so our "512G" rule setting comes back as
    the string "512 GB". mem_mb sidesteps that round-trip entirely.
    """
    assert duckdb_memory_limit_mb(mem_mb) == expected


def load_snakefile(tmp_path, monkeypatch, snakefile_text, config):
    """Write `snakefile_text` to tmp_path/Snakefile and have Snakemake parse it with `config`."""
    # Snakemake changes into the workdir while parsing; monkeypatch restores the original directory afterwards.
    monkeypatch.chdir(tmp_path)
    snakefile = tmp_path / "Snakefile"
    snakefile.write_text(snakefile_text)
    with SnakemakeApi(OutputSettings(quiet={"all"})) as api:
        workflow_api = api.workflow(
            resource_settings=ResourceSettings(),
            config_settings=ConfigSettings(config=config),
            snakefile=snakefile,
            workdir=tmp_path,
        )
        workflow_api.list_rules()


FIND_MISSING_SNAKEFILE = """
import json
from src.snakefiles.util import find_missing_id_prefixes

rule literal_hgnc:
    output: "out/gene/ids/HGNC"
    shell: "touch {output}"

rule nested_under_ids:
    output: "out/gene/ids/sub/NESTED"
    shell: "touch {output}"

rule extension_wildcard:
    output: "out/gene/ids/{prefix}.extra"
    shell: "touch {output}"

rule process_wildcard:
    output: "out/process/ids/{prefix}"
    shell: "touch {output}"

missing = find_missing_id_prefixes(workflow, config["ids_dir"], "test_ids", config["prefixes"])
with open("missing.json", "w") as f:
    json.dump(missing, f)
"""


def find_missing(tmp_path, monkeypatch, ids_dir, prefixes):
    load_snakefile(tmp_path, monkeypatch, FIND_MISSING_SNAKEFILE, {"ids_dir": ids_dir, "prefixes": prefixes})
    return json.loads((tmp_path / "missing.json").read_text())


@pytest.mark.unit
def test_literal_output_covers_prefix_and_missing_prefix_is_reported(tmp_path, monkeypatch):
    assert find_missing(tmp_path, monkeypatch, "out/gene/ids", ["HGNC", "ZZZ", "AAA"]) == ["AAA", "ZZZ"]


@pytest.mark.unit
def test_trailing_slash_on_ids_dir_is_ignored(tmp_path, monkeypatch):
    assert find_missing(tmp_path, monkeypatch, "out/gene/ids/", ["HGNC", "ZZZ"]) == ["ZZZ"]


@pytest.mark.unit
def test_outputs_that_are_not_ids_dir_slash_prefix_do_not_count(tmp_path, monkeypatch):
    # ids/sub/NESTED is not ids/NESTED, and ids/{prefix}.extra cannot produce ids/OTHER.
    assert find_missing(tmp_path, monkeypatch, "out/gene/ids", ["NESTED", "OTHER"]) == ["NESTED", "OTHER"]


@pytest.mark.unit
def test_wildcard_output_covers_every_prefix(tmp_path, monkeypatch):
    assert find_missing(tmp_path, monkeypatch, "out/process/ids", ["GO", "REACT", "RHEA"]) == []


@pytest.mark.unit
def test_string_instead_of_list_is_a_clear_error(tmp_path, monkeypatch):
    # `--config gene_ids=HGNC` gives a string; it must not be checked one character at a time.
    with pytest.raises(
        WorkflowError, match=r"test_ids must be a list of prefixes, not str 'HGNC'.*test_ids=\[\"HGNC\"\]"
    ):
        find_missing(tmp_path, monkeypatch, "out/gene/ids", "HGNC")


CHECK_SNAKEFILE = """
from src.snakefiles.util import check_id_prefix_rules

rule gene_hgnc:
    output: config["intermediate_directory"] + "/gene/ids/HGNC"
    shell: "touch {output}"

rule chemical_ids:
    output: config["intermediate_directory"] + "/chemicals/ids/{prefix}"
    shell: "touch {output}"

check_id_prefix_rules(workflow, config)
"""


def check_config(**prefix_lists):
    config = {"intermediate_directory": "out/intermediate"}
    config.update({config_key: [] for config_key in ID_PREFIX_LISTS})
    config.update(prefix_lists)
    return config


@pytest.mark.unit
def test_check_id_prefix_rules_passes_when_every_prefix_has_a_rule(tmp_path, monkeypatch):
    load_snakefile(
        tmp_path, monkeypatch, CHECK_SNAKEFILE, check_config(gene_ids=["HGNC"], chemical_ids=["CHEBI", "MESH"])
    )


@pytest.mark.unit
def test_check_id_prefix_rules_reports_every_list_with_its_real_path(tmp_path, monkeypatch):
    config = check_config(gene_ids=["HGNC", "NCBIGene"], chemical_ids=["CHEBI"], taxon_ids=["NCBITaxon"])
    with pytest.raises(WorkflowError) as excinfo:
        load_snakefile(tmp_path, monkeypatch, CHECK_SNAKEFILE, config)
    message = str(excinfo.value)
    # The message names the configured directory (not a hard-coded "intermediate/..."), and the chemicals
    # list maps to the "chemicals" directory rather than "chemical".
    assert "gene_ids: no rule produces out/intermediate/gene/ids/<prefix> for NCBIGene" in message
    assert "taxon_ids: no rule produces out/intermediate/taxon/ids/<prefix> for NCBITaxon" in message
    assert "chemical_ids" not in message
    assert "HGNC" not in message


@pytest.mark.unit
def test_id_prefix_lists_match_config_yaml():
    # Every *_ids list in config.yaml should be checked, so a new semantic type isn't silently skipped.
    config_text = (get_repo_root() / "config.yaml").read_text()
    id_keys = {line.split(":", 1)[0] for line in config_text.splitlines() if line.split(":", 1)[0].endswith("_ids")}
    assert id_keys == set(ID_PREFIX_LISTS)


@pytest.mark.unit
def test_top_level_snakefile_runs_check_after_every_rule():
    # check_id_prefix_rules() only sees rules defined before it runs, so it must stay the last statement in the
    # top-level Snakefile, after every include.
    code_lines = [
        line
        for line in (get_repo_root() / "Snakefile").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert code_lines[-1] == "check_id_prefix_rules(workflow, config)"


# SAPBERT EXPORT FILE LIST


@pytest.mark.unit
def test_sapbert_export_leaves_out_geneproteinconflated():
    """With config.yaml as shipped, the SAPBERT export should write Gene, Protein and DrugChemicalConflated
    but not GeneProteinConflated, and should otherwise match the full synonym list in its order."""
    config = get_config()
    files = get_sapbert_training_synonyms(config)
    assert "GeneProteinConflated.txt" not in files
    assert {"Gene.txt", "Protein.txt", "DrugChemicalConflated.txt"} <= set(files)
    all_files = get_all_synonyms_with_drugchemicalconflated(config)
    assert files == [filename for filename in all_files if filename != "GeneProteinConflated.txt"]


@pytest.mark.unit
def test_sapbert_export_writes_every_file_when_nothing_is_excluded():
    """Emptying sapbert_excluded_synonym_outputs should bring GeneProteinConflated back into the export."""
    config = {**get_config(), "sapbert_excluded_synonym_outputs": []}
    assert get_sapbert_training_synonyms(config) == get_all_synonyms_with_drugchemicalconflated(config)


@pytest.mark.unit
def test_sapbert_export_rejects_an_exclusion_that_matches_no_file():
    """A misspelled exclusion should raise rather than export the file it was meant to leave out."""
    config = {**get_config(), "sapbert_excluded_synonym_outputs": ["GeneProteinConflated.txt.gz"]}
    with pytest.raises(ValueError, match="GeneProteinConflated.txt.gz"):
        get_sapbert_training_synonyms(config)
