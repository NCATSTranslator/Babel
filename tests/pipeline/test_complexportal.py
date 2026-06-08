"""ComplexPortal pipeline tests.

Downloads all ComplexPortal TSV files and verifies that labels, synonyms, and
taxa are extracted correctly.

Run with:
    uv run pytest tests/pipeline/test_complexportal.py --pipeline --no-cov -v
"""

import os

import pytest

from src.babel_utils import make_local_name
from src.datahandlers import complexportal
from src.prefixes import COMPLEXPORTAL
from tests.conftest import assert_labels_file_valid, assert_synonyms_file_valid
from tests.datahandlers.test_complexportal import _assert_descriptions_file_valid, _assert_taxa_file_valid
from tests.pipeline.conftest import _download_or_fail

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def complexportal_tsv_files():
    """Download all ComplexPortal TSV files; fail if unavailable."""
    manifest = make_local_name(complexportal.COMPLEXPORTAL_MANIFEST, subpath=COMPLEXPORTAL)
    return _download_or_fail(
        "ComplexPortal TSV files",
        complexportal.pull_complexportal,
        manifest,
    )


@pytest.fixture(scope="session")
def complexportal_pipeline_outputs(complexportal_tsv_files, regenerate):
    """Run ComplexPortal label/synonym/taxa extraction; returns {manifest, labels, synonyms, taxa} paths.

    Output files go to babel_downloads/ComplexPortal/.
    Reused on subsequent runs unless --regenerate is passed.
    """
    from src.util import get_config  # deferred: avoid config load at import time

    cfg = get_config()
    download_dir = os.path.join(cfg["download_directory"], COMPLEXPORTAL)
    manifest = os.path.join(download_dir, complexportal.COMPLEXPORTAL_MANIFEST)
    labels = os.path.join(download_dir, "labels")
    synonyms = os.path.join(download_dir, "synonyms")
    taxa = os.path.join(download_dir, "taxa")
    descriptions = os.path.join(download_dir, "descriptions")
    metadata = os.path.join(download_dir, "metadata.yaml")

    if (
        regenerate
        or not os.path.exists(labels)
        or not os.path.exists(synonyms)
        or not os.path.exists(taxa)
        or not os.path.exists(descriptions)
    ):
        os.makedirs(download_dir, exist_ok=True)
        complexportal.make_labels_synonyms_and_taxa(manifest, download_dir, labels, synonyms, taxa, descriptions, metadata)

    return {"manifest": manifest, "labels": labels, "synonyms": synonyms, "taxa": taxa, "descriptions": descriptions}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.pipeline
def test_complexportal_tsv_files_downloaded(complexportal_tsv_files):
    """Manifest file exists and lists at least one TSV."""
    assert os.path.exists(complexportal_tsv_files)
    with open(complexportal_tsv_files) as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) > 0, "Manifest is empty — no TSV files were downloaded"
    assert all(fn.endswith(".tsv") for fn in lines), f"Non-TSV entry in manifest: {lines}"


@pytest.mark.pipeline
def test_complexportal_tsv_header_columns(complexportal_tsv_files):
    """Verify the TSV column layout so we know which index holds the taxonomy field.

    This test is intentionally explicit about the expected column names so that
    any upstream format change is caught here rather than silently producing wrong output.
    """
    from src.util import get_config  # deferred

    cfg = get_config()
    download_dir = os.path.join(cfg["download_directory"], COMPLEXPORTAL)

    with open(complexportal_tsv_files) as mf:
        first_filename = next(line.strip() for line in mf if line.strip())

    tsv_path = os.path.join(download_dir, first_filename)
    with open(tsv_path) as f:
        header = f.readline().rstrip("\n").split("\t")

    # We care most about the columns Babel actually reads; assert their indices explicitly.
    assert header[0] == "#Complex ac", f"Column 0 is {header[0]!r}, expected '#Complex ac'"
    assert header[1] == "Recommended name", f"Column 1 is {header[1]!r}, expected 'Recommended name'"
    assert header[2] == "Aliases for complex", f"Column 2 is {header[2]!r}, expected 'Aliases for complex'"
    assert header[3] == "Taxonomy identifier", f"Column 3 is {header[3]!r}, expected 'Taxonomy identifier'"


@pytest.mark.pipeline
def test_complexportal_labels_valid(complexportal_pipeline_outputs):
    """Labels file is non-empty and every row is a valid CURIE→name pair."""
    rows = assert_labels_file_valid(complexportal_pipeline_outputs["labels"])
    assert all(row[0].startswith(f"{COMPLEXPORTAL}:") for row in rows), (
        "Some labels do not start with the ComplexPortal prefix"
    )


