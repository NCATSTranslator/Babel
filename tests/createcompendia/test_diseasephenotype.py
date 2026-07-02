"""
Unit tests for src/createcompendia/diseasephenotype.py.

Sections:

- ``# --- UMLS semantic-type tree mapping ---`` exercises the UMLS
  semantic-type-tree → Biolink category map that ``write_umls_ids`` hands to
  ``umls.write_umls_ids``. The map is built inline, so we capture it by mocking
  the downstream ``umls.write_umls_ids`` call rather than running a real MRSTY
  parse -- keeping these tests fast and offline.
- ``# --- MONDO_close parsing in compute_cliques_for_impact_report ---`` guards
  the 3-column ``MONDO_close`` concord reader against a column-count regression.
- ``# --- classify_disease_clique ---`` checks the per-clique biolink typing used
  by both the real build and the source-impact report.
- ``# --- write_phenotype_taxa ---`` checks the per-prefix taxa file (HP->human,
  MP->mammal) derived from a phenotype ids file.
- ``# --- split_mutually_exclusive_cliques (HP/MP disjointness) ---`` checks that a
  glommed clique holding both HP and MP is split (MP peeled out, HP side kept).
"""

from unittest.mock import patch

import pytest

from src.categories import DISEASE, PHENOTYPIC_FEATURE
from src.createcompendia import diseasephenotype
from tests.conftest import assert_taxa_file_valid, glom_dict_from_cliques

# --- UMLS semantic-type tree mapping ---


def _capture_umlsmap(tmp_path):
    """Run write_umls_ids with the downstream call mocked, returning the category map it built."""
    badumlsfile = tmp_path / "badumls.txt"
    badumlsfile.write_text("# no blocked CUIs\n")
    with patch.object(diseasephenotype.umls, "write_umls_ids") as mock_write:
        diseasephenotype.write_umls_ids(
            mrsty=str(tmp_path / "MRSTY.RRF"),  # never read: write_umls_ids is mocked
            outfile=str(tmp_path / "out"),
            badumlsfile=str(badumlsfile),
        )
    assert mock_write.call_count == 1, "expected diseasephenotype to delegate to umls.write_umls_ids exactly once"
    # umls.write_umls_ids(mrsty, category_map, outfile, ...): the map is the 2nd positional arg.
    return mock_write.call_args.args[1]


@pytest.mark.unit
def test_finding_and_lab_result_trees_are_not_claimed(tmp_path):
    """
    Regression guard for #569: the disease/phenotype compendium must NOT claim UMLS
    "Finding" (A2.2 / T033) or "Laboratory or Test Result" (A2.2.1 / T034). Leaving them
    unmapped is what lets them fall through to the leftover UMLS sweep, where STY_OVERRIDES
    re-types them (T033 → biolink:Phenomenon, T034 → biolink:ClinicalFinding). If either
    tree is re-added here the override never fires, so fail loudly.
    """
    umlsmap = _capture_umlsmap(tmp_path)
    assert "A2.2" not in umlsmap, 'A2.2 "Finding" (T033) must stay unclaimed so leftover re-types it -- see #569'
    assert "A2.2.1" not in umlsmap, (
        'A2.2.1 "Lab/Test Result" (T034) must stay unclaimed so leftover re-types it -- see #569'
    )


@pytest.mark.unit
def test_phenotype_trees_remain_claimed(tmp_path):
    """A2.2.2 (Sign or Symptom) and A2.3 (Organism Attribute) genuinely are phenotypic features."""
    umlsmap = _capture_umlsmap(tmp_path)
    assert umlsmap.get("A2.2.2") == PHENOTYPIC_FEATURE
    assert umlsmap.get("A2.3") == PHENOTYPIC_FEATURE


