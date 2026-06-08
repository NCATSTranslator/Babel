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


# Real ComplexPortal ComplexTAB header (all 19 columns as of 2026-06).
# Columns currently used by Babel are marked with (*); the rest are set to "-" in test rows.
# Columns worth considering for future use are noted inline.
_HEADER = (
    "#Complex ac\t"           # 0  (*) complex accession → CURIE
    "Recommended name\t"      # 1  (*) preferred label
    "Aliases for complex\t"   # 2  (*) "|"-separated synonyms, or "-"
    "Taxonomy identifier\t"   # 3  (*) NCBI taxon integer, or "-"
    "Identifiers (and stoichiometry) of molecules in complex\t"  # 4  participants — could add to concords
    "Evidence Code\t"         # 5
    "Experimental evidence\t" # 6
    "Go Annotations\t"        # 7  GO terms — could enrich type/function info
    "Cross references\t"      # 8  Reactome, PubMed, wwPDB, etc. — potential concord sources
    "Description\t"           # 9  free-text description — could populate descriptions file
    "Complex properties\t"    # 10
    "Complex assembly\t"      # 11
    "Ligand\t"                # 12
    "Disease\t"               # 13 disease associations — potentially useful
    "Agonist\t"               # 14
    "Antagonist\t"            # 15
    "Comment\t"               # 16
    "Source\t"                # 17
    "Expanded participant list\n"  # 18
)

# Shorthand for a row with all unused columns set to "-".
def _row(ac, name, aliases, taxon):
    return f"{ac}\t{name}\t{aliases}\t{taxon}\t" + "\t".join(["-"] * 15) + "\n"


def _assert_taxa_file_valid(path: str) -> list[list[str]]:
    """Assert every line is CURIE\\tNCBITaxon:NNNN; return the rows."""
    rows = []
    with open(path) as f:
        for line in f:
            stripped = line.rstrip("\n")
            if stripped:
                cols = stripped.split("\t")
                assert len(cols) == 2, f"Expected 2 columns in taxa file, got {len(cols)}: {cols}"
                assert cols[0].startswith(f"{COMPLEXPORTAL}:"), f"First column is not a ComplexPortal CURIE: {cols[0]}"
                assert cols[1].startswith("NCBITaxon:"), f"Second column is not an NCBITaxon CURIE: {cols[1]}"
                rows.append(cols)
    assert rows, f"Taxa file is empty: {path}"
    return rows


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
def test_make_labels_synonyms_and_taxa_combines_manifest_files(tmp_path):
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("10090.tsv\n559292.tsv\n")

    (complexportal_dir / "10090.tsv").write_text(
        _HEADER
        + _row("CPX-1", "Mediator complex", "Mediator|Mediator complex", "10090")
        + _row("CPX-2", "Shared alias complex", "Mediator", "10090")
    )
    (complexportal_dir / "559292.tsv").write_text(
        _HEADER
        + _row("CPX-1", "Mediator complex", "Mediator|Mediator complex", "559292")
        + _row("CPX-3", "No alias complex", "-", "559292")
    )

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(taxa), str(metadata)
    )

    label_rows = assert_labels_file_valid(str(labels))
    synonym_rows = assert_synonyms_file_valid(str(synonyms))
    taxa_rows = _assert_taxa_file_valid(str(taxa))

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
    assert metadata.exists()


@pytest.mark.unit
def test_make_labels_synonyms_and_taxa_deduplicates_labels_by_identifier(tmp_path):
    """Same complex ID in two species files with different labels: first label wins, no duplicate label row."""
    complexportal_dir = tmp_path / "ComplexPortal"
    complexportal_dir.mkdir()
    manifest = complexportal_dir / complexportal.COMPLEXPORTAL_MANIFEST
    manifest.write_text("9606.tsv\n10090.tsv\n")

    (complexportal_dir / "9606.tsv").write_text(_HEADER + _row("CPX-1", "Human name", "-", "9606"))
    (complexportal_dir / "10090.tsv").write_text(_HEADER + _row("CPX-1", "Mouse name", "-", "10090"))

    labels = complexportal_dir / "labels"
    synonyms = complexportal_dir / "synonyms"
    taxa = complexportal_dir / "taxa"
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(taxa), str(metadata)
    )

    label_rows = assert_labels_file_valid(str(labels))
    assert label_rows == [[f"{COMPLEXPORTAL}:CPX-1", "Human name"]]

    # Both taxa are recorded even though the label was deduplicated.
    taxa_rows = _assert_taxa_file_valid(str(taxa))
    assert [f"{COMPLEXPORTAL}:CPX-1", "NCBITaxon:9606"] in taxa_rows
    assert [f"{COMPLEXPORTAL}:CPX-1", "NCBITaxon:10090"] in taxa_rows


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
    metadata = complexportal_dir / "metadata.yaml"

    complexportal.make_labels_synonyms_and_taxa(
        str(manifest), str(complexportal_dir), str(labels), str(synonyms), str(taxa), str(metadata)
    )

    taxa_rows = _assert_taxa_file_valid(str(taxa))
    assert len(taxa_rows) == 1
    assert taxa_rows[0] == [f"{COMPLEXPORTAL}:CPX-1", "NCBITaxon:9606"]


@pytest.mark.network
def test_fetch_complexportal_tsv_filenames_returns_real_files():
    filenames = complexportal.fetch_complexportal_tsv_filenames()
    assert len(filenames) > 0
    assert all(f.endswith(".tsv") for f in filenames)
    assert filenames == sorted(filenames)
