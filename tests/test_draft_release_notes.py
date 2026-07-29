"""Tests for the release-note drafting script (``releases/scripts/draft_release_notes.py``).

Covers the two parts that are easy to get quietly wrong: which PRs are folded away as routine, and
the number formatting in the `Summary of changes` table (a dropped `\\-` escape or a mis-shaped
from-zero row is invisible until the published note renders).
"""

import importlib.util
import sys

import pytest

from src.util import get_repo_root

_SCRIPT = get_repo_root() / "releases" / "scripts" / "draft_release_notes.py"


def _load_module():
    """Import the script by path: `releases/` is deliberately not a package under `src/`."""
    spec = importlib.util.spec_from_file_location("draft_release_notes", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


drn = _load_module()


def _pr(title, author="gaurav", number=1):
    return drn.PullRequest("Babel", "NCATSTranslator/Babel", number, title, author)


@pytest.mark.unit
@pytest.mark.parametrize(
    "title,author,expected",
    [
        # Real changes a consumer should read about.
        ("Add MP, kept disjoint from HP, with an xref allowlist and HP/MP taxa", "gaurav", False),
        ("Type DrugBank foods as biolink:Food, extracts as ComplexMolecularMixture (#828)", "gaurav", False),
        # "Update" alone is substantive; only "Update <dep> requirement from ..." is routine.
        ("Update node_normalizer/server.py to return a 400", "gaurav", False),
        # Routine: version increments, dependency bumps, merge commits, and anything from a bot.
        ("Increment version to Babel v1.17", "gaurav", True),
        ("Incremented version to v1.6.2", "gaurav", True),
        ("build(deps-dev): bump snakefmt from 2.0.2 to 2.0.3", "dependabot[bot]", True),
        ("Update setuptools requirement from >=64 to >=83.0.0", "gaurav", True),
        ("Upgraded packages using `uv sync --upgrade`", "gaurav", True),
        ("Merge pull request #123 from NCATSTranslator/some-branch", "gaurav", True),
        ("Something a bot did that we cannot pattern-match", "dependabot[bot]", True),
    ],
)
def test_routine_classification(title, author, expected):
    assert _pr(title, author).is_routine is expected


@pytest.mark.unit
def test_pull_request_markdown_is_an_unchecked_checklist_item():
    line = _pr("Add MP, kept disjoint from HP", number=886).as_markdown()
    assert line == (
        "- [ ] [Babel #886](https://github.com/NCATSTranslator/Babel/pull/886) — Add MP, kept disjoint from HP (@gaurav)"
    )


@pytest.mark.unit
def test_summary_of_changes_formats_every_kind_of_row(tmp_path):
    """A growing row, a shrinking row, an unchanged row and a from-zero row."""
    tables = tmp_path / "reports" / "tables"
    tables.mkdir(parents=True)
    (tables / "prefix_comparison_overall.csv").write_text(
        "Metric,Previous,Current,Absolute change,Percent change\n"
        "All CURIEs,688983999,605864191,-83119808,-12.1%\n"
        "All cliques (approx),490293340,388490111,-101803229,-20.8%\n"
        "AnatomicalEntity CURIEs,249584,252287,2703,+1.1%\n"
        "CellLine CURIEs,38810,38810,0,+0.0%\n"
        "Food CURIEs,0,932,932,NEW\n"
    )

    table = drn.summary_of_changes(tmp_path, "2025sep1", "2026jul22")
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in table.splitlines()]

    assert rows[0] == ["Filename", "2025sep1", "2026jul22", "Diff", "% Diff"]
    # "All CURIEs"/"All cliques" are renamed to the labels the published notes have always used.
    assert rows[2] == ["Count of CURIEs in all files", "688,983,999", "605,864,191", "\\-83,119,808", "\\-12.1%"]
    assert rows[3][0] == "Count of cliques in all files"
    assert rows[4] == ["AnatomicalEntity", "249,584", "252,287", "+2,703", "+1.1%"]
    # An unchanged row is a bare "0", not "+0".
    assert rows[5] == ["CellLine", "38,810", "38,810", "0", "+0.0%"]
    # A compendium that did not exist before reads as Infinity%, matching 2025mar31.md's CellLine row.
    assert rows[6] == ["Food", "0", "932", "+932", "Infinity%"]


