"""Checks on the coding-agent instruction files (`AGENTS.md`).

Every agent instruction file in this repository is an `AGENTS.md`, and there are no `CLAUDE.md` files
(root `AGENTS.md`, top of the file). Claude Code reads a directory's `AGENTS.md` only when that
directory has no `CLAUDE.md`, so a `CLAUDE.md` added anywhere, by hand or by `/init`, silently hides
the `AGENTS.md` beside it from Claude Code. The root `AGENTS.md` also lists every directory that has
its own `AGENTS.md`, and that list is the only way an agent that doesn't load nested files learns
they exist, so it is checked against the files too.

Both checks ask Git for the tracked files rather than walking the tree, for the reasons in
`_tracked_files()` in `tests/test_docs_links.py`: a walk descends into `babel_downloads/` and
`babel_outputs/`, and an untracked file is nobody else's problem.
"""

import re
import subprocess
from pathlib import Path, PurePosixPath

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).parent.parent
ROOT_AGENTS_MD = REPO_ROOT / "AGENTS.md"
DIRECTORY_SECTION_HEADING = "## Directory-scoped instructions"


def _git_ls_files(pathspec: str) -> list[PurePosixPath]:
    """Tracked files matching a Git pathspec, as repo-relative paths."""
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--", pathspec],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(PurePosixPath(name) for name in listing.split("\0") if name)


def _directories_listed_in_root_agents_md() -> set[str]:
    """Every backticked directory path (one ending in `/`) in root `AGENTS.md`'s directory section."""
    text = ROOT_AGENTS_MD.read_text()
    start = text.index(DIRECTORY_SECTION_HEADING) + len(DIRECTORY_SECTION_HEADING)
    end = text.find("\n## ", start)
    section = text[start:] if end == -1 else text[start:end]
    return set(re.findall(r"`([^`\s]+/)`", section))


# NO CLAUDE.md


def test_no_claude_md_is_tracked():
    """No tracked file should be named CLAUDE.md, in any directory or letter case: Claude Code would
    read it instead of the AGENTS.md beside it."""
    claude_mds = _git_ls_files(":(glob,icase)**/CLAUDE.md")
    assert not claude_mds, (
        f"Found {', '.join(map(str, claude_mds))}. This repository keeps agent instructions in "
        "AGENTS.md only: Claude Code reads a directory's AGENTS.md only when there is no CLAUDE.md "
        "beside it. Merge the file's content into that directory's AGENTS.md (creating one if "
        "needed, and listing it in root AGENTS.md) and delete the CLAUDE.md."
    )


# ROOT AGENTS.md DIRECTORY LIST


def test_root_agents_md_lists_every_nested_agents_md():
    """Root AGENTS.md's "Directory-scoped instructions" list should name exactly the directories that
    hold a tracked AGENTS.md, so neither a new file nor a removed one goes unmentioned."""
    nested = {f"{path.parent}/" for path in _git_ls_files(":(glob)**/AGENTS.md") if path.parent != PurePosixPath(".")}
    listed = _directories_listed_in_root_agents_md()
    assert nested, "Found no nested AGENTS.md at all; is git ls-files working?"
    assert not nested - listed, (
        f"These directories have an AGENTS.md that root AGENTS.md doesn't list under "
        f"{DIRECTORY_SECTION_HEADING!r}: {sorted(nested - listed)}"
    )
    assert not listed - nested, (
        f"Root AGENTS.md lists these directories under {DIRECTORY_SECTION_HEADING!r}, but none has an "
        f"AGENTS.md: {sorted(listed - nested)}"
    )
