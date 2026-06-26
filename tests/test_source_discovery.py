"""Unit tests for src/model/source.py.

Test groups
-----------
scan_concords_for_curies:
    Row-matching and asserter-recording logic. Key behaviours: matches either endpoint
    of a concord triple; records the file path relative to concords_dir as the asserter;
    skips metadata sidecars; recurses into subdirectories (e.g. UNICHEM/*).

discover_source — structure:
    The four axes a source can vary along — single vs multi babel_pipeline, single vs
    multi biolink_type within one pipeline, single vs multi prefix — each verified with a
    minimal fixture tree.

discover_source — edge cases:
    Missing source name, missing intermediate root, and metadata sidecar filtering.
"""

import pytest

from src.model.source import discover_source, scan_concords_for_curies

# ---------------------------------------------------------------------------
# scan_concords_for_curies
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scan_concords_for_curies_matches_either_endpoint_and_records_asserter(tmp_path):
    concords = tmp_path / "anatomy" / "concords"
    concords.mkdir(parents=True)
    # EMAPA's own concord is empty; its xrefs live in UBERON's concord.
    (concords / "EMAPA").write_text("")
    (concords / "UBERON").write_text(
        "UBERON:1\txref\tEMAPA:10\n"  # source CURIE on the object side
        "EMAPA:20\tskos:exactMatch\tCL:2\n"  # source CURIE on the subject side
        "UBERON:3\txref\tCL:4\n"  # no source CURIE — skipped
    )
    # Metadata sidecars must be ignored.
    (concords / "metadata-UBERON.yaml").write_text("UBERON:1\txref\tEMAPA:10\n")

    rows = scan_concords_for_curies(concords, {"EMAPA:10", "EMAPA:20"})

    assert ("UBERON:1", "xref", "EMAPA:10", "UBERON") in rows
    assert ("EMAPA:20", "skos:exactMatch", "CL:2", "UBERON") in rows
    assert all(r[3] == "UBERON" for r in rows), "asserted_by is the concord file path relative to concords_dir"
    assert not any("UBERON:3" in r for r in rows), "rows without a source CURIE are dropped"
    assert len(rows) == 2


@pytest.mark.unit
def test_scan_concords_for_curies_missing_dir_returns_empty(tmp_path):
    assert scan_concords_for_curies(tmp_path / "nope", {"EMAPA:1"}) == []


# ---------------------------------------------------------------------------
# discover_source — structure
# ---------------------------------------------------------------------------


def _make_source_tree(root, source_name, semantic_type, ids_lines=None, concord_lines=None):
    """Write minimal ids/ and concords/ files under ``root/<semantic_type>/`` for one source."""
    ids_dir = root / semantic_type / "ids"
    concords_dir = root / semantic_type / "concords"
    ids_dir.mkdir(parents=True, exist_ok=True)
    concords_dir.mkdir(parents=True, exist_ok=True)
    if ids_lines is not None:
        (ids_dir / source_name).write_text("\n".join(ids_lines) + "\n")
    if concord_lines is not None:
        (concords_dir / source_name).write_text("\n".join(concord_lines) + "\n")


@pytest.mark.unit
def test_discover_single_prefix_single_type_single_semantic_type(tmp_path):
    """Baseline: one source, one babel_pipeline, one biolink_type, one prefix."""
    _make_source_tree(
        tmp_path,
        "EMAPA",
        "anatomy",
        ids_lines=["EMAPA:1\tbiolink:AnatomicalEntity", "EMAPA:2\tbiolink:AnatomicalEntity"],
        concord_lines=["EMAPA:1\txref\tUBERON:1"],
    )

    contrib = discover_source("EMAPA", tmp_path)

    assert contrib.semantic_types == frozenset({"anatomy"})
    assert contrib.prefixes == frozenset({"EMAPA"})
    assert contrib.declared_biolink_types == frozenset({"biolink:AnatomicalEntity"})
    assert contrib.total_identifier_count == 2
    assert contrib.total_concord_row_count == 1

    stc = contrib.by_semantic_type["anatomy"]
    assert stc.declared_type_counts == {"biolink:AnatomicalEntity": 2}
    assert stc.concord_partner_prefix_counts == {"UBERON": 1}


@pytest.mark.unit
def test_discover_multi_biolink_type_within_one_semantic_type(tmp_path):
    """An ids file may mix biolink types in its second column — UBERON does this with
    AnatomicalEntity and GrossAnatomicalStructure."""
    _make_source_tree(
        tmp_path,
        "UBERON",
        "anatomy",
        ids_lines=[
            "UBERON:1\tbiolink:AnatomicalEntity",
            "UBERON:2\tbiolink:GrossAnatomicalStructure",
            "UBERON:3\tbiolink:AnatomicalEntity",
        ],
    )

    contrib = discover_source("UBERON", tmp_path)

    assert contrib.declared_biolink_types == frozenset({"biolink:AnatomicalEntity", "biolink:GrossAnatomicalStructure"})
    stc = contrib.by_semantic_type["anatomy"]
    assert stc.declared_type_counts == {
        "biolink:AnatomicalEntity": 2,
        "biolink:GrossAnatomicalStructure": 1,
    }


