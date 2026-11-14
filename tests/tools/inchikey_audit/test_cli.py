"""Unit test for the babel-inchikey-audit CLI wrapper.

The analysis is tested in tests/model/test_glom_edges.py and tests/model/test_inchikey_audit.py; this covers the
argument handling and the files the CLI writes, over the same miniature ofatumumab build.
"""

import csv

import pytest

from src.tools.inchikey_audit.cli import main
from tests.model.chemical_build_fixture import write_build, write_structure_file
from tests.model.test_inchikey_audit import (
    DIMETHYL_ETHER_INCHI,
    DIMETHYL_ETHER_KEY,
    OFATUMUMAB_CONCORDS,
    OFATUMUMAB_LABELS,
)


def read(path):
    with open(path) as f:
        return list(csv.DictReader(f, delimiter="\t"))


@pytest.mark.unit
def test_cli_writes_components_boundary_refused_and_summary(tmp_path):
    """The CLI should write all four outputs, with the ofatumumab component and its one bad edge in them."""
    members = sorted({c for _, s, o in OFATUMUMAB_CONCORDS for c in (s, o)} | {"RXCUI:712566"})
    build = write_build(
        tmp_path / "build", OFATUMUMAB_CONCORDS, {"CHEBI:28887": ("SmallMolecule", members)}, OFATUMUMAB_LABELS
    )
    structures = write_structure_file(
        tmp_path / "structure.tsv.gz", [("1", DIMETHYL_ETHER_INCHI, DIMETHYL_ETHER_KEY.split(":", 1)[1])]
    )
    out = tmp_path / "out"

    assert main(["--build", str(build), "--structure-file", str(structures), "--out", str(out), "--threads", "1"]) == 0

    components = read(out / "components.tsv")
    assert [(c["clique_leader"], c["tier"], c["verdict"]) for c in components] == [
        ("CHEBI:28887", "A", "likely misattached")
    ]
    boundary = read(out / "boundary_edges.tsv")
    assert [(b["subj"], b["subj_label"], b["obj"], b["obj_label"]) for b in boundary] == [
        ("DrugCentral:4951", "ofatumumab", "PUBCHEM.COMPOUND:8254", "Dimethyl Ether")
    ]
    assert read(out / "refused_edges.tsv") == []
    summary = {(r["kind"], r["category"]): int(r["n"]) for r in read(out / "summary.tsv")}
    assert summary[("glom edge", "applied")] == len(OFATUMUMAB_CONCORDS)
    assert summary[("component tier A", "likely misattached")] == 1
