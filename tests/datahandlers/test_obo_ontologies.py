from contextlib import contextmanager

import pytest

from src.categories import ANATOMICAL_ENTITY, CELLULAR_COMPONENT
from src.createcompendia import anatomy
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


def test_write_emapa_ids_collects_partonomy(tmp_path):
    """EMAPA is a part_of partonomy, so write_obo_ids() (a subClassOf walk) misses it.

    write_emapa_ids() must instead collect the thousands of anatomy terms reachable by
    part_of from the EMAPA root, all typed biolink:AnatomicalEntity. The lower bound
    guards against a regression to the subClassOf-only behaviour, which found 2 terms.
    """
    outfile = tmp_path / "EMAPA.ids.tsv"
    with _server_errors_are_xfail():
        anatomy.write_emapa_ids(str(outfile))

    rows = [line.split("\t") for line in outfile.read_text().splitlines() if line.strip()]
    assert len(rows) > 1000, f"expected thousands of EMAPA terms, got {len(rows)}"
    assert all(row[0].startswith("EMAPA:") for row in rows)
    assert {row[1] for row in rows} == {ANATOMICAL_ENTITY}
