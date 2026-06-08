from unittest.mock import patch

import pytest

from src.datahandlers import complexportal
from src.predicates import HAS_EXACT_SYNONYM
from src.prefixes import COMPLEXPORTAL
from tests.conftest import assert_labels_file_valid, assert_synonyms_file_valid


class _FakeResponse:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.content


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
    manifest = tmp_path / "ComplexPortal" / complexportal.COMPLEXPORTAL_MANIFEST

    with (
        patch(
            "src.datahandlers.complexportal.fetch_complexportal_tsv_filenames", return_value=["10090.tsv", "559292.tsv"]
        ),
        patch("src.datahandlers.complexportal.pull_via_urllib") as mock_pull,
    ):
        complexportal.pull_complexportal(str(manifest))

    assert manifest.read_text() == "10090.tsv\n559292.tsv\n"
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
def test_make_labels_and_synonyms_combines_manifest_files(tmp_path):
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("10090.tsv\n559292.tsv\n")

    header = "Complex ac\tRecommended name\tAliases\tDescription\n"
    (complexportal_dir / "10090.tsv").write_text(
        header
        + "CPX-1\tMediator complex\tMediator|Mediator complex\tA complex\n"
        + "CPX-2\tShared alias complex\tMediator\tAnother complex\n"
    )
    (complexportal_dir / "559292.tsv").write_text(
        header
        + "CPX-1\tMediator complex\tMediator|Mediator complex\tA complex\n"
        + "CPX-3\tNo alias complex\t-\tNo aliases\n"
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_and_synonyms(str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(metadata))

    label_rows = assert_labels_file_valid(str(labels))
    synonym_rows = assert_synonyms_file_valid(str(synonyms))

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
    assert metadata.exists()


@pytest.mark.unit
def test_make_labels_and_synonyms_deduplicates_by_identifier(tmp_path):
    """Same complex ID in two species files with different labels: first label wins, no duplicate row."""
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("9606.tsv\n10090.tsv\n")

    header = "Complex ac\tRecommended name\tAliases\tDescription\n"
    (complexportal_dir / "9606.tsv").write_text(header + "CPX-1\tHuman name\t-\tHuman complex\n")
    (complexportal_dir / "10090.tsv").write_text(header + "CPX-1\tMouse name\t-\tMouse complex\n")

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_and_synonyms(str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(metadata))

    label_rows = assert_labels_file_valid(str(labels))
    assert label_rows == [[f"{COMPLEXPORTAL}:CPX-1", "Human name"]]


@pytest.mark.network
def test_fetch_complexportal_tsv_filenames_returns_real_files():
    filenames = complexportal.fetch_complexportal_tsv_filenames()
    assert len(filenames) > 0
    assert all(f.endswith(".tsv") for f in filenames)
    assert filenames == sorted(filenames)
