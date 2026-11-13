"""Checks on config.yaml itself, rather than on any one setting in it."""

import re

import pytest

from src.util import get_config, get_repo_root

# Where a config key can be read: the build's Python and Snakemake code, and the test fixtures that locate a
# build's files (compendium_directories is read only by tests/pipeline/conftest.py).
CODE_GLOBS = ["src/**/*.py", "src/**/*.snakefile", "Snakefile", "tests/**/conftest.py"]


@pytest.mark.unit
def test_every_top_level_config_key_is_read_somewhere():
    """Every top-level key in config.yaml should be looked up -- as ``["key"]`` or ``.get("key"`` -- somewhere in
    the code. A key nothing reads is dead config that still reads as a setting someone could change (`http: {}`
    outlived the code that read it by months), so delete it rather than leave it here. Only lookups count: a
    short key such as ``http`` is quoted in the code for unrelated reasons."""
    root = get_repo_root()
    code = "\n".join(path.read_text() for pattern in CODE_GLOBS for path in sorted(root.glob(pattern)))
    unread = [
        key
        for key in get_config()
        if not re.search(rf"""\[\s*["']{re.escape(key)}["']\s*\]|\.get\(\s*["']{re.escape(key)}["']""", code)
    ]
    assert unread == []
