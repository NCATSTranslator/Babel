"""Unit tests for the babel-overused-xrefs CLI wrapper.

The analysis itself is tested in tests/model/test_concords.py; these cover the argparse/CSV layer
and the one guard that stops a regenerated audit from silently losing its labels.
"""

import pytest

from src.tools.overused_xrefs.cli import resolve_labels

# One MRCONSO row, copied verbatim from babel_downloads/UMLS/MRCONSO.RRF (UMLS 2026AA) for
# G11.4 "Hereditary spastic paraplegia".
_MRCONSO_ROW = (
    "C0037773|ENG|P|L0037773|VCW|S0377908|N|A17774363|||G11.4|ICD10CM|PT|G11.4|Hereditary spastic paraplegia|4|N||\n"
)


@pytest.fixture
def mrconso(tmp_path):
    path = tmp_path / "MRCONSO.RRF"
    path.write_text(_MRCONSO_ROW)
    return str(path)


@pytest.mark.unit
def test_mrconso_labels_are_used_when_they_resolve(mrconso, tmp_path):
    """The ordinary case: a CURIE with no per-prefix labels file is labelled from MRCONSO."""
    labels = resolve_labels({"ICD10:G11.4"}, tmp_path, mrconso=mrconso)

    assert labels == {"ICD10:G11.4": "Hereditary spastic paraplegia"}


@pytest.mark.unit
def test_an_mrconso_that_resolves_nothing_raises(tmp_path):
    """Passing --mrconso and getting zero labels back must fail, not warn.

    That means the file is not the one the caller thinks it is -- truncated, a different release,
    or an RRF that is not MRCONSO. The audit would otherwise be regenerated as a page of bare
    codes and committed as though it were a real result."""
    empty = tmp_path / "MRCONSO.RRF"
    empty.write_text("")

    with pytest.raises(RuntimeError, match="resolved no labels at all"):
        resolve_labels({"ICD10:G11.4"}, tmp_path, mrconso=str(empty))


@pytest.mark.unit
def test_no_mrconso_is_not_an_error(tmp_path):
    """Without --mrconso, unlabelled CURIEs are expected -- the tool warns and carries on."""
    assert resolve_labels({"ICD10:G11.4"}, tmp_path) == {}


@pytest.mark.unit
def test_nothing_missing_means_mrconso_is_never_consulted(tmp_path, mrconso):
    """The guard must not fire when there was nothing to look up: a CURIE already labelled from a
    per-prefix file never reaches MRCONSO, so an unrelated file cannot fail the run."""
    (tmp_path / "ICD10").mkdir()
    (tmp_path / "ICD10" / "labels").write_text("ICD10:G11.4\tfrom the labels file\n")

    assert resolve_labels({"ICD10:G11.4"}, tmp_path, mrconso=mrconso) == {"ICD10:G11.4": "from the labels file"}
