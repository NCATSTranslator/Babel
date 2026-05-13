"""Unit tests for compute_disease_cliques().

The function under test is the pure clique-formation step extracted from
``build_compendium`` in ``src/createcompendia/diseasephenotype.py``. The same
function is called by the development-time simulation in
``tests/pipeline/checks/test_disease.py``, so verifying its behaviour on a
synthetic fixture protects both call sites.
"""

import pytest

from src.categories import DISEASE, PHENOTYPIC_FEATURE
from src.createcompendia.diseasephenotype import compute_disease_cliques


def _write(directory, name, rows):
    """Write a tab-separated fixture file and return its path.

    The concord-processing code in compute_disease_cliques() uses path.basename(infile) to look
    up badxrefs and to decide whether remove_overused_xrefs applies, so concord files MUST be
    named exactly ``MONDO``, ``HP``, ``EFO``, etc. To keep that property while also having
    same-named identifier files, callers pass distinct directories for ids and concords.
    """
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / name
    p.write_text("".join("\t".join(row) + "\n" for row in rows))
    return str(p)


@pytest.mark.unit
def test_compute_disease_cliques_basic_merge(tmp_path):
    """A two-row concord file merges three identifiers into one disease clique."""
    ids_dir = tmp_path / "ids"
    concords_dir = tmp_path / "concords"
    mondo_ids = _write(ids_dir, "MONDO", [("MONDO:0011479", DISEASE)])
    umls_ids = _write(ids_dir, "UMLS", [("UMLS:C2930833", DISEASE)])
    doid_ids = _write(ids_dir, "DOID", [("DOID:0050722", DISEASE)])

    mondo_concord = _write(
        concords_dir,
        "MONDO",
        [
            ("MONDO:0011479", "oio:exactMatch", "UMLS:C2930833"),
            ("MONDO:0011479", "oio:exactMatch", "DOID:0050722"),
        ],
    )
    mondo_close = _write(concords_dir, "MONDO_close", [])  # empty close-mondo file

    typed_sets = compute_disease_cliques(
        concordances=[mondo_concord],
        identifiers=[mondo_ids, umls_ids, doid_ids],
        mondoclose=mondo_close,
        badxrefs={},
    )

    assert DISEASE in typed_sets
    cliques = typed_sets[DISEASE]
    # Exactly one clique containing all three identifiers.
    matching = [c for c in cliques if "MONDO:0011479" in c]
    assert len(matching) == 1
    assert matching[0] == frozenset({"MONDO:0011479", "UMLS:C2930833", "DOID:0050722"})


@pytest.mark.unit
def test_compute_disease_cliques_types_disease_and_phenotype(tmp_path):
    """A MONDO clique types as Disease; a separate HP clique types as PhenotypicFeature."""
    ids_dir = tmp_path / "ids"
    concords_dir = tmp_path / "concords"
    mondo_ids = _write(ids_dir, "MONDO", [("MONDO:0005578", DISEASE)])
    doid_ids = _write(ids_dir, "DOID", [("DOID:848", DISEASE)])
    hp_ids = _write(ids_dir, "HP", [("HP:0001508", PHENOTYPIC_FEATURE)])
    umls_ids = _write(ids_dir, "UMLS", [("UMLS:C4531021", PHENOTYPIC_FEATURE)])

    mondo_concord = _write(
        concords_dir,
        "MONDO",
        [("MONDO:0005578", "oio:exactMatch", "DOID:848")],
    )
    hp_concord = _write(
        concords_dir,
        "HP",
        [("HP:0001508", "oio:exactMatch", "UMLS:C4531021")],
    )
    mondo_close = _write(concords_dir, "MONDO_close", [])

    typed_sets = compute_disease_cliques(
        concordances=[mondo_concord, hp_concord],
        identifiers=[mondo_ids, doid_ids, hp_ids, umls_ids],
        mondoclose=mondo_close,
        badxrefs={},
    )

    disease_cliques = typed_sets.get(DISEASE, set())
    phenotype_cliques = typed_sets.get(PHENOTYPIC_FEATURE, set())

    assert frozenset({"MONDO:0005578", "DOID:848"}) in disease_cliques
    assert frozenset({"HP:0001508", "UMLS:C4531021"}) in phenotype_cliques


@pytest.mark.unit
def test_compute_disease_cliques_badxrefs_blocks_merge(tmp_path):
    """A pair listed in badxrefs is dropped before glom; the clique stays split."""
    ids_dir = tmp_path / "ids"
    concords_dir = tmp_path / "concords"
    mondo_ids = _write(ids_dir, "MONDO", [("MONDO:0011479", DISEASE)])
    umls_ids = _write(ids_dir, "UMLS", [("UMLS:C2930833", DISEASE)])
    mondo_concord = _write(
        concords_dir,
        "MONDO",
        [("MONDO:0011479", "oio:exactMatch", "UMLS:C2930833")],
    )
    bad_mondo = tmp_path / "bad_mondo.txt"
    bad_mondo.write_text("MONDO:0011479 UMLS:C2930833\n")
    mondo_close = _write(concords_dir, "MONDO_close", [])

    typed_sets = compute_disease_cliques(
        concordances=[mondo_concord],
        identifiers=[mondo_ids, umls_ids],
        mondoclose=mondo_close,
        badxrefs={"MONDO": str(bad_mondo)},
    )

    cliques = typed_sets.get(DISEASE, set())
    mondo_clique = next(c for c in cliques if "MONDO:0011479" in c)
    assert "UMLS:C2930833" not in mondo_clique
