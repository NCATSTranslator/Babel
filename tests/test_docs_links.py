"""Checks on the links in our documentation.

Ported from NameResolution's tests/test_docs_links.py so that Babel, NodeNorm and NameRes enforce
the same rules. Keep them in sync when any of them changes. Babel has no API server, so the check
those two have on endpoint-description anchors has no equivalent here; instead the `master` ban
also covers the pipeline source, which reports URLs to users.

Everything here is offline: it resolves relative paths and heading anchors on disk and greps for a
banned URL form. Nothing fetches a URL, because a test that fails when GitHub is slow is a test
people learn to ignore.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

#: Directories that are not ours to check: virtualenvs, and the gitignored working data directory,
#: which accumulates generated reports and scratch PR bodies.
EXCLUDED = {"venv", ".venv", "node_modules", ".git", ".pytest_cache", "data", "babel_outputs",
            "babel_downloads"}


def _ours(path):
    return not any(part in EXCLUDED for part in path.parts)


MARKDOWN_FILES = sorted(p for p in REPO_ROOT.rglob("*.md") if _ours(p))

#: Pipeline source that carries URLs -- snakefiles report download and provenance URLs to users,
#: and CITATION.cff carries the canonical repository URL that Zenodo reads.
SOURCE_WITH_LINKS = sorted(
    [p for p in REPO_ROOT.rglob("*.snakefile") if _ours(p)]
    + [p for p in (REPO_ROOT / "src").rglob("*.py") if _ours(p)]
    + [REPO_ROOT / "CITATION.cff"]
)

INLINE_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#+\s+(.*)$", re.MULTILINE)

#: A GitHub link pinned to `master`, in either the blob or the raw form. Scoped to NCATSTranslator
#: on purpose: biolink-model really does default to master, and TranslatorSRI/babel-validation is
#: genuinely still under that org rather than being a stale reference.
MASTER_LINK = re.compile(
    r"github\.com/NCATSTranslator/[^/\s]+/blob/master/"
    r"|raw\.githubusercontent\.com/NCATSTranslator/[^/\s]+/master/",
    re.IGNORECASE,
)


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
        for target in INLINE_LINK.findall(path.read_text()):
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
        for target in INLINE_LINK.findall(path.read_text()):
            if "#" not in target or target.startswith(("http://", "https://", "mailto:")):
                continue
            rel, _, anchor = target.partition("#")
            if not anchor:
                continue
            target_path = path if rel == "" else (path.parent / rel)
            if target_path.suffix != ".md" or not target_path.exists():
                continue
            if anchor not in anchors_for(target_path.read_text()):
                broken.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert not broken, "Anchors with no matching heading:\n  " + "\n  ".join(broken)


def test_no_master_branch_links():
    """Babel, NodeNormalization and NameResolution all default to `main`. A master URL resolves
    only through GitHub's post-rename redirect, so it looks fine right up until that redirect goes
    away."""
    offenders = []
    for path in MARKDOWN_FILES + SOURCE_WITH_LINKS:
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text().splitlines(), start=1):
            if MASTER_LINK.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}")
    assert not offenders, "Links pinned to `master` instead of `main`:\n  " + "\n  ".join(offenders)


#: The three repositories that moved from the TranslatorSRI org to NCATSTranslator. Scoped to
#: these by name on purpose -- TranslatorSRI/babel-validation, referenced from docs/Deployment.md,
#: docs/Triage.md and src/exporters/sapbert.py, really does still live under that org. A blanket
#: ban on the string would push someone to "fix" those correct links into 404s.
MOVED_TO_NCATSTRANSLATOR = re.compile(r"TranslatorSRI/(Babel|NameResolution|NodeNormalization)\b")


def test_no_stale_org_links():
    """These three repositories are under NCATSTranslator now. The old URLs resolve through
    GitHub's org-rename redirect, which is more durable than the branch-rename one, but they
    still name an org that no longer owns the code. Babel is clean today; this keeps it that
    way, and is the same check NameResolution#262 and NodeNormalization#403 add."""
    offenders = []
    for path in MARKDOWN_FILES + SOURCE_WITH_LINKS:
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text().splitlines(), start=1):
            if MOVED_TO_NCATSTRANSLATOR.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}")
    assert not offenders, (
        "Links naming the pre-rename TranslatorSRI org:\n  " + "\n  ".join(offenders)
    )
