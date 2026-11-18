"""Checks on the coding-agent instruction files (`AGENTS.md`).

Every agent instruction file in this repository is an `AGENTS.md`, and there are no `CLAUDE.md` files
(root `AGENTS.md`, top of the file). Claude Code reads a directory's `AGENTS.md` only when that
directory has no `CLAUDE.md`, so a `CLAUDE.md` added anywhere, by hand or by `/init`, silently hides
the `AGENTS.md` beside it from Claude Code. The root `AGENTS.md` also lists every directory that has
its own `AGENTS.md`, and that list is the only way an agent that doesn't load nested files learns
they exist, so it is checked against the files too.

Every check asks Git for the tracked files rather than walking the tree, through `tracked_files()`
in `tests/conftest.py` (its docstring says why).
"""

import re
from pathlib import PurePosixPath

import pytest

from tests.conftest import REPO_ROOT, tracked_files

pytestmark = pytest.mark.unit

ROOT_AGENTS_MD = REPO_ROOT / "AGENTS.md"
DIRECTORY_SECTION_HEADING = "## Directory-scoped instructions"

# Every file name Claude Code loads as project instructions in place of an AGENTS.md. `.claude/CLAUDE.md`
# needs no pattern of its own: `**/` matches inside dot-directories too.
CLAUDE_INSTRUCTION_PATHSPECS = (":(glob,icase)**/CLAUDE.md", ":(glob,icase)**/CLAUDE.local.md")

# Every AGENTS.md in any letter case, so a misspelt `agents.md` is caught rather than overlooked.
AGENTS_MD_PATHSPEC = ":(glob,icase)**/AGENTS.md"


def _repo_relative(*pathspecs: str) -> list[PurePosixPath]:
    """Tracked files matching any of `pathspecs`, as repo-relative POSIX paths."""
    return [PurePosixPath(path.relative_to(REPO_ROOT).as_posix()) for path in tracked_files(*pathspecs)]


def _directories_listed_in_root_agents_md() -> set[str]:
    """The directories named by the list items in root `AGENTS.md`'s directory section.

    Each item names its directories in backticks before an em-dash and describes them after it
    (`` - `src/tools/` (plus `src/tools/slurm/`) — the convention ``). Only that head counts, so a
    directory mentioned in a description, or in prose around the list, isn't taken as listed.
    """
    text = ROOT_AGENTS_MD.read_text(encoding="utf-8")
    start = text.index(DIRECTORY_SECTION_HEADING) + len(DIRECTORY_SECTION_HEADING)
    end = text.find("\n## ", start)
    section = text[start:] if end == -1 else text[start:end]

    # Each top-level list item, with its indented continuation lines.
    items = re.findall(r"^- (.*(?:\n[ \t]+\S.*)*)", section, flags=re.MULTILINE)
    return {directory for item in items for directory in re.findall(r"`([^`\s]+/)`", item.split(" — ", 1)[0])}


# NO CLAUDE.md


def test_no_claude_md_is_tracked():
    """No tracked file should be named CLAUDE.md or CLAUDE.local.md, in any directory (`.claude/`
    included) or letter case: Claude Code would read it instead of the AGENTS.md beside it."""
    claude_mds = _repo_relative(*CLAUDE_INSTRUCTION_PATHSPECS)
    assert not claude_mds, (
        f"Found {', '.join(map(str, claude_mds))}. This repository keeps agent instructions in "
        "AGENTS.md only: Claude Code reads a directory's AGENTS.md only when there is no CLAUDE.md "
        "beside it. Merge the file's content into that directory's AGENTS.md (creating one if "
        "needed, and listing it in root AGENTS.md) and delete the CLAUDE.md."
    )


# AGENTS.md SPELLING


def test_every_agents_md_is_spelt_in_capitals():
    """Every agent instruction file should be named exactly AGENTS.md: on a case-sensitive file
    system an agent looking for AGENTS.md won't find an `agents.md` or `Agents.md`."""
    misspelt = [path for path in _repo_relative(AGENTS_MD_PATHSPEC) if path.name != "AGENTS.md"]
    assert not misspelt, f"Rename these to AGENTS.md: {', '.join(map(str, misspelt))}"


# ROOT AGENTS.md DIRECTORY LIST


def test_root_agents_md_lists_every_nested_agents_md():
    """Root AGENTS.md's "Directory-scoped instructions" list should name exactly the directories that
    hold a tracked AGENTS.md (in any letter case), so neither a new file nor a removed one goes
    unmentioned."""
    nested = {f"{path.parent}/" for path in _repo_relative(AGENTS_MD_PATHSPEC) if path.parent != PurePosixPath(".")}
    listed = _directories_listed_in_root_agents_md()
    assert nested, "Found no nested AGENTS.md at all; is git ls-files working?"
    assert not nested - listed, (
        f"These directories have an AGENTS.md that root AGENTS.md doesn't list under "
        f"{DIRECTORY_SECTION_HEADING!r}: {sorted(nested - listed)}. Add a list item naming the "
        "directory in backticks before the em-dash."
    )
    assert not listed - nested, (
        f"Root AGENTS.md lists these directories under {DIRECTORY_SECTION_HEADING!r}, but none has an "
        f"AGENTS.md: {sorted(listed - nested)}"
    )
