"""Pipeline tests for UMLS identifier partitioning across compendia (issue #675 extension).

These tests verify that:
1. Each compendium's write_umls_ids() produces non-empty output.
2. No UMLS:CUI appears in more than one compendium output — the core invariant.
3. Chemicals excludes UMLS IDs assigned to the protein compendium
   (semantic type tree A1.4.1.2.1.7, Amino Acid/Peptide/Protein).

All tests require UMLS_API_KEY to be set and network access for the initial
download; they are skipped by default. Run with:
    PYTHONPATH=. uv run pytest tests/pipeline/test_umls_pipeline.py --pipeline --no-cov -v
"""
import pytest


COMPENDIUM_NAMES = [
    "chemicals",
    "protein",
    "anatomy",
    "diseasephenotype",
    "processactivity",
    "taxon",
    "gene",
]


def _read_ids(path: str) -> set[str]:
    """Read a TSV output file and return the set of CURIEs (first column)."""
    ids = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(line.split("\t")[0])
    return ids


@pytest.mark.pipeline
@pytest.mark.parametrize("name", COMPENDIUM_NAMES)
def test_umls_ids_non_empty(umls_pipeline_outputs, name):
    """Each compendium's write_umls_ids() must produce at least one identifier."""
    ids = _read_ids(umls_pipeline_outputs[name])
    assert len(ids) > 0, f"{name}.write_umls_ids() produced no output"


@pytest.mark.pipeline
def test_no_umls_id_in_multiple_compendia(umls_pipeline_outputs):
    """Core correctness test: no UMLS:CUI may appear in more than one compendium.

    If the same UMLS ID lands in two compendia, Node Normalization will see a
    duplicate and normalization will be ambiguous or incorrect.
    """
    seen = {}       # id -> first compendium name
    duplicates = {} # id -> list of all compendia it appeared in

    for name in COMPENDIUM_NAMES:
        for id_ in _read_ids(umls_pipeline_outputs[name]):
            if id_ in seen:
                duplicates.setdefault(id_, [seen[id_]]).append(name)
            else:
                seen[id_] = name

    assert len(duplicates) == 0, (
        f"Found {len(duplicates)} UMLS IDs in multiple compendia: "
        f"{dict(list(duplicates.items())[:5])}"
    )


@pytest.mark.pipeline
def test_chemicals_excludes_protein_semantic_tree(umls_pipeline_outputs):
    """Chemicals must not contain any UMLS IDs that the protein compendium claimed.

    Guards against amino-acid/peptide/protein entries (semantic type tree
    A1.4.1.2.1.7) leaking into the chemical compendium.
    """
    chem_ids = _read_ids(umls_pipeline_outputs["chemicals"])
    prot_ids = _read_ids(umls_pipeline_outputs["protein"])
    overlap = chem_ids & prot_ids
    assert len(overlap) == 0, (
        f"Found {len(overlap)} IDs in both chemicals and protein UMLS outputs: "
        f"{sorted(overlap)[:10]}"
    )
