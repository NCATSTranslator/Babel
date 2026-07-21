"""Unit tests for the previous-release prefix comparison (``src/reports/prefix_comparison.py``).

Covered here (see the section headers below):

- RELEASE DATE PARSING — ``YYYYmonDD`` names sort by real date, not lexically.
- PIN CONSISTENCY — ``config.yaml``'s ``previous_release`` must be the newest committed baseline.
- DIFF TABLES — overall + by-clique-prefix diffs, sorting, NEW/REMOVED edge cases, warnings, and the
  graceful no-baseline path.

The reports are built from tiny hand-written combined prefix reports; the comparison only reads exact
occurrence counts (``count_curies``/``count_cliques`` and ``by_clique[*].by_file``), so the fixtures
omit the ``by_curie_prefix``/``by_filename`` sections the comparison never touches.
"""

import csv
import json
from pathlib import Path

import pytest

from src.reports import prefix_comparison
from src.util import get_config

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINES_DIR = REPO_ROOT / "releases" / "prefix_reports"


def _make_report(name, by_clique, count_curies, count_cliques):
    """Build a minimal combined prefix report holding only what the comparison reads."""
    return {
        "name": name,
        "count_curies": count_curies,
        "count_cliques": count_cliques,
        "by_clique": by_clique,
        "by_curie_prefix": {},
        "by_filename": {},
    }


def _write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def _read_csv(path):
    with open(path) as f:
        return list(csv.reader(f))


# ----
# RELEASE DATE PARSING
# ----


@pytest.mark.unit
def test_parse_release_date_orders_by_real_date():
    """Names must order by calendar date: 'dec' > 'sep' even though it sorts earlier lexically."""
    assert prefix_comparison.parse_release_date("2025jan23") < prefix_comparison.parse_release_date("2025mar31")
    assert prefix_comparison.parse_release_date("2025mar31") < prefix_comparison.parse_release_date("2025sep1")
    # The lexical trap: "2025dec1" < "2025sep1" as strings, but December is later.
    assert prefix_comparison.parse_release_date("2025sep1") < prefix_comparison.parse_release_date("2025dec1")


@pytest.mark.unit
def test_parse_release_date_rejects_bad_names():
    """A name that isn't YYYYmonDD should raise ValueError, not silently mis-sort."""
    with pytest.raises(ValueError):
        prefix_comparison.parse_release_date("2025foo1")
    with pytest.raises(ValueError):
        prefix_comparison.parse_release_date("not-a-release")


@pytest.mark.unit
def test_list_release_names_sorted_oldest_to_newest(tmp_path):
    """list_release_names returns parseable stems, oldest first, skipping non-release files."""
    for name in ("2025sep1.json", "2025jan23.json", "2025mar31.json", "README.json", "notes.txt"):
        (tmp_path / name).write_text("{}")
    assert prefix_comparison.list_release_names(str(tmp_path)) == ["2025jan23", "2025mar31", "2025sep1"]


@pytest.mark.unit
def test_list_release_names_raises_on_release_shaped_invalid_date(tmp_path):
    """A stem that looks like a release but is an impossible date must raise, not be silently skipped
    -- otherwise a mis-dated committed baseline could hide the newest one from the pin guard."""
    (tmp_path / "2025feb31.json").write_text("{}")  # Feb 31 does not exist
    with pytest.raises(ValueError):
        prefix_comparison.list_release_names(str(tmp_path))


# ----
# PIN CONSISTENCY (the weekly-unit-test guard the user asked for)
# ----


@pytest.mark.unit
def test_previous_release_pin_is_newest_committed_baseline():
    """config.yaml's previous_release must point at the newest baseline in releases/prefix_reports/.

    This catches the failure mode where a newer prefix report was committed but the pin was not bumped
    (the two silently out of sync). Running weekly, it flags the drift before the next build starts.
    """
    config = get_config()
    pinned = config["previous_release"]

    names = prefix_comparison.list_release_names(str(BASELINES_DIR))
    assert names, f"No committed baselines found in {BASELINES_DIR}"
    newest = names[-1]

    assert pinned == newest, (
        f"config.yaml previous_release={pinned!r} is not the newest committed baseline ({newest!r}); "
        f"bump previous_release when you archive a newer prefix report."
    )
    assert (BASELINES_DIR / f"{pinned}.json").exists()


# ----
# DIFF TABLES
# ----


