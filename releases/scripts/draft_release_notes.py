#!/usr/bin/env python3
"""Draft a combined Babel/NodeNorm/NameRes release note.

Babel ships to Translator as a build plus the NodeNorm and NameRes versions deployed against it, so
a release note has to cover all three repositories. This assembles the mechanical parts of that note
-- the pull request list, the version bumps, the per-compendium count table -- and leaves the
judgement to a human: every PR comes out as an unchecked checklist item to triage, keep or delete.

Everything except the build directory comes from ``releases/releases.yaml``. The entry below the one
being drafted supplies the baselines, so the three PR ranges are derived rather than remembered::

    uv run python releases/scripts/draft_release_notes.py 2026jul22 \\
        --build-dir /path/to/2026jul22 > releases/2026jul22.md

PRs are collected with ``gh api .../compare/BASE...HEAD``, which asks GitHub for the commits reachable
from HEAD but not from BASE. That is the only correct way to do this: NameRes v1.5.2 was cut *after*
v1.6.2 as a maintenance release on the v1.5 line, so neither a version sort nor a date sort produces
the right set. The compare endpoint follows the actual history.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# releases/scripts/draft_release_notes.py -> repo root. Deliberately not `src.util.get_repo_root`:
# this is release engineering, not pipeline code, and importing from `src/` would need a sys.path
# hack to buy a one-liner.
REPO_ROOT = Path(__file__).resolve().parents[2]

# The three repositories a Babel release spans. Hardcoded because they are the definition of a
# Babel release, not a knob: a fourth would need its own section in the note anyway.
REPOS: dict[str, str] = {
    "Babel": "NCATSTranslator/Babel",
    "NodeNorm": "NCATSTranslator/NodeNormalization",
    "NameRes": "NCATSTranslator/NameResolution",
}

# Where a deployed build's outputs live, by build name.
BUILD_URL = "https://stars.renci.org/var/babel_outputs/{build}/"

# config.yaml keys that record an upstream data version, and how to name them in prose. Diffing
# these between the baseline tag and now turns "Updated RxNorm from 01062025 to 03032025" -- written
# by hand in every previous release note -- into something the build itself reports.
VERSION_KEYS = {
    "biolink_version": "the Biolink Model",
    "umls_version": "UMLS",
    "rxnorm_version": "RxNorm",
    "drugbank_version": "DrugBank",
}

# PR titles matching any of these are routine: real changes, but not something a Babel consumer needs
# to read about. They are still listed, just folded away, because "there were no dependency bumps" and
# "the dependency bumps are collapsed" are different claims and only one of them is true.
ROUTINE_TITLE_PATTERNS = [
    re.compile(r"^increment(ed)? version", re.I),
    re.compile(r"^bump ", re.I),
    re.compile(r"^build\(deps", re.I),
    re.compile(r"^update \S+ requirement from", re.I),
    re.compile(r"^upgraded? packages", re.I),
    re.compile(r"^merge (branch|pull request)", re.I),
]
ROUTINE_AUTHORS = {"dependabot[bot]", "dependabot", "github-actions[bot]", "pre-commit-ci[bot]"}

# A squash merge leaves "Title (#123)"; the older merge commits leave "Merge pull request #123 from ...".
_SQUASH_RE = re.compile(r"^(?P<title>.*?)\s*\(#(?P<number>\d+)\)$")
_MERGE_RE = re.compile(r"^Merge pull request #(?P<number>\d+) from ")

# The `## Notable changes` section of the build's own prefix_comparison.md, up to the next heading.
_NOTABLE_RE = re.compile(r"^## Notable changes\s*\n(.*?)(?=^## |\Z)", re.M | re.S)

# Rows of the `## Summary` table. The numbers come from the deployed Redis and Solr instances, which
# this script cannot reach, so it emits the skeleton and leaves the cells blank.
SUMMARY_DB_ROWS = [
    ("id-id", "eq_id_to_id_db"),
    ("id-eq-id", "id_to_eqids_db"),
    ("id-categories", "id_to_type_db"),
    ("semantic-count", "curie_to_bl_type_db"),
    ("info-content", "info_content_db"),
    ("conflation-db", "gene_protein_db"),
    ("chemical-drug-db", "chemical_drug_db"),
    ("Solr", "name_lookup"),
]


@dataclass(frozen=True)
class PullRequest:
    repo_key: str  # "Babel", "NodeNorm", "NameRes"
    repo: str  # "NCATSTranslator/Babel"
    number: int
    title: str
    author: str

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repo}/pull/{self.number}"

    @property
    def is_routine(self) -> bool:
        if self.author in ROUTINE_AUTHORS:
            return True
        return any(pattern.match(self.title) for pattern in ROUTINE_TITLE_PATTERNS)

    def as_markdown(self) -> str:
        return f"- [ ] [{self.repo_key} #{self.number}]({self.url}) — {self.title} (@{self.author})"


def load_manifest(path: Path) -> list[dict]:
    """Read ``releases/releases.yaml`` into a newest-first list of release entries."""
    with open(path) as f:
        return yaml.safe_load(f)["releases"]


def find_release(manifest: list[dict], release_id: str) -> tuple[dict, dict | None]:
    """Return the entry for ``release_id`` and the deployed release it should be compared against.

    The baseline is the nearest *earlier* entry that was actually deployed. Entries marked
    ``deployed: false`` are code releases that never shipped, so they carry no NodeNorm/NameRes
    versions and cannot anchor a comparison.
    """
    ids = [entry["id"] for entry in manifest]
    if release_id not in ids:
        raise ValueError(f"Release {release_id!r} is not in the manifest. Known releases: {', '.join(ids)}")
    index = ids.index(release_id)
    for candidate in manifest[index + 1 :]:
        if candidate.get("deployed", True) and candidate.get("build"):
            return manifest[index], candidate
    return manifest[index], None


def fetch_pull_requests(repo_key: str, repo: str, base: str, head: str) -> list[PullRequest]:
    """List the PRs merged into ``head`` but not ``base``, newest number last.

    Titles and authors come from the commits themselves, so this costs one paginated request per
    repository rather than one per PR.
    """
    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo}/compare/{base}...{head}?per_page=250",
            "--paginate",
            "-q",
            '.commits[] | {m: (.commit.message | split("\\n")[0]), a: (.author.login // .commit.author.name)} | @json',
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    by_number: dict[int, PullRequest] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        commit = json.loads(line)
        message, author = commit["m"], commit["a"] or "unknown"
        squash = _SQUASH_RE.match(message)
        merge = _MERGE_RE.match(message)
        if squash:
            number, title = int(squash.group("number")), squash.group("title")
        elif merge:
            # A merge commit names the PR but not its title; the number is what makes it findable.
            number, title = int(merge.group("number")), message
        else:
            continue
        by_number[number] = PullRequest(repo_key, repo, number, title, author)
    return [by_number[n] for n in sorted(by_number)]


def read_config_versions(config_text: str) -> dict[str, str]:
    """Pull the upstream-data version keys out of a config.yaml's text."""
    config = yaml.safe_load(config_text) or {}
    return {key: str(config[key]) for key in VERSION_KEYS if key in config}