@pytest.mark.unit
def test_discover_multi_semantic_type(tmp_path):
    """MESH-style source present in two babel_pipeline directories (anatomy and chemical)."""
    _make_source_tree(
        tmp_path,
        "MESH",
        "anatomy",
        ids_lines=["MESH:A1\tbiolink:AnatomicalEntity"],
    )
    _make_source_tree(
        tmp_path,
        "MESH",
        "chemical",
        ids_lines=["MESH:C1\tbiolink:ChemicalEntity", "MESH:C2\tbiolink:ChemicalEntity"],
    )

    contrib = discover_source("MESH", tmp_path)

    assert contrib.semantic_types == frozenset({"anatomy", "chemical"})
    assert contrib.total_identifier_count == 3
    assert contrib.declared_biolink_types == frozenset({"biolink:AnatomicalEntity", "biolink:ChemicalEntity"})
    assert len(contrib.by_semantic_type["anatomy"].all_curies) == 1
    assert len(contrib.by_semantic_type["chemical"].all_curies) == 2


# ---------------------------------------------------------------------------
# discover_source — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_discover_multi_prefix(tmp_path):
    """A source may write rows under more than one prefix."""
    _make_source_tree(
        tmp_path,
        "WEIRD",
        "anatomy",
        ids_lines=[
            "PREFIXA:1\tbiolink:AnatomicalEntity",
            "PREFIXB:1\tbiolink:AnatomicalEntity",
        ],
    )

    contrib = discover_source("WEIRD", tmp_path)

    assert contrib.prefixes == frozenset({"PREFIXA", "PREFIXB"})
    stc = contrib.by_semantic_type["anatomy"]
    assert {p: len(c) for p, c in stc.curies_by_prefix.items()} == {
        "PREFIXA": 1,
        "PREFIXB": 1,
    }


@pytest.mark.unit
def test_discover_missing_source_returns_empty_contribution(tmp_path):
    """A source name with no ids or concords files anywhere returns an empty contribution."""
    (tmp_path / "anatomy" / "ids").mkdir(parents=True)
    (tmp_path / "anatomy" / "concords").mkdir(parents=True)

    contrib = discover_source("NONEXISTENT", tmp_path)
    assert contrib.by_semantic_type == {}
    assert contrib.semantic_types == frozenset()
    assert contrib.total_identifier_count == 0


@pytest.mark.unit
def test_discover_raises_when_intermediate_root_missing(tmp_path):
    """Passing a non-existent intermediate root raises FileNotFoundError rather than silently returning empty."""
    with pytest.raises(FileNotFoundError):
        discover_source("EMAPA", tmp_path / "missing")


@pytest.mark.unit
def test_scan_concords_for_curies_recurses_into_subdirectories(tmp_path):
    """Concord files in subdirectories (e.g. chemicals/concords/UNICHEM/UNICHEM_*) must be
    scanned; asserted_by should be the relative path from concords_dir."""
    concords = tmp_path / "chemicals" / "concords"
    unichem_dir = concords / "UNICHEM"
    unichem_dir.mkdir(parents=True)
    (unichem_dir / "UNICHEM_7").write_text("PUBCHEM.COMPOUND:1\txref\tCHEMBL.COMPOUND:2\n")
    (unichem_dir / "UNICHEM_22").write_text("PUBCHEM.COMPOUND:1\txref\tCHEBI:999\n")
    # Metadata sidecars in subdirectories are also skipped.
    (unichem_dir / "metadata-UNICHEM_7.yaml").write_text("name: unichem\n")

    rows = scan_concords_for_curies(concords, {"PUBCHEM.COMPOUND:1"})

    assert len(rows) == 2
    asserters = {r[3] for r in rows}
    assert asserters == {"UNICHEM/UNICHEM_7", "UNICHEM/UNICHEM_22"}


@pytest.mark.unit
def test_discover_skips_metadata_yaml_files(tmp_path):
    """discover_source should only treat files literally named <SOURCE>, not metadata-* siblings."""
    concord_dir = tmp_path / "anatomy" / "concords"
    concord_dir.mkdir(parents=True)
    (concord_dir / "EMAPA").write_text("EMAPA:1\txref\tUBERON:1\n")
    (concord_dir / "metadata-EMAPA.yaml").write_text("name: build_anatomy_obo_relationships()\n")
    (tmp_path / "anatomy" / "ids").mkdir(parents=True)

    contrib = discover_source("EMAPA", tmp_path)
    assert contrib.semantic_types == frozenset({"anatomy"})
    assert contrib.total_concord_row_count == 1