@pytest.mark.pipeline
def test_complexportal_synonyms_valid(complexportal_pipeline_outputs):
    """Synonyms file is non-empty and every row is a valid CURIE→predicate→synonym triple."""
    assert_synonyms_file_valid(complexportal_pipeline_outputs["synonyms"])


@pytest.mark.pipeline
def test_complexportal_taxa_valid(complexportal_pipeline_outputs):
    """Taxa file is non-empty and every row is a valid CURIE→NCBITaxon:NNNN pair."""
    rows = _assert_taxa_file_valid(complexportal_pipeline_outputs["taxa"])
    # Every label in the labels file should have at least one taxon entry.
    from tests.conftest import read_tsv

    label_curies = {row[0] for row in read_tsv(complexportal_pipeline_outputs["labels"])}
    taxa_curies = {row[0] for row in rows}
    missing = label_curies - taxa_curies
    assert not missing, f"{len(missing)} ComplexPortal identifiers have no taxon entry: {sorted(missing)[:10]}"


@pytest.mark.pipeline
def test_complexportal_descriptions_valid(complexportal_pipeline_outputs):
    """Descriptions file is non-empty and every row is a valid CURIE→description pair."""
    _assert_descriptions_file_valid(complexportal_pipeline_outputs["descriptions"])


@pytest.mark.pipeline
def test_complexportal_cross_file_duplicates_handled_correctly(complexportal_tsv_files, complexportal_pipeline_outputs):
    """Verify correct handling when the same CPX accession appears in multiple species TSV files.

    Labels: each CURIE appears exactly once (first-file wins).
    Synonyms: deduplicated by (CURIE, synonym) pair — no duplicate rows.
    Taxa: every (CURIE, taxon) pair from every file is preserved — a complex
          conserved across species should have one taxon entry per species.
    """
    from src.util import get_config  # deferred
    from tests.conftest import read_tsv

    cfg = get_config()
    download_dir = os.path.join(cfg["download_directory"], COMPLEXPORTAL)

    with open(complexportal_tsv_files) as mf:
        filenames = [line.strip() for line in mf if line.strip()]

    # Collect every (curie, taxon_id) pair seen across all source files.
    curie_to_files: dict[str, list[str]] = {}
    curie_taxon_pairs: set[tuple[str, str]] = set()
    for filename in filenames:
        tsv_path = os.path.join(download_dir, filename)
        with open(tsv_path) as f:
            next(f)  # skip header
            for line in f:
                cols = line.split("\t", 4)
                if len(cols) < 4:
                    continue
                curie = f"{COMPLEXPORTAL}:{cols[0]}"
                taxon_id = cols[3].strip()
                curie_to_files.setdefault(curie, []).append(filename)
                if taxon_id and taxon_id != "-":
                    curie_taxon_pairs.add((curie, taxon_id))

    cross_file_curies = {c for c, files in curie_to_files.items() if len(files) > 1}

    # Labels: every CURIE appears exactly once.
    label_rows = read_tsv(complexportal_pipeline_outputs["labels"])
    label_curies = [row[0] for row in label_rows]
    duplicate_labels = {c for c in label_curies if label_curies.count(c) > 1}
    assert not duplicate_labels, f"Duplicate label rows for: {sorted(duplicate_labels)[:10]}"

    # Synonyms: no duplicate (CURIE, synonym) rows.
    syn_rows = read_tsv(complexportal_pipeline_outputs["synonyms"])
    syn_pairs = [(row[0], row[2]) for row in syn_rows]
    duplicate_syns = {pair for pair in syn_pairs if syn_pairs.count(pair) > 1}
    assert not duplicate_syns, f"Duplicate synonym rows for: {sorted(duplicate_syns)[:5]}"

    # Taxa: every (CURIE, taxon) pair from the source files is present in the output.
    taxa_rows = read_tsv(complexportal_pipeline_outputs["taxa"])
    output_taxon_pairs = {(row[0], row[1].removeprefix("NCBITaxon:")) for row in taxa_rows}
    missing_pairs = curie_taxon_pairs - output_taxon_pairs
    assert not missing_pairs, (
        f"{len(missing_pairs)} (CURIE, taxon) pairs from source files are absent from taxa output: "
        f"{sorted(missing_pairs)[:5]}"
    )

    # Report how many cross-file CURIEs were found (informational, not a failure).
    if cross_file_curies:
        print(f"\n[info] {len(cross_file_curies)} CURIEs appear in multiple species files — all handled correctly.")  # noqa: T201
    else:
        print("\n[info] No CURIEs found in multiple species files in this ComplexPortal release.")  # noqa: T201