def version_bumps(repo_root: Path, baseline_tag: str) -> list[str]:
    """Prose bullets for every upstream version that changed since ``baseline_tag``."""
    try:
        previous_text = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{baseline_tag}:config.yaml"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return [f"_Could not read `config.yaml` at `{baseline_tag}`; fill in the version bumps by hand._"]

    previous = read_config_versions(previous_text)
    current = read_config_versions((repo_root / "config.yaml").read_text())
    bullets = []
    for key, label in VERSION_KEYS.items():
        was, now = previous.get(key), current.get(key)
        if was and now and was != now:
            bullets.append(f"- Updated {label} from {was} to {now}.")
    return bullets


def build_workarounds(repo_root: Path) -> list[str]:
    """The `build.workarounds` notes recorded in config.yaml for this build."""
    config = yaml.safe_load((repo_root / "config.yaml").read_text()) or {}
    return [str(note) for note in (config.get("build") or {}).get("workarounds") or []]


def notable_changes(build_dir: Path) -> str | None:
    """The `## Notable changes` bullets from the build's own prefix comparison report."""
    path = build_dir / "reports" / "tables" / "prefix_comparison.md"
    if not path.exists():
        return None
    match = _NOTABLE_RE.search(path.read_text())
    return match.group(1).strip() if match else None


