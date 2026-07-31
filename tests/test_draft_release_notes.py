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
def test_summary_of_changes_renders_a_header_only_report(tmp_path):
    """A comparison that ran and produced no rows should still render a table, not crash the draft.

    The column-width calculation reduces over the data rows, so an empty set used to raise
    `TypeError` from `max()` and take the whole note with it.
    """
    tables = tmp_path / "reports" / "tables"
    tables.mkdir(parents=True)
    (tables / "prefix_comparison_overall.csv").write_text("Metric,Previous,Current,Absolute change,Percent change\n")

    table = drn.summary_of_changes(tmp_path, "2025sep1", "2026jul22")

    lines = table.splitlines()
    assert len(lines) == 2  # header and separator, no data rows
    assert [cell.strip() for cell in lines[0].strip("|").split("|")] == [
        "Filename",
        "2025sep1",
        "2026jul22",
        "Diff",
        "% Diff",
    ]


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


# STATUS ENDPOINTS

# Trimmed from the real responses, so the shapes are the ones actually served:
#   https://nodenormalization-exp.apps.renci.org/status
#   https://name-resolution-sri.renci.org/status
NODENORM_STATUS = {
    "status": "running",
    "version": "2.5.1",
    "babel_version": "2026jul22",
    "databases": {
        "eq_id_to_id_db": {"dbname": "id-id", "count": 605837726, "used_memory_rss_human": "53.78G"},
        "chemical_drug_db": {"dbname": "chemical-drug-db", "count": 104863, "used_memory_rss_human": "210.54M"},
        "id_to_eqids_db": {"dbname": "id-eq-id", "count": 398664426, "used_memory_rss_human": "94.61G"},
    },
}
# NameRes v1.5.2 (Dev at the time of writing) nests the Solr counters under "solr"...
NAMERES_STATUS = {
    "status": "ok",
    "babel_version": "2025sep1",
    "nameres_version": "v1.5.2",
    "solr": {"numDocs": 425583002, "maxDoc": 425586610, "size": "142.17 GB"},
}
# ...while v1.7.0 (Exp, serving 2026jul22) promotes them to the top level. Trimmed verbatim from
# https://name-resolution-exp.apps.renci.org/status -- both shapes are live simultaneously, and
# reading only the nested one yields a blank Solr row rather than an error.
NAMERES_STATUS_V17 = {
    "status": "ok",
    "message": "Reporting results from primary core.",
    "babel_version": "2026jul22",
    "nameres_version": "v1.7.0",
    "numDocs": 331513708,
    "maxDoc": 331516999,
    "deletedDocs": 3291,
    "size": "109.75 GB",
}


@pytest.mark.unit
def test_summary_table_uses_the_published_row_order_not_the_json_order():
    """NodeNorm returns its databases in whatever order it likes; the note's order is fixed."""
    rows = [line for line in drn.summary_table(NODENORM_STATUS, NAMERES_STATUS) if line.startswith("| ")]
    ids = [row.split("|")[2].strip() for row in rows[1:]]
    assert ids == ["eq_id_to_id_db", "id_to_eqids_db", "chemical_drug_db", "name_lookup"]
    assert "605,837,726" in rows[1] and "53.78G" in rows[1]
    # The Solr row comes from NameRes, not NodeNorm.
    assert "425,583,002" in rows[-1] and "142.17 GB" in rows[-1]


@pytest.mark.unit
def test_summary_table_reads_solr_counters_from_either_nameres_shape():
    """v1.5.2 nests them under `solr`, v1.7.0 puts them at the top level; both must populate the row.

    Reading only one shape leaves the Solr row *blank* rather than erroring, so the note would ship
    with a missing number that nothing flags.
    """
    for status, docs, size in (
        (NAMERES_STATUS, "425,583,002", "142.17 GB"),
        (NAMERES_STATUS_V17, "331,513,708", "109.75 GB"),
    ):
        row = [line for line in drn.summary_table(NODENORM_STATUS, status) if line.startswith("| ")][-1]
        assert row.split("|")[2].strip() == "name_lookup"
        assert docs in row and size in row


@pytest.mark.unit
def test_summary_table_keeps_a_database_it_has_never_seen():
    """A new Redis database must be appended, not silently dropped for being unrecognised."""
    status = {"databases": dict(NODENORM_STATUS["databases"])}
    status["databases"]["brand_new_db"] = {"dbname": "new-thing", "count": 7, "used_memory_rss_human": "1M"}
    rows = [line for line in drn.summary_table(status, None) if line.startswith("| ")]
    assert rows[-2].split("|")[2].strip() == "brand_new_db"


@pytest.mark.unit
def test_summary_table_falls_back_to_a_blank_skeleton_when_nodenorm_is_unreachable():
    rows = [line for line in drn.summary_table(None, None) if line.startswith("| ")]
    ids = [row.split("|")[2].strip() for row in rows[1:]]
    assert ids == drn.SUMMARY_DB_ORDER + ["name_lookup"]
    assert all(row.split("|")[3].strip() == "" for row in rows[1:])


