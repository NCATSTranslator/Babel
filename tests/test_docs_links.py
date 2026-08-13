"""Checks on the links in our documentation.

Ported from NameResolution's tests/test_docs_links.py so that Babel, NodeNorm and NameRes enforce
the same rules. Keep them in sync when any of them changes. Babel has no API server, so the check
those two have on endpoint-description anchors has no equivalent here; instead the banned-URL scan
also covers the pipeline source, which reports URLs to users.

Everything here is offline: it resolves relative paths and heading anchors on disk and greps for
banned URL forms. Nothing fetches a URL, because a test that fails when GitHub is slow is a test
people learn to ignore.

Two known approximations, both chosen to keep the check cheap. Links inside fenced code blocks are
treated as real links, so a document demonstrating Markdown syntax has to use a target that exists;
and `anchors_for()` does not model GitHub's `-1` suffix for repeated headings, so a link to the
second `## Notes` in a file will look broken.
"""

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).parent.parent


def _tracked_files():
    """Every file Git tracks, as absolute paths.

    Asking Git rather than walking the tree is what keeps this off `babel_downloads/`,
    `babel_outputs/`, `.venv/` and `data/`: an `rglob("*")` from the repo root descends into all of
    them before anything can filter them out, which on a machine with a finished build is a
    multi-million-file walk — at import time, so even a run that deselects these tests pays for it.
    Untracked files can't carry a link anyone will follow, so Git's index is also the right scope.
    """
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # An index entry can outlive the file (deleted in the working tree, deletion not yet staged).
    return sorted(p for p in (REPO_ROOT / name for name in listing.split("\0") if name) if p.is_file())


def _is_archived_build_report(path: Path) -> bool:
    """Whether ``path`` is a build artifact copied verbatim into ``releases/<build>/``.

    Those files are byte-for-byte copies of what a build wrote (see `releases/ARTIFACTS.md`), so a
    URL inside one is a record of what the build recorded, not a link this repository is offering.
    Two provenance YAMLs carry a `master`-pinned upstream URL for exactly that reason. Editing them
    to satisfy this guard would make the archive disagree with the build it claims to be a subset
    of, which is the one property the whole layout rests on.
    """
    parts = path.relative_to(REPO_ROOT).parts
    return len(parts) > 2 and parts[0] == "releases" and parts[2] in {"reports", "metadata"}


TRACKED_FILES = [p for p in _tracked_files() if not _is_archived_build_report(p)]

MARKDOWN_FILES = [p for p in TRACKED_FILES if p.suffix == ".md"]

#: Everything else that can carry a GitHub link: snakefiles report download and provenance URLs to
#: users, and CITATION.cff carries the canonical repository URL that Zenodo reads. Globbed by
#: extension rather than listed, because an explicit list is exactly what let a stale Colab badge
#: and a wrong CITATION.cff sit unnoticed in sibling repos. Scanned only for banned URL forms --
#: relative links and heading anchors are a Markdown concern.
LINK_BEARING_SUFFIXES = {".py", ".yml", ".yaml", ".ipynb", ".cff", ".xml", ".sh", ".toml", ".snakefile"}

SOURCE_WITH_LINKS = [
    p
    for p in TRACKED_FILES
    # This file quotes the banned forms as regex source; excluding it is more honest than relying on
    # the backslashes in those patterns to keep them from matching themselves.
    if p != Path(__file__)
    and (p.suffix in LINK_BEARING_SUFFIXES or p.name.startswith("Dockerfile") or p.name == "Snakefile")
]

INLINE_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#+\s+(.*)$", re.MULTILINE)

#: A GitHub link pinned to `master`, in the blob, tree and raw forms, with or without a path after
#: the branch. Scoped to NCATSTranslator on purpose: biolink-model really does default to master,
#: and TranslatorSRI/babel-validation is genuinely still under that org rather than being a stale
#: reference. `(?![\w-])` rather than `\b` so that a branch actually named `master-something` is
#: left alone.
MASTER_LINK = re.compile(
    r"github\.com/NCATSTranslator/[^/\s]+/(blob|tree|raw)/master(?![\w-])"
    r"|raw\.githubusercontent\.com/NCATSTranslator/[^/\s]+/master(?![\w-])",
    re.IGNORECASE,
)

#: The three repositories that moved from the TranslatorSRI org to NCATSTranslator. Scoped to
#: these by name on purpose -- TranslatorSRI/babel-validation, referenced from docs/Deployment.md,
#: docs/Triage.md and src/exporters/sapbert.py, really does still live under that org. A blanket
#: ban on the string would push someone to "fix" those correct links into 404s.
MOVED_TO_NCATSTRANSLATOR = re.compile(r"TranslatorSRI/(Babel|NameResolution|NodeNormalization)\b")

#: Each banned URL form, paired with the message shown when one turns up.
BANNED_LINKS = [
    pytest.param(
        MASTER_LINK,
        # Babel, NodeNormalization and NameResolution all default to `main`. A master URL resolves
        # only through GitHub's post-rename redirect, so it looks fine right up until that redirect
        # goes away.
        "Links pinned to `master` instead of `main`",
        id="master-branch",
    ),
    pytest.param(
        MOVED_TO_NCATSTRANSLATOR,
        # The org-rename redirect is more durable than the branch-rename one, but these URLs still
        # name an org that no longer owns the code. Babel is clean today; this keeps it that way,
        # and is the same check NameResolution#262 and NodeNormalization#403 add.
        "Links naming the pre-rename TranslatorSRI org",
        id="stale-org",
    ),
]


def anchors_for(markdown_text):
    """The anchor slugs GitHub generates for a document's headings."""
    slugs = set()
    for heading in HEADING.findall(markdown_text):
        slug = re.sub(r"[`*]", "", heading.strip().lower())
        slug = re.sub(r"[^a-z0-9 _-]", "", slug)
        slugs.add(slug.replace(" ", "-"))
    return slugs


def test_relative_links_resolve():
    """A relative link is written relative to the file it sits in, which is easy to get wrong when
    a document moves between docs/ and docs/sources/."""
    broken = []
    for path in MARKDOWN_FILES:
        for target in INLINE_LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            resolved = (path.parent / target.split("#")[0]).resolve()
            if not resolved.exists():
                broken.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert not broken, "Relative links that do not resolve:\n  " + "\n  ".join(broken)


def test_anchors_resolve():
    """Anchors are case-sensitive and GitHub lower-cases them, so `#Conflation` silently lands at
    the top of the page rather than at the heading."""
    broken = []
    for path in MARKDOWN_FILES:
        for target in INLINE_LINK.findall(path.read_text(encoding="utf-8")):
            if "#" not in target or target.startswith(("http://", "https://", "mailto:")):
                continue
            rel, _, anchor = target.partition("#")
            if not anchor:
                continue
            target_path = path if rel == "" else (path.parent / rel)
            if target_path.suffix != ".md" or not target_path.exists():
                continue
            if anchor not in anchors_for(target_path.read_text(encoding="utf-8")):
                broken.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert not broken, "Anchors with no matching heading:\n  " + "\n  ".join(broken)


@pytest.mark.parametrize("pattern,message", BANNED_LINKS)
def test_no_banned_links(pattern, message):
    """A URL form we have decided not to use should not appear in any documentation or in the
    pipeline source that reports URLs to users."""
    offenders = []
    for path in MARKDOWN_FILES + SOURCE_WITH_LINKS:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}")
    assert not offenders, f"{message}:\n  " + "\n  ".join(offenders)
