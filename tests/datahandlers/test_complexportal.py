from unittest.mock import patch

import pytest

from src.datahandlers import complexportal
from src.datahandlers.complexportal import COMPLEXTAB_COLUMNS, COMPLEXTAB_HEADER
from src.predicates import HAS_EXACT_SYNONYM
from src.prefixes import COMPLEXPORTAL
from tests.conftest import (
    assert_descriptions_file_valid,
    assert_ids_file_valid,
    assert_labels_file_valid,
    assert_synonyms_file_valid,
    assert_taxa_file_valid,
)


class _FakeResponse:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.content


def _row(ac, name, aliases, taxon, description="-"):
    """Build a ComplexTAB test row with only the Babel-read columns set; all others are '-'."""
    values = ["-"] * len(COMPLEXTAB_COLUMNS)
    values[0] = ac
    values[1] = name
    values[2] = aliases
    values[3] = taxon
    values[9] = description
    return "\t".join(values) + "\n"


@pytest.mark.unit
def test_fetch_complexportal_tsv_filenames_selects_tsv_links():
    """Only .tsv hrefs are returned; parent-directory and non-tsv links are ignored."""
    listing = b"""
    <html>
      <body>
        <a href="../">Parent Directory</a>
        <a href="README.htm">README.htm</a>
        <a href="559292.tsv">559292.tsv</a>
        <a href="9606.tsv">9606.tsv</a>
        <a href="/pub/databases/intact/complex/current/complextab/10090.tsv">10090.tsv</a>
      </body>
    </html>
    """

    with patch("urllib.request.urlopen", return_value=_FakeResponse(listing)):
        filenames = complexportal.fetch_complexportal_tsv_filenames("https://example.org/complextab/")

    assert filenames == ["10090.tsv", "559292.tsv", "9606.tsv"]


@pytest.mark.unit
def test_pull_complexportal_downloads_all_discovered_tsvs_and_writes_manifest(tmp_path):
    """Every discovered TSV is fetched, the manifest lists them, and download_done is written last."""
    complexportal_dir = tmp_path / "ComplexPortal"
    download_done = complexportal_dir / complexportal.COMPLEXPORTAL_DOWNLOAD_DONE
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST

    with (
        patch(
            "src.datahandlers.complexportal.fetch_complexportal_tsv_filenames", return_value=["10090.tsv", "559292.tsv"]
        ),
        patch("src.datahandlers.complexportal.pull_via_urllib") as mock_pull,
    ):
        complexportal.pull_complexportal(str(download_done))

    assert manifest.read_text() == "10090.tsv\n559292.tsv\n"
    assert download_done.exists(), "Sentinel file download_done should be written last"
    assert mock_pull.call_count == 2
    mock_pull.assert_any_call(
        complexportal.COMPLEXPORTAL_COMPLEXTAB_URL,
        "10090.tsv",
        decompress=False,
        subpath=COMPLEXPORTAL,
    )
    mock_pull.assert_any_call(
        complexportal.COMPLEXPORTAL_COMPLEXTAB_URL,
        "559292.tsv",
        decompress=False,
        subpath=COMPLEXPORTAL,
    )


