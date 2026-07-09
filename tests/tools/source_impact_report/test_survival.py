"""Unit tests for the Biolink-prefix survival prediction in the source-impact report.

``prefix_survives`` mirrors ``NodeFactory.create_node``'s prefix filtering: an identifier
whose prefix is not in the Biolink Model ``id_prefixes`` for its biolink type is dropped by
``write_compendium``. These tests exercise the pure helper and the detail-file writers that
surface it (``would_be_added`` / ``needs_biolink_registration`` columns), using a
hand-built ``LookupContext`` so no Biolink network lookup is needed.

Test groups
-----------
- ``prefix_survives`` helper: registered, unregistered, unknown type, and case-insensitivity.
- ``new-cliques.csv`` survival columns: ``would_be_added``, ``needs_biolink_registration``,
  and ``unsupported_prefixes`` for pure-new cliques.
- ``modified-cliques.csv`` survival columns: per-added-identifier survival judged on the
  clique type, not the identifier's own declared type.
- ``modified-cliques.json`` detail: ``added_curie_details`` entries carry survival fields.
- No-lookup mode: survival columns are blank when ``prefix_priority_by_type`` is empty.
"""

import csv
import json

import pytest

from src.model.glom_diff import ExpandedClique, MergedClique, SourceImpactDiff
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
    """A prefix registered in the type's id_prefixes returns (True, False)."""
    assert prefix_survives("EMAPA:100", "biolink:AnatomicalEntity", PREFIX_PRIORITY) == (True, False)


@pytest.mark.unit
def test_prefix_survives_absent_needs_registration():
    """A prefix absent from the type's id_prefixes returns (False, True) — needs Biolink registration."""
    assert prefix_survives("EMAPA:100", "biolink:GrossAnatomicalStructure", PREFIX_PRIORITY) == (
        False,
        True,
    )


@pytest.mark.unit
def test_prefix_survives_unknown_type_or_empty_lookup():
    """Returns (None, False) when the type is unknown or the lookup map is empty (--no-biolink-lookup).

    The second element is never True in these cases to avoid false "needs registration" warnings.
    """
    assert prefix_survives("EMAPA:100", None, PREFIX_PRIORITY) == (None, False)
    assert prefix_survives("EMAPA:100", "biolink:AnatomicalEntity", {}) == (None, False)


@pytest.mark.unit
def test_prefix_survives_case_insensitive():
    """A lowercase CURIE prefix still matches an uppercased entry in the priority list."""
    assert prefix_survives("emapa:100", "biolink:AnatomicalEntity", PREFIX_PRIORITY) == (True, False)


def _lookup(types):
    """Build a ``LookupContext`` for the anatomy pipeline using *types* as the declared-type map.

    Uses the module-level ``PREFIX_PRIORITY`` and a classifier that picks the first type found
    by sorted CURIE order. Suitable for tests that do not need pipeline-specific classifier logic.
    """

    def classifier(clique, type_map):
        return next((type_map[c] for c in sorted(clique) if c in type_map), None)

    return LookupContext(
        types_by_pipeline={"anatomy": types},
        labels_by_prefix={},
        clique_classifier={"anatomy": classifier},
        prefix_priority_by_type=PREFIX_PRIORITY,
    )


