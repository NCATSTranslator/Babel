"""Tests for src/util.py helpers."""

import pytest

from src.util import _biolink_ref, ensure_parent_dir


@pytest.mark.unit
class TestBiolinkRef:
    """Unit tests for _biolink_ref(), which controls the git ref in GitHub raw URLs."""

    def test_version_number_gets_v_prefix(self):
        assert _biolink_ref("4.3.6") == "v4.3.6"

    def test_version_number_major_minor_gets_v_prefix(self):
        assert _biolink_ref("4.0.0") == "v4.0.0"

    def test_version_3x_gets_v_prefix(self):
        assert _biolink_ref("3.5.4") == "v3.5.4"

    def test_commit_sha_returned_unchanged(self):
        sha = "b0d9ef6494af9b3ab931e9505d446ca8c212f50f"
        assert _biolink_ref(sha) == sha

    def test_commit_sha_does_not_get_v_prefix(self):
        sha = "b0d9ef6494af9b3ab931e9505d446ca8c212f50f"
        assert not _biolink_ref(sha).startswith("v")

    def test_another_sha_returned_unchanged(self):
        sha = "a" * 40
        assert _biolink_ref(sha) == sha

    def test_sha_wrong_length_not_treated_as_sha(self):
        # 39 hex chars — not a valid SHA, treated as a version string.
        not_a_sha = "b0d9ef6494af9b3ab931e9505d446ca8c212f50"
        assert _biolink_ref(not_a_sha) == f"v{not_a_sha}"

    def test_sha_with_uppercase_not_treated_as_sha(self):
        # git SHAs are lowercase; uppercase hex should get v prefix.
        uppercase_sha = "B0D9EF6494AF9B3AB931E9505D446CA8C212F50F"
        assert _biolink_ref(uppercase_sha) == f"v{uppercase_sha}"


@pytest.mark.network
class TestGetBiolinkModelToolkitNetwork:
    """Network tests verifying that toolkit loading works for both version strings and SHAs."""

    def test_toolkit_loads_with_version_number(self):
        """get_biolink_model_toolkit() should succeed with a normal version string."""
        from src.util import get_biolink_model_toolkit

        toolkit = get_biolink_model_toolkit("4.4.2")
        assert toolkit is not None
        # Spot-check that the toolkit has a known class.
        element = toolkit.get_element("chemical entity")
        assert element is not None

    def test_toolkit_loads_with_commit_sha(self):
        """get_biolink_model_toolkit() should succeed with a 40-char commit SHA (no leading v)."""
        from src.util import get_biolink_model_toolkit

        # This is the SHA set in config.yaml for the 1.17 build (post-4.4.2 commit).
        sha = "b0d9ef6494af9b3ab931e9505d446ca8c212f50f"
        toolkit = get_biolink_model_toolkit(sha)
        assert toolkit is not None
        element = toolkit.get_element("chemical entity")
        assert element is not None


@pytest.mark.unit
class TestEnsureParentDir:
    """Unit tests for ensure_parent_dir(), which every output-writing module calls before writing."""

    def test_missing_parents_are_created(self, tmp_path):
        """A path several directories deep should have all of its parents created."""
        output_file = tmp_path / "does" / "not" / "exist" / "output.txt"
        ensure_parent_dir(str(output_file))
        assert output_file.parent.is_dir()

    def test_existing_parent_is_not_an_error(self, tmp_path):
        """An already-existing parent directory should be left alone rather than raising."""
        output_file = tmp_path / "output.txt"
        ensure_parent_dir(str(output_file))
        assert tmp_path.is_dir()

    def test_bare_filename_does_not_raise(self, tmp_path, monkeypatch):
        """A bare filename has no directory component (os.path.dirname returns ''), and
        os.makedirs('') raises FileNotFoundError even though the path is valid in the CWD --
        so this should be a no-op rather than an error."""
        monkeypatch.chdir(tmp_path)
        ensure_parent_dir("output.txt")
        assert list(tmp_path.iterdir()) == []
