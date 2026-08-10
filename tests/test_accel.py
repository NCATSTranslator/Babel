"""Unit tests for src/accel.py, the gateway to the Rust extension.

Rust is the implementation, not an optional overlay: there is no Python fallback and no runtime
toggle. src/accel.py therefore has just two behaviors, each with a consequence that is expensive
to discover late:

- a missing extension must raise, because a Rust toolchain is a hard build prerequisite (#975) --
  anyone who can run Babel at all has the extension, so its absence means the build regressed and
  should fail loudly at DAG-parse time rather than silently produce nothing;
- a stale extension must raise, because the extension is installed editable and a `git pull` does
  not rebuild it, so a silent stale binary could run for a 12-hour rule.

The missing-extension branch is tested by reloading under a patched import; the staleness check is
tested directly against stub modules -- building a genuinely stale extension would mean compiling
Rust inside a unit test.
"""

import builtins
import importlib
import types

import pytest

import src.accel


def reload_accel(monkeypatch, *, hide_extension=False):
    """Re-import src.accel and return the fresh module (letting any import error propagate)."""
    if hide_extension:
        real_import = builtins.__import__

        def fail_on_accel(name, globals=None, locals=None, fromlist=(), level=0):
            if fromlist and "_accel" in fromlist:
                raise ImportError("no compiled extension in this test")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fail_on_accel)

    return importlib.reload(src.accel)


@pytest.fixture(autouse=True)
def restore_accel():
    """Leave src.accel in its real state, so reloads here can't leak into other tests."""
    yield
    importlib.reload(src.accel)


def stub_extension(version):
    """A stand-in for the compiled module, carrying just the attribute the guard reads."""
    module = types.ModuleType("src._accel")
    if version is not None:
        module.ABI_VERSION = version
    return module


# A MISSING BUILD FAILS LOUDLY


@pytest.mark.unit
def test_a_missing_extension_raises(monkeypatch):
    """Without the compiled extension, importing src.accel must raise.

    A Rust toolchain is a hard build prerequisite (#975), so anyone who can run Babel has the
    extension; its absence means the build silently regressed, and failing at DAG-parse time (with
    the ImportError) is better than silently producing nothing.
    """
    with pytest.raises(ImportError):
        reload_accel(monkeypatch, hide_extension=True)


# GUARDING AGAINST A STALE BUILD


@pytest.mark.unit
def test_a_matching_abi_version_is_accepted():
    """The guard returns the module untouched when the versions agree."""
    stub = stub_extension(src.accel._REQUIRED_ABI_VERSION)
    assert src.accel.check_abi_version(stub) is stub


@pytest.mark.unit
@pytest.mark.parametrize(
    "version,description",
    [
        (src.accel._REQUIRED_ABI_VERSION + 1, "extension newer than the checkout"),
        (src.accel._REQUIRED_ABI_VERSION - 1, "extension older than the checkout"),
        (None, "extension predates ABI_VERSION existing at all"),
    ],
)
def test_a_mismatched_abi_version_raises_with_a_rebuild_instruction(version, description):
    """Any mismatch must raise, and the message must say how to fix it.

    The rebuild command is asserted because that is the whole point of the error: the person who
    hits it is mid-run and needs the fix, not a diagnosis.
    """
    assert description  # names the case in the failure output
    with pytest.raises(RuntimeError, match="uv sync --reinstall-package babel-pipeline"):
        src.accel.check_abi_version(stub_extension(version))


@pytest.mark.unit
def test_the_built_extension_matches_the_version_python_expects():
    """The built extension's ABI_VERSION must be the one this checkout expects.

    Every `uv sync` builds the extension (uv bootstraps a Rust toolchain if cargo is missing), so
    its absence means the build silently regressed -- a failure, not a skip, so that regression
    can't hide. Both constants are bumped by hand in the same commit: failing in CI after a Rust
    change means the bump was forgotten; a version mismatch locally means the checkout needs
    `uv sync --reinstall-package babel-pipeline`.
    """
    assert src.accel.accel is not None, "compiled extension not built -- run `uv sync`"
    assert src.accel.accel.ABI_VERSION == src.accel._REQUIRED_ABI_VERSION
