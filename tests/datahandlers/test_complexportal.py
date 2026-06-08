from unittest.mock import patch

import pytest

from src.datahandlers import complexportal
from src.predicates import HAS_EXACT_SYNONYM
from src.prefixes import COMPLEXPORTAL
from tests.conftest import (
    assert_descriptions_file_valid,
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


# Real ComplexPortal ComplexTAB header (all 19 columns as of 2026-06).
# Columns currently used by Babel are marked with (*); the rest are set to "-" in test rows.
# Columns worth considering for future use are noted inline.
_COLUMNS = [
    "#Complex ac",                                           # 0  (*) complex accession → CURIE
    "Recommended name",                                      # 1  (*) preferred label
    "Aliases for complex",                                   # 2  (*) "|"-separated synonyms, or "-"
    "Taxonomy identifier",                                   # 3  (*) NCBI taxon integer, or "-"
    "Identifiers (and stoichiometry) of molecules in complex",  # 4  participants — could add to concords
    "Evidence Code",                                         # 5
    "Experimental evidence",                                 # 6
    "Go Annotations",                                        # 7  GO terms — could enrich type/function info
    "Cross references",                                      # 8  Reactome, PubMed, wwPDB, etc. — potential concord sources
    "Description",                                           # 9  (*) free-text description
    "Complex properties",                                    # 10
    "Complex assembly",                                      # 11
    "Ligand",                                                # 12
    "Disease",                                               # 13 disease associations — potentially useful
    "Agonist",                                               # 14
    "Antagonist",                                            # 15
    "Comment",                                               # 16
    "Source",                                                # 17
    "Expanded participant list",                             # 18
]
_HEADER = "\t".join(_COLUMNS) + "\n"


def _row(ac, name, aliases, taxon, description="-"):
    """Build a test data row with only the columns Babel reads set to real values."""
    values = ["-"] * len(_COLUMNS)
    values[0] = ac
    values[1] = name
    values[2] = aliases
    values[3] = taxon
    values[9] = description
    return "\t".join(values) + "\n"


@pytest.mark.unit
def test_fetch_complexportal_tsv_filenames_selects_tsv_links():
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
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("10090.tsv\n559292.tsv\n")

    (complexportal_dir / "10090.tsv").write_text(
        _HEADER
        + _row("CPX-1", "Mediator complex", "Mediator|Mediator complex", "10090", "A conserved complex.")
        + _row("CPX-2", "Shared alias complex", "Mediator", "10090", "Another complex.")
    )
    (complexportal_dir / "559292.tsv").write_text(
        _HEADER
        # CPX-1 has the same description in both files — should appear only once.
        + _row("CPX-1", "Mediator complex", "Mediator|Mediator complex", "559292", "A conserved complex.")
        + _row("CPX-3", "No alias complex", "-", "559292")
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(taxa), str(descriptions), str(metadata)
    )

    label_rows = assert_labels_file_valid(str(labels))
    synonym_rows = assert_synonyms_file_valid(str(synonyms))
    taxa_rows = assert_taxa_file_valid(str(taxa))
    desc_rows = assert_descriptions_file_valid(str(descriptions))

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
    assert metadata.exists()


@pytest.mark.unit
def test_make_labels_synonyms_and_taxa_deduplicates_labels_by_identifier(tmp_path):
    """Same complex ID in two species files with different labels: first label wins, no duplicate label row."""
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("9606.tsv\n10090.tsv\n")

    (complexportal_dir / "9606.tsv").write_text(
        _HEADER + _row("CPX-1", "Human name", "-", "9606", "Human-specific description.")
    )
    (complexportal_dir / "10090.tsv").write_text(
        _HEADER + _row("CPX-1", "Mouse name", "-", "10090", "Mouse-specific description.")
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(taxa), str(descriptions), str(metadata)
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
        _HEADER
        + _row("CPX-1", "Complex with taxon", "-", "9606")
        + _row("CPX-2", "Complex without taxon", "-", "-")
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(taxa), str(descriptions), str(metadata)
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
    (complexportal_dir / "9606.tsv").write_text(_HEADER + _row("CPX-1", "Human name", "-", "9606", shared_desc))
    (complexportal_dir / "10090.tsv").write_text(_HEADER + _row("CPX-1", "Mouse name", "-", "10090", shared_desc))

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    descriptions = complexportal_dir / "descriptions"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(taxa), str(descriptions), str(metadata)
    )

    desc_rows = assert_descriptions_file_valid(str(descriptions))
    assert desc_rows == [[f"{COMPLEXPORTAL}:CPX-1", shared_desc]]


@pytest.mark.network
def test_fetch_complexportal_tsv_filenames_returns_real_files():
    filenames = complexportal.fetch_complexportal_tsv_filenames()
    assert len(filenames) > 0
    assert all(f.endswith(".tsv") for f in filenames)
    assert filenames == sorted(filenames)
