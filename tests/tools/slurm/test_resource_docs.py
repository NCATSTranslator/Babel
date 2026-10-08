"""Drift guard: `slurm/README.md`'s hotspot table must match the snakefiles it documents.

That table is what an operator reads before deciding whether a rule can be given less memory, so a
row that disagrees with the rule sends them after a setting that isn't there. It drifts silently --
nothing else reads it -- and it drifted four ways at once while PR #983 was being reviewed: two rows
introduced by that branch (`untyped_chemical_compendia` listed 192G against a `mem="184G"` rule) and
two that predated it (`chemical_compendia` declares `runtime="7h"` while the README said 6h, and
`generate_curie_report`/`generate_clique_leader_report` had been merged into `generate_prefix_report`
without the table noticing).

The declared side is read with the same parser `babel-slurm-resources` uses, so a regex change that
stops matching real declarations fails here too -- see
`test_read_snakefile_resources_matches_the_real_snakefiles` in `test_parse.py` for the other half.
"""

import re

import pytest

from src.tools.slurm.parse import read_snakefile_resources
from src.util import get_repo_root

pytestmark = pytest.mark.unit

README = get_repo_root() / "slurm" / "README.md"
SNAKEFILE_DIR = get_repo_root() / "src" / "snakefiles"

#: The hotspot table's heading, so a second table elsewhere in the README with the same row shape
#: can't quietly join the checks. The section runs to the next `## `.
_SECTION_RE = re.compile(r"^## Known Resource Hotspots\s*$.*?(?=^## |\Z)", re.M | re.S)
#: `| `rule` | `file.snakefile` | 512G | 12h | Notes |` -- the four columns the snakefiles can confirm.
_ROW_RE = re.compile(r"^\| `(\w+)` \| `([\w.]+)` \| ([^|]+?) \| ([^|]+?) \|", re.M)


def _fmt_mem(mb: int | None) -> str:
    return "—" if mb is None else f"{mb // 1000}G"


def _fmt_runtime(minutes: int | None) -> str:
    if minutes is None:
        return "—"
    return f"{minutes // 60}h" if minutes % 60 == 0 else f"{minutes}m"


def _rows():
    section = _SECTION_RE.search(README.read_text(encoding="utf-8"))
    assert section, "slurm/README.md has no `## Known Resource Hotspots` section for this guard to read"
    return _ROW_RE.findall(section.group(0))


def test_the_hotspot_table_was_found():
    """Guard the guard: a table reformat that breaks the row regex must fail loudly, not silently
    check zero rows and pass."""
    assert len(_rows()) > 20


def test_every_documented_rule_still_exists():
    """A rule that was renamed or merged away leaves a row pointing at nothing."""
    declared = read_snakefile_resources(SNAKEFILE_DIR)
    missing = [rule for rule, _file, _mem, _runtime in _rows() if rule not in declared]
    assert not missing, "slurm/README.md documents rules that no longer exist: " + ", ".join(missing)


def test_documented_mem_and_runtime_match_the_snakefiles():
    """Each row's `mem`/`runtime` must be what the rule actually declares.

    A row reading `512G / 128G` documents a `mem=lambda wildcards: ...`, which has no single declared
    value; the parser reports None for it, so those are checked for existence only.
    """
    declared = read_snakefile_resources(SNAKEFILE_DIR)
    wrong = []
    for rule, _file, mem, runtime in _rows():
        rule_decl = declared.get(rule)
        if rule_decl is None:
            continue  # covered by test_every_documented_rule_still_exists
        mem, runtime = mem.strip(), runtime.strip()
        if "/" not in mem and mem != _fmt_mem(rule_decl.mem_mb):
            wrong.append(f"{rule}: README mem={mem}, snakefile declares {_fmt_mem(rule_decl.mem_mb)}")
        if runtime != _fmt_runtime(rule_decl.runtime_min):
            wrong.append(f"{rule}: README runtime={runtime}, snakefile declares {_fmt_runtime(rule_decl.runtime_min)}")
    assert not wrong, "slurm/README.md disagrees with the snakefiles:\n  " + "\n  ".join(wrong)


def test_documented_files_are_where_the_rule_lives():
    """The `File` column has to name the snakefile the rule is actually in."""
    wrong = []
    for rule, filename, _mem, _runtime in _rows():
        path = SNAKEFILE_DIR / filename
        if not path.exists():
            wrong.append(f"{rule}: {filename} does not exist")
        elif not re.search(rf"^(?:rule|checkpoint)\s+{re.escape(rule)}\s*:", path.read_text(), re.M):
            wrong.append(f"{rule}: not defined in {filename}")
    assert not wrong, "slurm/README.md points at the wrong snakefile:\n  " + "\n  ".join(wrong)
