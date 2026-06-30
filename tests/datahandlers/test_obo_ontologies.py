from contextlib import contextmanager

import pytest

from src.categories import CELLULAR_COMPONENT, PHENOTYPIC_FEATURE
from src.createcompendia import diseasephenotype
from src.datahandlers import obo

pytestmark = [pytest.mark.network]


@contextmanager
def _server_errors_are_xfail():
    """Treat endpoint/server instability as xfail, not product failure."""
    try:
        yield
    except Exception as e:
        pytest.xfail(f"UberGraph query failed (server-side issue): {e}")


@pytest.mark.parametrize(
    ("root", "biolink_type", "expected_prefix"),
    [
        ("GO:0005575", CELLULAR_COMPONENT, "GO"),
    ],
)
def test_write_obo_ids_for_registered_ontology(tmp_path, root, biolink_type, expected_prefix):
    outfile = tmp_path / f"{expected_prefix}.ids.tsv"
    with _server_errors_are_xfail():
        obo.write_obo_ids([(root, biolink_type)], str(outfile), [biolink_type])

    lines = [line.strip() for line in outfile.read_text().splitlines() if line.strip()]
    assert lines, f"{expected_prefix} write_obo_ids returned no rows"
    prefixes = {line.split("\t", 1)[0].split(":", 1)[0] for line in lines}
    assert prefixes == {expected_prefix}


def test_write_mp_ids_collects_subclass_hierarchy(tmp_path):
    """MP is a standard rdfs:subClassOf hierarchy rooted at MP:0000001.

    Unlike EMAPA (a part_of partonomy), the default subClassOf walk reaches every MP
    term, so write_mp_ids() uses get_subclasses_of() with the default predicate. The
    lower bound guards against a regression where the root or hierarchy predicate gets
    changed and the walk collapses to a handful of terms.
    """
    outfile = tmp_path / "MP.ids.tsv"
    with _server_errors_are_xfail():
        diseasephenotype.write_mp_ids(str(outfile))

    rows = [line.split("\t") for line in outfile.read_text().splitlines() if line.strip()]
    assert len(rows) > 5000, f"expected thousands of MP terms, got {len(rows)}"
    assert all(row[0].startswith("MP:") for row in rows)
    assert {row[1] for row in rows} == {PHENOTYPIC_FEATURE}