@pytest.mark.unit
def test_disease_trees_remain_claimed(tmp_path):
    """The core disease semantic-type trees must still map to biolink:Disease."""
    umlsmap = _capture_umlsmap(tmp_path)
    for tree in [
        "B2.2.1.2.1",
        "A1.2.2.1",
        "A1.2.2.2",
        "B2.3",
        "B2.2.1.2",
        "B2.2.1.2.1.1",
        "B2.2.1.2.2",
        "A1.2.2",
        "B2.2.1.2.1.2",
    ]:
        assert umlsmap.get(tree) == DISEASE, f"{tree} should map to {DISEASE}"


# --- MONDO_close parsing in compute_cliques_for_impact_report ---


def _write_lines(p, lines):
    """Write an iterable of strings to path ``p`` as newline-terminated rows."""
    p.write_text("".join(f"{line}\n" for line in lines))
    return str(p)


@pytest.mark.unit
def test_mondo_close_accepts_three_column_concord(tmp_path):
    """MONDO_close is a 3-column (subject, predicate, object) concord written by
    ubergraph.build_sets(); compute_cliques_for_impact_report() must parse it without
    raising. Regression guard: a reader that assumes 2 columns rejects every real row
    and aborts the whole disease build.
    """
    ids = _write_lines(tmp_path / "MONDO", [f"MONDO:0000001\t{DISEASE}"])
    mondoclose = _write_lines(
        tmp_path / "MONDO_close",
        [
            "MONDO:0000739\toio:closeMatch\tMEDDRA:10051962",
            "",  # blank line must be skipped, not crash
            "MONDO:0000740\toio:closeMatch\tMEDDRA:10001229",
        ],
    )

    dicts, types = diseasephenotype.compute_cliques_for_impact_report(
        concordances=[],
        identifiers=[ids],
        mondoclose=mondoclose,
        badxrefs={},
    )

    assert "MONDO:0000001" in dicts
    assert types["MONDO:0000001"] == DISEASE


@pytest.mark.unit
def test_mondo_close_rejects_malformed_row(tmp_path):
    """A MONDO_close row that is not exactly three tab-separated columns is malformed
    and must raise a clear RuntimeError rather than silently mis-parsing or hitting an
    IndexError deep inside glom.
    """
    ids = _write_lines(tmp_path / "MONDO", [f"MONDO:0000001\t{DISEASE}"])
    mondoclose = _write_lines(tmp_path / "MONDO_close", ["MONDO:0000739\tMEDDRA:10051962"])

    with pytest.raises(RuntimeError, match="not a valid MONDO_close entry"):
        diseasephenotype.compute_cliques_for_impact_report(
            concordances=[],
            identifiers=[ids],
            mondoclose=mondoclose,
            badxrefs={},
        )


# --- classify_disease_clique ---


@pytest.mark.unit
def test_classify_disease_clique_trusts_mondo_over_other_members():
    """A mixed clique containing a MONDO term should be typed from MONDO's declared type,
    regardless of what other members (e.g. an MP phenotype) declare. This is the case the
    MP impact report hit: a disease clique that an MP cross-reference expanded must still
    classify as biolink:Disease so the report picks MONDO (not DOID) as the preferred id."""
    clique = frozenset({"DOID:0050545", "MONDO:0018677", "HP:0030853", "MP:0004133"})
    types = {
        "MONDO:0018677": DISEASE,
        "HP:0030853": PHENOTYPIC_FEATURE,
        "MP:0004133": PHENOTYPIC_FEATURE,
        # DOID intentionally has no declared type to prove MONDO is what's trusted.
    }
    assert diseasephenotype.classify_disease_clique(clique, types) == DISEASE


@pytest.mark.unit
def test_classify_disease_clique_falls_through_to_hp_then_mp():
    """When no MONDO is present the classifier should trust HP next, then MP. A clique with
    only HP and MP members should take HP's declared type."""
    clique = frozenset({"HP:0001638", "MP:0005330"})
    types = {"HP:0001638": PHENOTYPIC_FEATURE, "MP:0005330": PHENOTYPIC_FEATURE}
    assert diseasephenotype.classify_disease_clique(clique, types) == PHENOTYPIC_FEATURE