@pytest.mark.unit
def test_deployed_version_check_warns_only_on_a_mismatch():
    """NameRes was still serving 2025sep1 when 2026jul22's note was written; copying its Solr
    numbers in unremarked would have described the previous release."""
    assert drn.check_deployed_version(NODENORM_STATUS, "NodeNorm", "2026jul22") == []
    warning = drn.check_deployed_version(NAMERES_STATUS, "NameRes", "2026jul22")
    assert len(warning) == 1
    assert "serving Babel 2025sep1, not 2026jul22" in warning[0]
    # An unreachable service is not a mismatch; the blank table already says the numbers are missing.
    assert drn.check_deployed_version(None, "NameRes", "2026jul22") == []


@pytest.mark.unit
def test_fetch_status_returns_none_instead_of_raising(capsys):
    """A note is worth drafting when the services are down or not yet deployed."""
    assert drn.fetch_status("http://127.0.0.1:1/status") is None
    assert "warning: could not read" in capsys.readouterr().err


@pytest.mark.unit
def test_fetch_pull_requests_surfaces_ghs_own_error(monkeypatch):
    """A failing `gh api` must report *why*, not just that it exited non-zero.

    `capture_output=True` hides gh's stderr, and that message -- an unknown tag, an expired token, a
    rate limit -- is the entire diagnosis. Unlike a missing tag, none of these is guessable from the
    exit code.
    """
    import subprocess

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "gh", stderr="gh: Not Found (HTTP 404)\n")

    monkeypatch.setattr(drn.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Not Found"):
        drn.fetch_pull_requests("Babel", "NCATSTranslator/Babel", "2025sep1", "2026jul22")


# SECTION STRUCTURE


@pytest.mark.unit
def test_draft_emits_the_house_section_order():
    """The skeleton must match the structure `releases/2026jul22.md` converged on.

    That note was hand-reorganized twice (c22e83b4, 5ac3dff0) away from the Bugfixes/Updates/New
    features skeleton the script used to emit, and both passes moved the same direction. Pinning the
    order here is what stops the next release being hand-rebuilt a third time.

    Two orderings are load-bearing rather than cosmetic:

    - `## Bugfixes` leads, so the section a consumer must act on is the first thing they see.
    - `## Areas that changed substantially` trails the two tables it explains. The same change is
      often worth a headline near the top *and* a paragraph here; separating them keeps that from
      reading as an accident.
    """
    entry = {"id": "2026jul22", "title": "Babel 2026jul22", "build": "2026jul22"}
    text = drn.draft(entry, None, None, drn.REPO_ROOT)
    headings = [line for line in text.splitlines() if line.startswith("#")]

    assert headings == [
        "# Babel 2026jul22",
        "## Bugfixes",
        "## Babel changes",
        "### Updates",
        "### New features and identifier/mapping additions",
        "### Improvements to Babel's output",
        "### Development and infrastructure",
        "### Minor changes and fixes",
        "### Known issues and caveats",
        "## NodeNorm Redis",
        "## NameRes Solr",
        "## All changes in this release",
        "## Deployed database sizes",
        "## Compendium size comparison",
    ]


@pytest.mark.unit
def test_unexplained_movers_flags_every_large_compendium_move(tmp_path):
    """A compendium that moved a lot but is explained nowhere must surface as an unchecked item.

    Nothing flagged these before: the build's own comparison warns per *prefix*, while the note is
    written per *compendium*. Polypeptide fell 97% in 2026jul22 and reached review unmentioned.
    """
    tables = tmp_path / "reports" / "tables"
    tables.mkdir(parents=True)
    (tables / "prefix_comparison_overall.csv").write_text(
        "Metric,Previous,Current,Absolute change,Percent change\n"
        "All CURIEs,688983999,605864191,-83119808,-12.1%\n"  # aggregate: never a mover
        "Polypeptide CURIEs,166,5,-161,-97.0%\n"
        "Food CURIEs,0,932,932,NEW\n"
        "Disease CURIEs,632330,639398,7068,1.1%\n"  # below threshold
    )

    movers = drn.unexplained_movers(tmp_path)

    assert "- [ ] **Polypeptide** (-97.0%, \\-161 CURIEs)" in movers
    assert "- [ ] **Food** (new this release)" in movers
    assert not [line for line in movers if "Disease" in line]
    assert not [line for line in movers if "All CURIEs" in line]


@pytest.mark.unit
def test_unexplained_movers_is_silent_without_a_build(tmp_path):
    """No CSV means no claim either way, rather than an empty checklist that reads as 'all clear'."""
    assert drn.unexplained_movers(tmp_path) == []
