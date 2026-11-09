"""Tests for the build-report archiver (``releases/scripts/archive_build.py``).

The two behaviours worth pinning are the ones that protect the repository from a bad archive: the
size cap that keeps a 200 MB DuckDB dump out of git, and the check that the prefix report is stamped
with the release it is being filed under.
"""

import importlib.util
import json
import sys

import pytest

from src.util import get_repo_root

_SCRIPT = get_repo_root() / "releases" / "scripts" / "archive_build.py"


def _load_module():
    """Import the script by path: `releases/` is deliberately not a package under `src/`."""
    spec = importlib.util.spec_from_file_location("archive_build", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


abd = _load_module()


def _make_build(tmp_path, name="2026jul22", extras=True):
    """A build directory holding every manifest file, plus the junk a real build has beside them.

    Named after the stamped release so one test can build both a good and a bad one.
    """
    build = tmp_path / f"build-{name}"
    for rel in abd.REQUIRED_FILES:
        path = build / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}" if rel.endswith(".json") else "a,b\n1,2\n")
    (build / abd.PREFIX_REPORT).write_text(json.dumps({"name": name}))
    for compendium in ("Protein", "Disease"):
        (build / "metadata" / f"{compendium}.txt.yaml").parent.mkdir(parents=True, exist_ok=True)
        (build / "metadata" / f"{compendium}.txt.yaml").write_text("counts:\n  cliques: 1\n")
        (build / "reports" / "content" / "compendia" / f"{compendium}.json").parent.mkdir(parents=True, exist_ok=True)
        (build / "reports" / "content" / "compendia" / f"{compendium}.json").write_text("{}")
    if extras:
        # The things a real build directory has that must never be archived.
        (build / "reports" / "duckdb" / "identically_labeled_cliques.tsv").write_text("huge\n")
        (build / "logs").mkdir(exist_ok=True)
        (build / "logs" / "sbatch.err").write_text("noise\n")
        (build / "reports" / "SmallMolecule.txt").write_text("clusters\n")
    return build


def _manifest(tmp_path, build="2026jul22", release_id="2026jul22"):
    path = tmp_path / "releases.yaml"
    path.write_text(f"releases:\n  - id: {release_id}\n    build: {build}\n")
    return path


@pytest.mark.unit
def test_manifest_takes_the_summary_files_and_nothing_else(tmp_path):
    """Only the declared subset is archived -- not the logs, the cluster histograms, or the dumps."""
    build = _make_build(tmp_path)

    paths = abd.resolve_manifest(build)

    assert set(abd.REQUIRED_FILES) <= set(paths)
    assert "metadata/Protein.txt.yaml" in paths
    assert "reports/content/compendia/Disease.json" in paths
    assert not [p for p in paths if p.startswith("logs/")]
    assert "reports/duckdb/identically_labeled_cliques.tsv" not in paths
    assert "reports/SmallMolecule.txt" not in paths


@pytest.mark.unit
def test_a_missing_required_file_names_every_one_that_is_missing(tmp_path):
    """One report per run, not one per re-run: an incomplete build should fail once, informatively."""
    build = _make_build(tmp_path)
    (build / "reports/tables/prefix_table.csv").unlink()
    (build / "reports/tables/cliques_table.csv").unlink()

    with pytest.raises(FileNotFoundError, match="prefix_table.csv.*cliques_table.csv|cliques_table.csv"):
        abd.resolve_manifest(build)


@pytest.mark.unit
def test_a_prefix_report_stamped_with_the_wrong_release_is_refused(tmp_path):
    """The trap this check exists for: 2026jul22 shipped stamped `2026jul15`.

    `name` is written from config.yaml's `release_name` at build time, and it labels the baseline in
    the *next* release's comparison -- so a wrong value propagates forward silently.
    """
    build = _make_build(tmp_path, name="2026jul15")

    with pytest.raises(ValueError, match="stamped name='2026jul15'"):
        abd.check_prefix_report_name(build, "2026jul22")

    abd.check_prefix_report_name(_make_build(tmp_path, name="2026jul22"), "2026jul22")


@pytest.mark.unit
def test_a_file_over_the_cap_is_left_out_and_reported(tmp_path):
    """The cap is what stops a widened glob committing `identically_labeled_cliques.tsv.gz` (200 MB)."""
    build = _make_build(tmp_path)
    (build / "metadata/Protein.txt.yaml").write_text("x" * 5000)

    to_copy, oversize = abd.plan_copy(build, abd.resolve_manifest(build), max_bytes=1000)

    assert oversize == ["metadata/Protein.txt.yaml"]
    assert "metadata/Protein.txt.yaml" not in to_copy
    assert "metadata/Disease.txt.yaml" in to_copy


@pytest.mark.unit
def test_archiving_mirrors_the_build_layout_and_is_idempotent(tmp_path):
    """Same relative paths on both sides -- that is what makes the archive a usable `--build-dir`."""
    build = _make_build(tmp_path)
    dest = tmp_path / "releases"
    argv = ["2026jul22", "--build-dir", str(build), "--dest-root", str(dest), "--manifest", str(_manifest(tmp_path))]

    assert abd.main(argv) == 0
    archived = dest / "2026jul22"
    for rel in abd.resolve_manifest(build):
        assert (archived / rel).read_bytes() == (build / rel).read_bytes(), rel
    assert not (archived / "logs").exists()

    # Re-running against the same build changes nothing.
    before = {p: p.read_bytes() for p in archived.rglob("*") if p.is_file()}
    assert abd.main(argv) == 0
    assert {p: p.read_bytes() for p in archived.rglob("*") if p.is_file()} == before


@pytest.mark.unit
def test_dry_run_and_a_failed_check_both_write_nothing(tmp_path):
    """A refusal must leave no partial archive behind, which is why the name check is pre-flight."""
    dest = tmp_path / "releases"
    manifest = _manifest(tmp_path)

    ok_build = _make_build(tmp_path)
    assert (
        abd.main(
            [
                "2026jul22",
                "--build-dir",
                str(ok_build),
                "--dest-root",
                str(dest),
                "--manifest",
                str(manifest),
                "--dry-run",
            ]
        )
        == 0
    )
    assert not dest.exists()

    bad_build = _make_build(tmp_path, name="2026jul15")
    assert (
        abd.main(["2026jul22", "--build-dir", str(bad_build), "--dest-root", str(dest), "--manifest", str(manifest)])
        == 1
    )
    assert not dest.exists()


@pytest.mark.unit
def test_a_release_id_resolves_to_its_build_name(tmp_path):
    """Archives are keyed by build: TranslatorFuguJuly2024's artifacts are filed under 2024jul13."""
    manifest = _manifest(tmp_path, build="2024jul13", release_id="TranslatorFuguJuly2024")

    assert abd.build_name_for("TranslatorFuguJuly2024", manifest) == "2024jul13"
    assert abd.build_name_for("2024jul13", manifest) == "2024jul13"  # a build name passes through
    with pytest.raises(ValueError, match="neither a release id nor a build name"):
        abd.build_name_for("nope", manifest)
