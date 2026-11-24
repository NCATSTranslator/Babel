"""Pipeline tests for the Plant Ontology ingest: its ids file, and its name-match concord checked against
the curated mappings in docs/sources/PO/curation/."""

import csv

import pytest

from src.categories import CELL, GROSS_ANATOMICAL_STRUCTURE
from src.createcompendia import anatomy
from src.model.intermediates import read_concords
from src.util import get_repo_root
from tests.pipeline.conftest import _intermediate_concord_path

CURATION_DIR = get_repo_root() / "docs" / "sources" / "PO" / "curation"

# Pairs the name rule writes that the curator decided differently. Each is a judgement the rule cannot
# make from a name; docs/sources/PO/mappings.md discusses them. A pair appearing here that the rule no
# longer writes, or a new disagreement, fails the test: review it and update this list.
KNOWN_DISAGREEMENTS = {
    # NCIt "Blade" is the leaf blade; the curator chose PO:0020039 "leaf lamina" over the generic lamina.
    ("NCIT:C79619", "PO:0025060"),
    # NCIt "Stalk" is "Caulis Principalis", the main stem; the curator chose no mapping.
    ("NCIT:C79690", "PO:0025066"),
    # NCIt "Fiber" has no definition; the curator left it out of anatomy as a product (dietary fiber), but
    # the plant-part rule takes it and PO:0025407 "plant fiber cell" has "fiber" as an exact synonym.
    ("NCIT:C1502", "PO:0025407"),
}


def _curated(filename, key):
    with open(CURATION_DIR / filename, newline="") as inf:
        return {row[key]: row["po"] for row in csv.DictReader(inf, delimiter="\t")}


@pytest.mark.pipeline
def test_po_ids_are_plant_structures_and_cells(po_pipeline_outputs):
    """ids/PO should hold only PO terms, typed GrossAnatomicalStructure or Cell (the two classes Biolink
    registers PO for), and none from the two branches ANATOMY_OBO_SOURCES leaves out."""
    with open(po_pipeline_outputs["anatomy"]) as inf:
        rows = [line.rstrip("\n").split("\t") for line in inf]

    assert len(rows) > 1000, f"expected over a thousand PO anatomy terms, got {len(rows)}"
    assert all(curie.startswith("PO:") for curie, _ in rows)
    assert {biolink_type for _, biolink_type in rows} == {GROSS_ANATOMICAL_STRUCTURE, CELL}
    curies = {curie for curie, _ in rows}
    assert "PO:0025538" not in curies  # "plant sap", under PO:0025161 "portion of plant substance"
    assert "PO:0025117" not in curies  # "plant anatomical space"


@pytest.mark.pipeline
def test_po_concord_agrees_with_the_curated_mappings(po_pipeline_outputs):
    """The name-match concord should be one-to-one within each vocabulary and should not contradict the
    curated PO mappings, apart from KNOWN_DISAGREEMENTS.

    The curation is the rule's validation set, not its input: a curated pair the rule misses is fine (the
    names differ), but a pair it writes for a curated term must be the curated one. The lower bounds
    guard against the rule quietly matching almost nothing: a local build in November 2026 agreed on 31
    MeSH and 40 NCIt pairs.
    """
    _ = po_pipeline_outputs
    rows = list(read_concords(_intermediate_concord_path("anatomy", "PO")))

    assert {predicate for _, predicate, _ in rows} == {anatomy.PO_LABEL_MATCH_PREDICATE}
    assert all(po.startswith("PO:") for po, _, _ in rows)
    for prefix in ("MESH:", "NCIT:"):
        pairs = [(po, other) for po, _, other in rows if other.startswith(prefix)]
        assert len({po for po, _ in pairs}) == len(pairs), f"a PO term is paired with two {prefix} terms"
        assert len({other for _, other in pairs}) == len(pairs), f"a {prefix} term is paired with two PO terms"

    curated = _curated("po_mesh.tsv", "mesh") | _curated("po_ncit.tsv", "ncit")
    written = {other: po for po, _, other in rows}
    agreements = {(other, po) for other, po in written.items() if curated.get(other) == po}
    disagreements = {(other, po) for other, po in written.items() if other in curated and curated[other] != po}

    assert disagreements == KNOWN_DISAGREEMENTS
    assert sum(other.startswith("MESH:") for other, _ in agreements) >= 28
    assert sum(other.startswith("NCIT:") for other, _ in agreements) >= 35


@pytest.mark.pipeline
def test_ncit_plant_part_rule_takes_every_curated_plant_part(ncit_pipeline_outputs):
    """Every NCIt plant part the curator kept, bar the branch root, should be in the anatomy ids/NCIT, and
    the rule should not pull in the materials the UNII annotation marks.

    The rule (no FDA UNII, Semantic_Type "Plant") was chosen because it reproduces a term-by-term review of
    the branch; this is that comparison. NCIT:C79611 "Plant Part" itself is typed "Classification", so
    the rule leaves it out.
    """
    with open(ncit_pipeline_outputs["anatomy"]) as inf:
        anatomy_ncit = {line.split("\t")[0] for line in inf}
    with open(CURATION_DIR / "po_ncit.tsv", newline="") as inf:
        kept = {row["ncit"] for row in csv.DictReader(inf, delimiter="\t") if row["in_anatomy"] == "yes"}

    assert kept - anatomy_ncit == {anatomy.NCIT_PLANT_PART_ROOT}
    assert "NCIT:C29250" not in anatomy_ncit  # "Psyllium Husk": has a UNII
    assert "NCIT:C80312" not in anatomy_ncit  # "Acer negundo Pollen": has a UNII