@pytest.mark.unit
def test_classify_disease_clique_skips_trusted_prefix_with_missing_type():
    """If a trusted prefix's CURIE has no entry in the types map (concords out of sync),
    the classifier should fall through to the next trusted prefix rather than raising."""
    clique = frozenset({"MONDO:0000001", "HP:0001638"})
    types = {"HP:0001638": PHENOTYPIC_FEATURE}  # MONDO present but untyped
    assert diseasephenotype.classify_disease_clique(clique, types) == PHENOTYPIC_FEATURE


@pytest.mark.unit
def test_classify_disease_clique_majority_vote_breaks_ties_by_order():
    """With no trusted prefix present, the classifier should take a majority vote over
    declared types, breaking ties by the ``order`` list (DISEASE before PHENOTYPIC_FEATURE)."""
    clique = frozenset({"UMLS:C1", "UMLS:C2"})
    types = {"UMLS:C1": DISEASE, "UMLS:C2": PHENOTYPIC_FEATURE}  # 1-1 tie -> DISEASE wins
    assert diseasephenotype.classify_disease_clique(clique, types) == DISEASE


@pytest.mark.unit
def test_classify_disease_clique_returns_none_when_no_types():
    """A clique whose members are all absent from the types map should return None so the
    source-impact report can render it blank; create_typed_sets turns that None into a
    RuntimeError instead."""
    clique = frozenset({"FOO:1", "BAR:2"})
    assert diseasephenotype.classify_disease_clique(clique, {}) is None


@pytest.mark.unit
def test_create_typed_sets_drops_untypable_clique_with_warning(caplog):
    """create_typed_sets should skip (not crash on) a clique with no declared type for any
    member, logging a warning. The HP/MP split can strand such a clique (an identifier in a
    concord but absent from every ids file), and one stray must not abort the whole build."""
    import logging

    with caplog.at_level(logging.WARNING):
        typed_sets = diseasephenotype.create_typed_sets({frozenset({"FOO:1"})}, {})
    assert typed_sets == {}, "untypeable clique should be dropped, not emitted"
    assert any("untypeable" in r.message.lower() for r in caplog.records), "expected a warning about the dropped clique"


# --- write_phenotype_taxa ---


@pytest.mark.unit
def test_write_phenotype_taxa_assigns_taxon_to_every_id(tmp_path):
    """Every identifier in the ids file should get exactly one row mapping it to the given
    taxon, and the biolink-type column of the ids file should be dropped. This is how HP
    terms become NCBITaxon:9606 and MP terms NCBITaxon:40674 in the compendia."""
    idfile = tmp_path / "HP"
    idfile.write_text(f"HP:0000118\t{PHENOTYPIC_FEATURE}\nHP:0001234\t{PHENOTYPIC_FEATURE}\n")
    outfile = tmp_path / "taxa"
    diseasephenotype.write_phenotype_taxa(str(idfile), "NCBITaxon:9606", str(outfile))
    rows = assert_taxa_file_valid(str(outfile))
    assert rows == [["HP:0000118", "NCBITaxon:9606"], ["HP:0001234", "NCBITaxon:9606"]]


@pytest.mark.unit
def test_write_phenotype_taxa_skips_blank_lines(tmp_path):
    """A blank trailing line in the ids file must not produce a malformed taxa row."""
    idfile = tmp_path / "MP"
    idfile.write_text(f"MP:0000001\t{PHENOTYPIC_FEATURE}\n\n")
    outfile = tmp_path / "taxa"
    diseasephenotype.write_phenotype_taxa(str(idfile), "NCBITaxon:40674", str(outfile))
    assert outfile.read_text() == "MP:0000001\tNCBITaxon:40674\n"


@pytest.mark.unit
def test_write_phenotype_taxa_rejects_non_ncbitaxon(tmp_path):
    """A taxon that is not an NCBITaxon CURIE is a configuration error and must raise,
    rather than silently writing a malformed taxa file the TaxonFactory can't use."""
    idfile = tmp_path / "HP"
    idfile.write_text(f"HP:0000118\t{PHENOTYPIC_FEATURE}\n")
    with pytest.raises(ValueError, match="NCBITaxon"):
        diseasephenotype.write_phenotype_taxa(str(idfile), "9606", str(tmp_path / "taxa"))