def _format_count(value: str) -> str:
    return f"{int(value):,}"


def _format_diff(value: str) -> str:
    """Comma-group a signed difference, escaping a leading minus so Markdown doesn't eat it."""
    number = int(value)
    if number < 0:
        # `\-` keeps the sign visible; a bare leading `-` can be read as a list bullet.
        return f"\\-{abs(number):,}"
    if number > 0:
        return f"+{number:,}"
    return "0"


def _format_percent(value: str) -> str:
    """Match the existing tables: escaped negatives, and a from-zero row reads as Infinity%."""
    if value == "NEW":
        return "Infinity%"
    return f"\\{value}" if value.startswith("-") else value


def summary_of_changes(build_dir: Path, previous_id: str, release_id: str) -> str | None:
    """Rebuild the release note's `Summary of changes` table from the build's comparison CSV.

    The CSV is already the exact comparison the note wants (this build against the baseline pinned in
    config.yaml); this only reformats it -- no numbers are recomputed here.
    """
    path = build_dir / "reports" / "tables" / "prefix_comparison_overall.csv"
    if not path.exists():
        return None

    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            metric = row["Metric"]
            if metric == "All CURIEs":
                label = "Count of CURIEs in all files"
            elif metric.startswith("All cliques"):
                label = "Count of cliques in all files"
            else:
                label = metric.removesuffix(" CURIEs")
            rows.append(
                (
                    label,
                    _format_count(row["Previous"]),
                    _format_count(row["Current"]),
                    _format_diff(row["Absolute change"]),
                    _format_percent(row["Percent change"]),
                )
            )

    header = ["Filename", previous_id, release_id, "Diff", "% Diff"]
    widths = [max(len(header[i]), *(len(r[i]) for r in rows)) for i in range(5)]
    lines = [
        "| " + " | ".join(h.ljust(w) for h, w in zip(header, widths)) + " |",
        "| " + " | ".join("-" * w for w in widths) + " |",
    ]
    lines += ["| " + " | ".join(c.ljust(w) for c, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join(lines)


def provenance_block(entry: dict, previous: dict | None) -> list[str]:
    """The bullet block at the top of the note: what was built, and what was deployed with it."""
    release_id, build = entry["id"], entry.get("build")
    lines = []

    babel_bits = []
    if build:
        babel_bits.append(f"[tagged {build}](https://github.com/{REPOS['Babel']}/releases/tag/{build})")
    if entry.get("babel"):
        version = entry["babel"]
        approx = "approx " if entry.get("approx") else ""
        babel_bits.append(f"{approx}[Babel {version}](https://github.com/{REPOS['Babel']}/releases/tag/{version})")
    if entry.get("branch"):
        babel_bits.append(f"branch `{entry['branch']}`")
    target = f"[{build}]({BUILD_URL.format(build=build)})" if build else release_id
    lines.append(f"- Babel: {target}" + (f" ({', '.join(babel_bits)})" if babel_bits else ""))
    if entry.get("biolink"):
        lines.append(f"  - Built against Biolink Model v{entry['biolink']}")
    lines.append(f"  - [CURIE summary](./summaries/{release_id}.json)")
    lines.append(f"  - [Prefix report](./prefix_reports/{release_id}.json)")

    for key, repo_key in (("nodenorm", "NodeNorm"), ("nameres", "NameRes")):
        versions = entry.get(key) or []
        if not versions:
            continue
        links = ", ".join(f"[{v}](https://github.com/{REPOS[repo_key]}/releases/tag/{v})" for v in versions)
        lines.append(f"- {repo_key}: {links}")

    lines.append("")
    lines.append("Next release: _None as yet_")
    if previous:
        lines.append(f"Previous release: [{previous['title']}](./{previous['id']}.md)")
    return lines


def pull_request_sections(prs_by_repo: dict[str, list[PullRequest]]) -> list[str]:
    """The triage checklist: every PR in the release, substantive ones first, routine ones folded."""
    lines = [
        "## All changes in this release",
        "",
        "Every pull request between this release and the previous one, for triage: promote what",
        "matters into the sections above, then delete the rest of this section before publishing.",
    ]
    for repo_key, prs in prs_by_repo.items():
        substantive = [pr for pr in prs if not pr.is_routine]
        routine = [pr for pr in prs if pr.is_routine]
        lines += ["", f"### {repo_key} ({len(prs)} PRs)", ""]
        lines += [pr.as_markdown() for pr in substantive] or ["_No substantive changes._"]
        if routine:
            # A plain sub-heading rather than a <details> block: rumdl's MD033 rejects inline HTML,
            # and this section is deleted before publishing anyway.
            plural = "" if len(routine) == 1 else "s"
            lines += [
                "",
                f"#### {len(routine)} routine {repo_key} change{plural}",
                "",
                "Dependency bumps, version increments and merge commits.",
                "",
            ]
            lines += [pr.as_markdown() for pr in routine]
    return lines


def draft(entry: dict, previous: dict | None, build_dir: Path | None, repo_root: Path) -> str:
    release_id = entry["id"]
    lines = [f"# {entry['title']}", ""]
    lines += provenance_block(entry, previous)

    if previous:
        prs_by_repo: dict[str, list[PullRequest]] = {}
        for repo_key, repo in REPOS.items():
            base, head = _range_for(repo_key, entry, previous)
            if base and head:
                prs_by_repo[repo_key] = fetch_pull_requests(repo_key, repo, base, head)
    else:
        prs_by_repo = {}

    bumps = version_bumps(repo_root, previous["build"]) if previous else []
    workarounds = build_workarounds(repo_root)
    notable = notable_changes(build_dir) if build_dir else None
    table = summary_of_changes(build_dir, previous["id"], release_id) if build_dir and previous else None

    lines += ["", "## Bugfixes", "", "- _TODO_.", "", "## Updates", ""]
    lines += bumps or ["- _TODO_."]
    lines += ["", "## New features", "", "- _TODO_."]

    if workarounds:
        lines += ["", "## Known issues and caveats", ""]
        lines += [f"- {note}" for note in workarounds]

    if notable:
        lines += [
            "",
            "## Areas that changed substantially",
            "",
            "Straight from this build's own `reports/tables/prefix_comparison.md`. Every large change",
            "here should trace back to a pull request below; one that doesn't is a bug to file before",
            "this release ships.",
            "",
            notable,
        ]

    lines += ["", *pull_request_sections(prs_by_repo)]

    lines += [
        "",
        "## Summary",
        "",
        "<!-- TODO: fill in from the deployed Redis and Solr instances. -->",
        "",
        "| Database name    | Database ID         | Number of keys | Memory used |",
        "|------------------|---------------------|----------------|-------------|",
    ]
    lines += [f"| {name:<16} | {db:<19} |                |             |" for name, db in SUMMARY_DB_ROWS]

    lines += ["", "## Summary of changes", ""]
    lines += [table] if table else ["_TODO: no `prefix_comparison_overall.csv` found in the build directory._"]

    return "\n".join(lines) + "\n"


def _range_for(repo_key: str, entry: dict, previous: dict) -> tuple[str | None, str | None]:
    """The (base, head) refs to compare for one repository.

    For Babel that is the two build tags. For NodeNorm and NameRes it is the *last* version deployed
    against each build, since a build can outlive several service releases.
    """
    if repo_key == "Babel":
        return previous.get("build"), entry.get("build")
    key = repo_key.lower()
    base, head = previous.get(key) or [], entry.get(key) or []
    return (base[-1] if base else None), (head[-1] if head else None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("release", help="Release id to draft, as listed in releases/releases.yaml (e.g. 2026jul22).")
    parser.add_argument(
        "--build-dir",
        type=Path,
        help="A copy of the build's output directory, used for reports/tables/. Without it the count "
        "table and the notable-changes section are left as TODOs.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to releases.yaml (default: releases/releases.yaml in the repo root).",
    )
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    manifest_path = args.manifest or repo_root / "releases" / "releases.yaml"
    entry, previous = find_release(load_manifest(manifest_path), args.release)
    if args.build_dir and not args.build_dir.is_dir():
        parser.error(f"--build-dir {args.build_dir} is not a directory")

    print(draft(entry, previous, args.build_dir, repo_root), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
