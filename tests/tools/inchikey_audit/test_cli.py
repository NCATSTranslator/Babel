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


@pytest.mark.unit
def test_cli_refuses_the_repos_badxrefs_file(tmp_path):
    """--badxrefs takes the pairs a build applied; the repo's input_data file may list pairs added since, which would
    hide edges the build applied, so the CLI should refuse it before reading the build."""
    from src.createcompendia.chemicals import CHEMICAL_BAD_XREFS

    with pytest.raises(ValueError, match="applied_badxrefs.txt"):
        main(["--build", str(tmp_path), "--badxrefs", CHEMICAL_BAD_XREFS, "--out", str(tmp_path / "out")])


@pytest.mark.unit
def test_cli_creates_the_output_directory_when_the_work_dir_is_elsewhere(tmp_path):
    """With --work-dir outside --out, the CLI should still create a fresh --out rather than fail at the first COPY."""
    members = sorted({c for _, s, o in OFATUMUMAB_CONCORDS for c in (s, o)} | {"RXCUI:712566"})
    build = write_build(
        tmp_path / "build", OFATUMUMAB_CONCORDS, {"CHEBI:28887": ("SmallMolecule", members)}, OFATUMUMAB_LABELS
    )
    structures = write_structure_file(
        tmp_path / "structure.tsv.gz", [("1", DIMETHYL_ETHER_INCHI, DIMETHYL_ETHER_KEY.split(":", 1)[1])]
    )
    out = tmp_path / "fresh" / "out"
    args = ["--build", str(build), "--structure-file", str(structures), "--out", str(out)]

    assert main(args + ["--work-dir", str(tmp_path / "scratch"), "--threads", "1"]) == 0
    assert (out / "components.tsv").exists()
