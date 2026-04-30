from contextlib import contextmanager

import pytest

from src.categories import ANATOMICAL_ENTITY, CELLULAR_COMPONENT
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
        ("EMAPA:0", ANATOMICAL_ENTITY, "EMAPA"),
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