@pytest.fixture
def compared(tmp_path):
    """Run a representative comparison and return the parsed outputs.

    INCHIKEY drops by 8,443,204 in PUBCHEM.COMPOUND-led SmallMolecule cliques (the user's example),
    GONE is removed entirely, and MESH/Disease is brand new.
    """
    baseline = _make_report(
        "2025sep1",
        by_clique={
            "PUBCHEM.COMPOUND": {
                "by_file": {"SmallMolecule": {"INCHIKEY": 10_000_000, "PUBCHEM.COMPOUND": 5_000_000, "GONE": 300}}
            },
            "CHEBI": {"by_file": {"ChemicalEntity": {"CHEBI": 100}}},
        },
        count_curies=15_000_400,
        count_cliques=200,
    )
    current = _make_report(
        "2026jul2",
        by_clique={
            "PUBCHEM.COMPOUND": {"by_file": {"SmallMolecule": {"INCHIKEY": 1_556_796, "PUBCHEM.COMPOUND": 5_000_000}}},
            "CHEBI": {"by_file": {"ChemicalEntity": {"CHEBI": 100}}},
            "MESH": {"by_file": {"Disease": {"MESH": 50}}},
        },
        count_curies=6_556_946,
        count_cliques=210,
    )

    current_json = tmp_path / "prefix_report.json"
    baseline_json = tmp_path / "2025sep1.json"
    _write_json(current_json, current)
    _write_json(baseline_json, baseline)

    overall_csv = tmp_path / "overall.csv"
    by_clique_csv = tmp_path / "by_clique.csv"
    md = tmp_path / "prefix_comparison.md"
    prefix_comparison.generate_prefix_comparison(
        str(current_json), str(baseline_json), str(overall_csv), str(by_clique_csv), str(md), 100_000, 25
    )
    return {
        "overall": _read_csv(overall_csv),
        "by_clique": _read_csv(by_clique_csv),
        "md": md.read_text(),
    }


@pytest.mark.unit
def test_overall_table_curies_and_cliques(compared):
    """The overall table leads with All CURIEs and All cliques, each with the absolute change."""
    rows = {r[0]: r for r in compared["overall"][1:]}
    assert rows["All CURIEs"][1:4] == ["15000400", "6556946", "-8443454"]
    assert rows["All cliques (approx)"][1:4] == ["200", "210", "10"]


@pytest.mark.unit
def test_overall_table_per_filename_curie_totals(compared):
    """Per-filename rows sum by_file occurrence counts on each side (exact)."""
    rows = {r[0]: r for r in compared["overall"][1:]}
    # SmallMolecule: 10,000,000 + 5,000,000 + 300 -> 1,556,796 + 5,000,000.
    assert rows["SmallMolecule CURIEs"][1:4] == ["15000300", "6556796", "-8443504"]
    # Disease is brand new.
    assert rows["Disease CURIEs"][1:5] == ["0", "50", "50", "NEW"]


@pytest.mark.unit
def test_by_clique_table_sorted_by_absolute_change(compared):
    """The by-clique-prefix table is sorted by absolute change, largest first (ignoring sign)."""
    data = compared["by_clique"][1:]
    top = data[0]
    # The INCHIKEY drop (-8,443,204) is the largest-magnitude change.
    assert top[:3] == ["SmallMolecule", "PUBCHEM.COMPOUND", "INCHIKEY"]
    assert top[5] == "-8443204"
    assert top[7] == "8,443,204 fewer INCHIKEY identifiers in SmallMolecule cliques led by PUBCHEM.COMPOUND"
    # Magnitudes are non-increasing down the table.
    magnitudes = [abs(int(r[5])) for r in data]
    assert magnitudes == sorted(magnitudes, reverse=True)


@pytest.mark.unit
def test_by_clique_table_new_and_removed_rows(compared):
    """NEW rows report percent 'NEW'; removed rows report -100.0% and Current 0."""
    by_key = {(r[0], r[1], r[2]): r for r in compared["by_clique"][1:]}

    new_row = by_key[("Disease", "MESH", "MESH")]
    assert new_row[3] == "0" and new_row[4] == "50" and new_row[6] == "NEW"
    assert "new" in new_row[7]

    removed_row = by_key[("SmallMolecule", "PUBCHEM.COMPOUND", "GONE")]
    assert removed_row[3] == "300" and removed_row[4] == "0" and removed_row[6] == "-100.0%"
    assert "removed" in removed_row[7]


@pytest.mark.unit
def test_markdown_names_baseline_and_lists_notable(compared):
    """The .md must name the baseline explicitly and flag the large drop and the removal."""
    md = compared["md"]
    assert "2026jul2" in md and "2025sep1" in md
    assert "2025sep1.json" in md  # the exact baseline file is named
    # The big INCHIKEY drop and the removed prefix are notable; the tiny new MESH row is not.
    assert "8,443,204 fewer INCHIKEY" in md
    assert "300 removed GONE" in md
    assert "50 new MESH" not in md


@pytest.mark.unit
def test_missing_baseline_is_graceful(tmp_path):
    """With no baseline file, write header-only CSVs and an explanatory .md (no exception)."""
    current_json = tmp_path / "prefix_report.json"
    _write_json(current_json, _make_report("2026jul2", {}, 0, 0))

    overall_csv = tmp_path / "overall.csv"
    by_clique_csv = tmp_path / "by_clique.csv"
    md = tmp_path / "prefix_comparison.md"
    prefix_comparison.generate_prefix_comparison(
        str(current_json), str(tmp_path / "does_not_exist.json"), str(overall_csv), str(by_clique_csv), str(md), 1, 1
    )

    assert _read_csv(overall_csv) == [["Metric", "Previous", "Current", "Absolute change", "Percent change"]]
    assert len(_read_csv(by_clique_csv)) == 1  # header only
    assert "No prior baseline" in md.read_text()
