"""Unit tests for the Biolink-prefix survival prediction in the source-impact report.

``prefix_survives`` mirrors ``NodeFactory.create_node``'s prefix filtering: an identifier
whose prefix is not in the Biolink Model ``id_prefixes`` for its biolink type is dropped by
``write_compendium``. These tests exercise the pure helper and the detail-file writers that
surface it (``would_be_added`` / ``needs_biolink_registration`` columns), using a
hand-built ``LookupContext`` so no Biolink network lookup is needed.
"""

import csv
import json

import pytest

from src.model.clique_diff import ExpandedClique, MergedClique, SourceImpactDiff
from src.reports.source_impact import LookupContext, prefix_survives
from src.reports.source_impact_details import (
    write_modified_cliques_csv,
    write_modified_cliques_json,
    write_new_cliques_csv,
)

# EMAPA is registered for AnatomicalEntity but NOT for GrossAnatomicalStructure, so a
# gross-typed EMAPA term must be flagged as needing Biolink registration.
PREFIX_PRIORITY = {
    "biolink:AnatomicalEntity": ["UBERON", "EMAPA", "GO"],
    "biolink:GrossAnatomicalStructure": ["UBERON"],
}


@pytest.mark.unit
def test_prefix_survives_present():
    assert prefix_survives("EMAPA:100", "biolink:AnatomicalEntity", PREFIX_PRIORITY) == (True, False)


@pytest.mark.unit
def test_prefix_survives_absent_needs_registration():
    assert prefix_survives("EMAPA:100", "biolink:GrossAnatomicalStructure", PREFIX_PRIORITY) == (
        False,
        True,
    )


@pytest.mark.unit
def test_prefix_survives_unknown_type_or_empty_lookup():
    # No declared type, or an empty priority map (e.g. --no-biolink-lookup): unknown, never
    # a false "needs registration".
    assert prefix_survives("EMAPA:100", None, PREFIX_PRIORITY) == (None, False)
    assert prefix_survives("EMAPA:100", "biolink:AnatomicalEntity", {}) == (None, False)


@pytest.mark.unit
def test_prefix_survives_case_insensitive():
    # Lowercase CURIE prefix still matches the uppercased priority list.
    assert prefix_survives("emapa:100", "biolink:AnatomicalEntity", PREFIX_PRIORITY) == (True, False)


def _lookup(types):
    """A LookupContext with the test prefix priorities and a simple declared-type classifier."""

    def classifier(clique, type_map):
        return next((type_map[c] for c in sorted(clique) if c in type_map), None)

    return LookupContext(
        types_by_semantic_type={"anatomy": types},
        labels_by_prefix={},
        clique_classifier={"anatomy": classifier},
        prefix_priority_by_type=PREFIX_PRIORITY,
    )


@pytest.mark.unit
def test_new_cliques_csv_survival_columns(tmp_path):
    types = {
        "EMAPA:100": "biolink:GrossAnatomicalStructure",  # not registered -> dropped
        "EMAPA:300": "biolink:AnatomicalEntity",  # registered -> survives
    }
    diffs = {
        "anatomy": SourceImpactDiff(
            semantic_type="anatomy",
            source_curies=frozenset({"EMAPA:100", "EMAPA:300"}),
            pure_new_cliques=[frozenset({"EMAPA:100"}), frozenset({"EMAPA:300"})],
        )
    }
    path = tmp_path / "new-cliques.csv"
    write_new_cliques_csv(path, diffs, _lookup(types))
    with path.open() as f:
        rows = {r["preferred_id"]: r for r in csv.DictReader(f)}

    assert rows["EMAPA:100"]["preferred_id_would_survive"] == "false"
    assert rows["EMAPA:100"]["needs_biolink_registration"] == "true"
    assert rows["EMAPA:100"]["unsupported_prefixes"] == "EMAPA"

    assert rows["EMAPA:300"]["preferred_id_would_survive"] == "true"
    assert rows["EMAPA:300"]["needs_biolink_registration"] == "false"
    assert rows["EMAPA:300"]["unsupported_prefixes"] == ""