@pytest.mark.unit
def test_summary_of_changes_is_none_without_a_report(tmp_path):
    assert drn.summary_of_changes(tmp_path, "2025sep1", "2026jul22") is None


@pytest.mark.unit
def test_baseline_skips_releases_that_were_never_deployed():
    """v1.11 sits between 2025sep1 and 2025mar31 but never shipped, so it cannot be a baseline."""
    manifest = drn.load_manifest(get_repo_root() / "releases" / "releases.yaml")
    entry, previous = drn.find_release(manifest, "2025sep1")
    assert entry["id"] == "2025sep1"
    assert previous["id"] == "2025mar31"


@pytest.mark.unit
def test_ranges_use_the_last_service_version_deployed_against_each_build():
    """NameRes v1.5.2 shipped after v1.6.2, so the baseline is what was deployed, not what sorts highest."""
    manifest = drn.load_manifest(get_repo_root() / "releases" / "releases.yaml")
    entry, previous = drn.find_release(manifest, "2026jul22")
    assert drn._range_for("Babel", entry, previous) == ("2025sep1", "2026jul22")
    assert drn._range_for("NodeNorm", entry, previous) == ("v2.4.1", "v2.5.1")
    assert drn._range_for("NameRes", entry, previous) == ("v1.5.2", "v1.7.0")


@pytest.mark.unit
def test_every_release_note_is_listed_in_the_manifest():
    """Drift guard: a new note in releases/ must be added to releases.yaml or the tooling won't see it."""
    releases_dir = get_repo_root() / "releases"
    on_disk = {path.stem for path in releases_dir.glob("*.md")} - {"README"}
    in_manifest = {entry["id"] for entry in drn.load_manifest(releases_dir / "releases.yaml")}
    assert on_disk == in_manifest


@pytest.mark.unit
@pytest.mark.parametrize(
    "message,expected",
    [
        # Squash merges, the normal case across all three repos.
        ("Add MP, kept disjoint from HP (#886)", (886, "Add MP, kept disjoint from HP")),
        # A title that itself cites an issue number must not be mistaken for the PR number.
        ("Type DrugBank foods as biolink:Food (#828) (#918)", (918, "Type DrugBank foods as biolink:Food (#828)")),
        # Older merge commits name the PR but carry no title.
        ("Merge pull request #472 from TranslatorSRI/remove-redundant-ensembl-id-code", (472, None)),
        # Direct commits with no PR reference are skipped, not guessed at.
        ("Fixed a typo", None),
        ("Refs #123 but not a squash merge", None),
    ],
)
def test_commit_message_pr_extraction(message, expected):
    squash = drn._SQUASH_RE.match(message)
    merge = drn._MERGE_RE.match(message)
    if expected is None:
        assert squash is None and merge is None
        return
    number, title = expected
    if title is None:
        assert squash is None
        assert int(merge.group("number")) == number
    else:
        assert int(squash.group("number")) == number
        assert squash.group("title") == title


@pytest.mark.unit
def test_provenance_block_records_the_deployed_service_versions():
    """The whole point of releases.yaml: a note must say which NodeNorm/NameRes shipped with it."""
    manifest = drn.load_manifest(get_repo_root() / "releases" / "releases.yaml")
    entry, previous = drn.find_release(manifest, "2026jul22")
    block = "\n".join(drn.provenance_block(entry, previous))

    assert "https://stars.renci.org/var/babel_outputs/2026jul22/" in block
    assert "branch `babel-1.18.1`" in block
    assert "Biolink Model v4.4.3" in block
    # Both NodeNorm versions deployed against this build are listed, not just the latest.
    assert "NodeNorm: [v2.5.0]" in block and "[v2.5.1]" in block
    assert "NameRes: [v1.7.0]" in block
    assert "Previous release: [Babel 2025sep1](./2025sep1.md)" in block


@pytest.mark.unit
def test_provenance_block_hedges_an_approximate_babel_version():
    """The 2024 notes say "approx"; a manifest entry marked approx must not imply precision."""
    manifest = drn.load_manifest(get_repo_root() / "releases" / "releases.yaml")
    entry, _ = drn.find_release(manifest, "TranslatorGuppyAugust2024")
    assert "approx [Babel v1.8.0]" in "\n".join(drn.provenance_block(entry, None))
