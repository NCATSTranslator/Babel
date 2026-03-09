import os

import pytest

from src.createcompendia.geneprotein import build_compendium


@pytest.mark.unit
def test_gp(tmp_path):
    here = os.path.abspath(os.path.dirname(__file__))
    gene_compendium = os.path.join(here, "data", "gptest_Gene.txt")
    protein_compendium = os.path.join(here, "data", "gptest_Protein.txt")
    geneprotein_concord = os.path.join(here, "data", "gp_UniProtNCBI.txt")
    outfile = tmp_path / "gp_output.txt"
    build_compendium(gene_compendium, protein_compendium, geneprotein_concord, str(outfile))
    assert outfile.stat().st_size > 0