@pytest.mark.unit
def test_new_cliques_csv_survival_columns(tmp_path):
    """``new-cliques.csv`` carries correct survival columns for registered and unregistered prefixes.

    EMAPA:100 is typed GrossAnatomicalStructure (EMAPA not in id_prefixes → dropped);
    EMAPA:300 is typed AnatomicalEntity (EMAPA registered → survives).
    """
    types = {
        "EMAPA:100": "biolink:GrossAnatomicalStructure",  # not registered -> dropped
        "EMAPA:300": "biolink:AnatomicalEntity",  # registered -> survives
    }
    diffs = {
        "anatomy": SourceImpactDiff(
            babel_pipeline="anatomy",
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
def test_modified_cliques_csv_survival_columns(tmp_path):
    """``modified-cliques.csv`` carries correct survival columns for identifiers joining existing cliques.

    EMAPA:100 joins a clique classified as GrossAnatomicalStructure (EMAPA not registered → dropped,
    biolink_registration_note populated); EMAPA:300 joins one classified as AnatomicalEntity (registered
    → survives). The UBERON members carry no declared type here, so the classifier falls back to the
    EMAPA term's type; the case where clique type diverges from own type is tested separately.
    """
    types = {
        "EMAPA:100": "biolink:GrossAnatomicalStructure",
        "EMAPA:300": "biolink:AnatomicalEntity",
    }
    diffs = {
        "anatomy": SourceImpactDiff(
            babel_pipeline="anatomy",
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
def test_modified_cliques_csv_judges_on_clique_type_not_own_type(tmp_path):
    """Survival is judged on the clique's Biolink type, not the identifier's own declared type.

    EMAPA:9 declares GrossAnatomicalStructure (where EMAPA is not registered), but joins a
    clique typed AnatomicalEntity (where EMAPA is registered). NodeFactory keeps EMAPA:9 because
    it uses the clique type, so ``would_be_added`` must be true with no false ``needs_biolink_registration``,
    even though checking the identifier's own type alone would flag it as dropped.
    """
    types = {
        "UBERON:0001": "biolink:AnatomicalEntity",
        "EMAPA:9": "biolink:GrossAnatomicalStructure",
    }

    # Mirror anatomy's classifier: trust the UBERON member's declared type for the clique.
    def classifier(clique, type_map):
        for curie in sorted(clique):
            if curie.startswith("UBERON:") and curie in type_map:
                return type_map[curie]
        return next((type_map[c] for c in sorted(clique) if c in type_map), None)

    lookup = LookupContext(
        types_by_pipeline={"anatomy": types},
        labels_by_prefix={},
        clique_classifier={"anatomy": classifier},
        prefix_priority_by_type=PREFIX_PRIORITY,
    )
    diffs = {
        "anatomy": SourceImpactDiff(
            babel_pipeline="anatomy",
            source_curies=frozenset({"EMAPA:9"}),
            expanded_cliques=[
                ExpandedClique(
                    before_clique=frozenset({"UBERON:0001"}),
                    added_source_curies=frozenset({"EMAPA:9"}),
                    after_clique=frozenset({"UBERON:0001", "EMAPA:9"}),
                ),
            ],
        )
    }
    path = tmp_path / "modified-cliques.csv"
    write_modified_cliques_csv(path, diffs, lookup)
    with path.open() as f:
        row = next(r for r in csv.DictReader(f) if r["added_id"] == "EMAPA:9")

    assert row["clique_biolink_type"] == "biolink:AnatomicalEntity"
    assert row["added_id_biolink_type"] == "biolink:GrossAnatomicalStructure"
    assert row["would_be_added"] == "true"
    assert row["needs_biolink_registration"] == "false"
    assert row["biolink_registration_note"] == ""


@pytest.mark.unit
def test_modified_cliques_json_added_curie_details(tmp_path):
    """``modified-cliques.json`` entries carry per-CURIE survival detail in ``added_curie_details``.

    Each entry records ``declared_biolink_type``, ``clique_biolink_type``, ``would_be_added``,
    ``needs_biolink_registration``, and ``note`` alongside the flat ``added_source_curies`` list
    retained for back-compat.
    """
    types = {"EMAPA:100": "biolink:GrossAnatomicalStructure"}
    diffs = {
        "anatomy": SourceImpactDiff(
            babel_pipeline="anatomy",
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
    # Own declared type is recorded for context; survival is judged on the clique type
    # (here the singleton-ish merge classifies as Gross too, so the term is dropped).
    assert detail["declared_biolink_type"] == "biolink:GrossAnatomicalStructure"
    assert detail["clique_biolink_type"] == "biolink:GrossAnatomicalStructure"
    assert detail["would_be_added"] is False
    assert detail["needs_biolink_registration"] is True
    assert detail["note"]


@pytest.mark.unit
def test_survival_columns_blank_without_biolink_lookup(tmp_path):
    """Survival columns exist but are blank when ``prefix_priority_by_type`` is empty (``--no-biolink-lookup``).

    An empty priority map simulates running without a Biolink lookup. The columns must be present
    in the CSV but contain empty strings, and ``needs_biolink_registration`` must never be ``true``.
    """
    types = {"EMAPA:100": "biolink:GrossAnatomicalStructure"}
    lookup = LookupContext(
        types_by_pipeline={"anatomy": types},
        clique_classifier={"anatomy": lambda clique, tm: next(iter(tm.values()), None)},
        prefix_priority_by_type={},
    )
    diffs = {
        "anatomy": SourceImpactDiff(
            babel_pipeline="anatomy",
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