# --- split_mutually_exclusive_cliques (HP/MP disjointness) ---


def _glom_dict(*cliques):
    """Varargs convenience wrapper over the shared glom_dict_from_cliques test helper."""
    return glom_dict_from_cliques(cliques)


@pytest.mark.unit
def test_split_separates_mp_from_hp_keeping_rest():
    """A clique holding HP, MP, and MONDO should split: HP and MONDO stay together (one
    shared object), MP is peeled into its own clique, and the two are distinct objects."""
    dicts = _glom_dict(["HP:0000118", "MP:0004133", "MONDO:0018677"])
    diseasephenotype.split_mutually_exclusive_cliques(dicts)
    assert dicts["HP:0000118"] == {"HP:0000118", "MONDO:0018677"}
    assert dicts["HP:0000118"] is dicts["MONDO:0018677"]
    assert dicts["MP:0004133"] == {"MP:0004133"}
    assert dicts["MP:0004133"] is not dicts["HP:0000118"]


@pytest.mark.unit
def test_split_leaves_mp_without_hp_untouched():
    """A clique with MP and MONDO but no HP should be left intact (MP may merge with non-HP
    disease ids); all members keep pointing at one shared, unchanged set."""
    dicts = _glom_dict(["MP:0002989", "MONDO:0005110"])
    diseasephenotype.split_mutually_exclusive_cliques(dicts)
    assert dicts["MP:0002989"] == {"MP:0002989", "MONDO:0005110"}
    assert dicts["MP:0002989"] is dicts["MONDO:0005110"]


@pytest.mark.unit
def test_split_leaves_pure_hp_clique_untouched():
    """A clique with HP and MONDO but no MP should be unchanged."""
    dicts = _glom_dict(["HP:0001638", "MONDO:0005110"])
    diseasephenotype.split_mutually_exclusive_cliques(dicts)
    assert dicts["HP:0001638"] == {"HP:0001638", "MONDO:0005110"}
    assert dicts["HP:0001638"] is dicts["MONDO:0005110"]


@pytest.mark.unit
def test_split_pulls_all_mp_ids_into_one_clique():
    """Every MP identifier in an HP-bearing clique should be peeled into a single MP clique,
    leaving HP plus any non-group members (e.g. MESH) behind."""
    dicts = _glom_dict(["HP:0001638", "MP:0010412", "MP:0011667", "MESH:D004694"])
    diseasephenotype.split_mutually_exclusive_cliques(dicts)
    assert dicts["MP:0010412"] == {"MP:0010412", "MP:0011667"}
    assert dicts["MP:0010412"] is dicts["MP:0011667"]
    assert dicts["HP:0001638"] == {"HP:0001638", "MESH:D004694"}


@pytest.mark.unit
def test_split_then_create_typed_sets_routes_mp_to_phenotypic_feature():
    """End-to-end build/report contract: after splitting an HP+MP+MONDO clique, create_typed_sets
    should route the peeled MP-only clique to PhenotypicFeature and keep the HP/MONDO clique as
    Disease (its pre-split type, since MONDO is trusted first)."""
    dicts = _glom_dict(["HP:0000118", "MP:0004133", "MONDO:0018677"])
    types = {
        "HP:0000118": PHENOTYPIC_FEATURE,
        "MP:0004133": PHENOTYPIC_FEATURE,
        "MONDO:0018677": DISEASE,
    }
    diseasephenotype.split_mutually_exclusive_cliques(dicts)
    typed_sets = diseasephenotype.create_typed_sets({frozenset(x) for x in dicts.values()}, types)
    assert frozenset({"MP:0004133"}) in typed_sets[PHENOTYPIC_FEATURE]
    assert frozenset({"HP:0000118", "MONDO:0018677"}) in typed_sets[DISEASE]