@pytest.mark.unit
def test_make_labels_synonyms_and_taxa_combines_manifest_files(tmp_path):
    """Labels, synonyms, taxa, descriptions, and IDs are correctly extracted across multiple species files."""
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("10090.tsv\n559292.tsv\n")

    (complexportal_dir / "10090.tsv").write_text(
        COMPLEXTAB_HEADER
        + _row("CPX-1", "Mediator complex", "Mediator|Mediator complex", "10090", "A conserved complex.")
        + _row("CPX-2", "Shared alias complex", "Mediator", "10090", "Another complex.")
    )
    (complexportal_dir / "559292.tsv").write_text(
        COMPLEXTAB_HEADER
        # CPX-1 has the same description in both files — should appear only once.
        + _row("CPX-1", "Mediator complex", "Mediator|Mediator complex", "559292", "A conserved complex.")
        + _row("CPX-3", "No alias complex", "-", "559292")
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    ids = complexportal_dir / "ids"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest),
        str(complexportal_dir),
        str(labels),
        str(synonyms),
        str(taxa),
        str(descriptions),
        str(metadata),
        str(ids),
    )

    label_rows = assert_labels_file_valid(str(labels))
    synonym_rows = assert_synonyms_file_valid(str(synonyms))
    taxa_rows = assert_taxa_file_valid(str(taxa))
    desc_rows = assert_descriptions_file_valid(str(descriptions))
    ids_rows = assert_ids_file_valid(str(ids))

    assert label_rows == [
        [f"{COMPLEXPORTAL}:CPX-1", "Mediator complex"],
        [f"{COMPLEXPORTAL}:CPX-2", "Shared alias complex"],
        [f"{COMPLEXPORTAL}:CPX-3", "No alias complex"],
    ]
    assert synonym_rows == [
        [f"{COMPLEXPORTAL}:CPX-1", HAS_EXACT_SYNONYM, "Mediator"],
        [f"{COMPLEXPORTAL}:CPX-1", HAS_EXACT_SYNONYM, "Mediator complex"],
        [f"{COMPLEXPORTAL}:CPX-2", HAS_EXACT_SYNONYM, "Mediator"],
    ]
    # CPX-1 appears in both files with different taxa; both taxa should be recorded.
    assert [f"{COMPLEXPORTAL}:CPX-1", "NCBITaxon:10090"] in taxa_rows
    assert [f"{COMPLEXPORTAL}:CPX-1", "NCBITaxon:559292"] in taxa_rows
    assert [f"{COMPLEXPORTAL}:CPX-2", "NCBITaxon:10090"] in taxa_rows
    assert [f"{COMPLEXPORTAL}:CPX-3", "NCBITaxon:559292"] in taxa_rows
    # CPX-1 appears in both files with the same description text — written only once.
    cpx1_descs = [row[1] for row in desc_rows if row[0] == f"{COMPLEXPORTAL}:CPX-1"]
    assert cpx1_descs == ["A conserved complex."]
    assert [f"{COMPLEXPORTAL}:CPX-2", "Another complex."] in desc_rows
    # CPX-3 has no description ("-"); it should not appear in the descriptions file.
    assert not any(row[0] == f"{COMPLEXPORTAL}:CPX-3" for row in desc_rows)
    # All three distinct IDs must appear in the IDs file exactly once.
    ids_curies = [row[0] for row in ids_rows]
    assert ids_curies == [f"{COMPLEXPORTAL}:CPX-1", f"{COMPLEXPORTAL}:CPX-2", f"{COMPLEXPORTAL}:CPX-3"]
    assert all(row[1] == "biolink:MacromolecularComplex" for row in ids_rows)
    assert metadata.exists()


@pytest.mark.unit
def test_make_labels_synonyms_and_taxa_deduplicates_labels_by_identifier(tmp_path):
    """Same complex ID in two species files with different labels: first label wins, no duplicate label row."""
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("9606.tsv\n10090.tsv\n")

    (complexportal_dir / "9606.tsv").write_text(
        COMPLEXTAB_HEADER + _row("CPX-1", "Human name", "-", "9606", "Human-specific description.")
    )
    (complexportal_dir / "10090.tsv").write_text(
        COMPLEXTAB_HEADER + _row("CPX-1", "Mouse name", "-", "10090", "Mouse-specific description.")
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    ids = complexportal_dir / "ids"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest),
        str(complexportal_dir),
        str(labels),
        str(synonyms),
        str(taxa),
        str(descriptions),
        str(metadata),
        str(ids),
    )

    label_rows = assert_labels_file_valid(str(labels))
    assert label_rows == [[f"{COMPLEXPORTAL}:CPX-1", "Human name"]]

    # Both taxa are recorded even though the label was deduplicated.
    taxa_rows = assert_taxa_file_valid(str(taxa))
    assert [f"{COMPLEXPORTAL}:CPX-1", "NCBITaxon:9606"] in taxa_rows
    assert [f"{COMPLEXPORTAL}:CPX-1", "NCBITaxon:10090"] in taxa_rows

    # Both descriptions are kept — DescriptionFactory accumulates all descriptions per identifier.
    desc_rows = assert_descriptions_file_valid(str(descriptions))
    desc_texts = {row[1] for row in desc_rows if row[0] == f"{COMPLEXPORTAL}:CPX-1"}
    assert desc_texts == {"Human-specific description.", "Mouse-specific description."}