@pytest.mark.unit
def test_modified_cliques_csv_judges_on_own_type(tmp_path):
    # EMAPA:100 (gross, unregistered) is added to a UBERON clique; EMAPA:300 (anatomical,
    # registered) is added to another. Survival is judged on each identifier's OWN type.
    types = {
        "EMAPA:100": "biolink:GrossAnatomicalStructure",
        "EMAPA:300": "biolink:AnatomicalEntity",
    }
    diffs = {
        "anatomy": SourceImpactDiff(
            semantic_type="anatomy",
            source_curies=frozenset({"EMAPA:100", "EMAPA:300"}),
            expanded_cliques=[
                ExpandedClique(
                    before_clique=frozenset({"UBERON:0001"}),
                    added_source_curies=frozenset({"EMAPA:100"}),
                    after_clique=frozenset({"UBERON:0001", "EMAPA:100"}),
                ),
                ExpandedClique(
                    before_clique=frozenset({"UBERON:0002"}),
                    added_source_curies=frozenset({"EMAPA:300"}),
                    after_clique=frozenset({"UBERON:0002", "EMAPA:300"}),
                ),
            ],
        )
    }
    path = tmp_path / "modified-cliques.csv"
    write_modified_cliques_csv(path, diffs, _lookup(types))
    with path.open() as f:
        rows = {r["added_id"]: r for r in csv.DictReader(f)}

    assert rows["EMAPA:100"]["added_id_biolink_type"] == "biolink:GrossAnatomicalStructure"
    assert rows["EMAPA:100"]["would_be_added"] == "false"
    assert rows["EMAPA:100"]["needs_biolink_registration"] == "true"
    assert "id_prefixes for biolink:GrossAnatomicalStructure" in rows["EMAPA:100"]["biolink_registration_note"]

    assert rows["EMAPA:300"]["would_be_added"] == "true"
    assert rows["EMAPA:300"]["needs_biolink_registration"] == "false"
    assert rows["EMAPA:300"]["biolink_registration_note"] == ""


@pytest.mark.unit
def test_modified_cliques_json_added_curie_details(tmp_path):
    types = {"EMAPA:100": "biolink:GrossAnatomicalStructure"}
    diffs = {
        "anatomy": SourceImpactDiff(
            semantic_type="anatomy",
            source_curies=frozenset({"EMAPA:100"}),
            merged_cliques=[
                MergedClique(
                    before_cliques=(frozenset({"UBERON:0001"}), frozenset({"UBERON:0002"})),
                    source_curies_involved=frozenset({"EMAPA:100"}),
                    after_clique=frozenset({"UBERON:0001", "UBERON:0002", "EMAPA:100"}),
                )
            ],
        )
    }
    path = tmp_path / "modified-cliques.json"
    write_modified_cliques_json(path, diffs, _lookup(types))
    entries = json.loads(path.read_text())

    assert len(entries) == 1
    # Back-compat flat list is retained.
    assert entries[0]["added_source_curies"] == ["EMAPA:100"]
    detail = entries[0]["added_curie_details"][0]
    assert detail["i"] == "EMAPA:100"
    assert detail["biolink_type"] == "biolink:GrossAnatomicalStructure"
    assert detail["would_be_added"] is False
    assert detail["needs_biolink_registration"] is True
    assert detail["note"]


@pytest.mark.unit
def test_survival_columns_blank_without_biolink_lookup(tmp_path):
    # An empty prefix_priority_by_type stands in for --no-biolink-lookup: the columns must
    # exist but be blank, with no false "needs registration".
    types = {"EMAPA:100": "biolink:GrossAnatomicalStructure"}
    lookup = LookupContext(
        types_by_semantic_type={"anatomy": types},
        clique_classifier={"anatomy": lambda clique, tm: next(iter(tm.values()), None)},
        prefix_priority_by_type={},
    )
    diffs = {
        "anatomy": SourceImpactDiff(
            semantic_type="anatomy",
            source_curies=frozenset({"EMAPA:100"}),
            pure_new_cliques=[frozenset({"EMAPA:100"})],
        )
    }
    path = tmp_path / "new-cliques.csv"
    write_new_cliques_csv(path, diffs, lookup)
    with path.open() as f:
        row = next(csv.DictReader(f))
    assert row["preferred_id_would_survive"] == ""
    assert row["needs_biolink_registration"] == ""
    assert row["unsupported_prefixes"] == ""