@pytest.mark.unit
def test_make_labels_synonyms_and_taxa_skips_missing_taxon(tmp_path):
    """Rows with '-' taxonomy identifier produce no taxa entry."""
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("9606.tsv\n")

    (complexportal_dir / "9606.tsv").write_text(
        COMPLEXTAB_HEADER
        + _row("CPX-1", "Complex with taxon", "-", "9606")
        + _row("CPX-2", "Complex without taxon", "-", "-")
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    ids = complexportal_dir / "ids"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest),
        str(complexportal_dir),
        str(labels),
        str(synonyms),
        str(taxa),
        str(descriptions),
        str(metadata),
        str(ids),
    )

    taxa_rows = assert_taxa_file_valid(str(taxa))
    assert len(taxa_rows) == 1
    assert taxa_rows[0] == [f"{COMPLEXPORTAL}:CPX-1", "NCBITaxon:9606"]


@pytest.mark.unit
def test_make_labels_synonyms_and_taxa_deduplicates_identical_descriptions(tmp_path):
    """Same description text in two species files produces only one description row."""
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("9606.tsv\n10090.tsv\n")

    shared_desc = "A description shared verbatim across species."
    (complexportal_dir / "9606.tsv").write_text(
        COMPLEXTAB_HEADER + _row("CPX-1", "Human name", "-", "9606", shared_desc)
    )
    (complexportal_dir / "10090.tsv").write_text(
        COMPLEXTAB_HEADER + _row("CPX-1", "Mouse name", "-", "10090", shared_desc)
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    ids = complexportal_dir / "ids"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest),
        str(complexportal_dir),
        str(labels),
        str(synonyms),
        str(taxa),
        str(descriptions),
        str(metadata),
        str(ids),
    )

    desc_rows = assert_descriptions_file_valid(str(descriptions))
    assert desc_rows == [[f"{COMPLEXPORTAL}:CPX-1", shared_desc]]


@pytest.mark.unit
def test_make_labels_synonyms_and_taxa_ids_file_includes_entries_with_empty_label(tmp_path):
    """IDs file must include every identifier even when the recommended name column is empty."""
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("9606.tsv\n")

    (complexportal_dir / "9606.tsv").write_text(
        COMPLEXTAB_HEADER
        + _row("CPX-1", "Normal complex", "-", "9606")
        + _row("CPX-2", "", "-", "9606")  # empty recommended name
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    ids = complexportal_dir / "ids"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest),
        str(complexportal_dir),
        str(labels),
        str(synonyms),
        str(taxa),
        str(descriptions),
        str(metadata),
        str(ids),
    )

    ids_rows = assert_ids_file_valid(str(ids))
    ids_curies = [row[0] for row in ids_rows]
    assert f"{COMPLEXPORTAL}:CPX-1" in ids_curies
    assert f"{COMPLEXPORTAL}:CPX-2" in ids_curies, "ID with empty label must still appear in IDs file"
    assert all(row[1] == "biolink:MacromolecularComplex" for row in ids_rows)


@pytest.mark.network
def test_fetch_complexportal_tsv_filenames_returns_real_files():
    """Live EBI endpoint returns at least one .tsv file and the list is sorted."""
    filenames = complexportal.fetch_complexportal_tsv_filenames()
    assert len(filenames) > 0
    assert all(f.endswith(".tsv") for f in filenames)
    assert filenames == sorted(filenames)
