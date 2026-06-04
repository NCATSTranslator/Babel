import csv
import os

import jsonlines
import pytest

from src.reports.protein_chemical_overlap import (
    concord_source_label,
    generate_protein_chemical_overlap_report,
)


def _clique(identifiers, biolink_type, preferred_name):
    """Build a compendium clique line in the schema write_compendium() produces."""
    return {
        "type": biolink_type,
        "ic": 100,
        "identifiers": [{"i": curie, "l": label, "d": [], "t": []} for curie, label in identifiers],
        "preferred_name": preferred_name,
        "taxa": [],
    }


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with jsonlines.open(path, "w") as writer:
        for row in rows:
            writer.write(row)


def _read_tsv(path):
    with open(path) as inf:
        return list(csv.DictReader(inf, delimiter="\t"))


def test_concord_source_label():
    assert concord_source_label("/x/intermediate/chemicals/concords/DrugCentral") == "chemicals/DrugCentral"
    assert concord_source_label("/x/intermediate/protein/concords/UNICHEM/UNICHEM_1_7") == "protein/UNICHEM/UNICHEM_1_7"
    assert concord_source_label("/some/other/file") == "file"


@pytest.mark.unit
def test_generate_protein_chemical_overlap_report(tmp_path):
    # --- Chemical side ---------------------------------------------------------------------------
    # Clique A: etanercept, no InChIKey, and it shares the CURIE UMLS:C0717758 with a protein clique
    #           (a duplicate-across-cliques case, #276/#513).
    # Clique B: "pepsin" but actually a structurally-defined small molecule (has an InChIKey) -- the
    #           kind of crossing that is usually a *bug* (#440).
    chemical_compendium = str(tmp_path / "compendia" / "ChemicalEntity.txt")
    _write_jsonl(
        chemical_compendium,
        [
            _clique(
                [("CHEBI:4875", "etanercept"), ("DRUGBANK:DB00005", "Etanercept"), ("UMLS:C0717758", "etanercept")],
                "biolink:ChemicalEntity",
                "Etanercept",
            ),
            _clique(
                [("CHEBI:24536", "Pepsin"), ("INCHIKEY:JLYXXMFPNIAWKQ-UHFFFAOYSA-N", "")],
                "biolink:SmallMolecule",
                "Pepsin",
            ),
        ],
    )

    # --- Protein side ----------------------------------------------------------------------------
    # Clique P: pepsin A-5; also (deliberately) carries UMLS:C0717758 so it duplicates with clique A.
    # Clique Q: belimumab target.
    protein_compendium = str(tmp_path / "compendia" / "Protein.txt")
    _write_jsonl(
        protein_compendium,
        [
            _clique(
                [("UniProtKB:P0DJD9", "Pepsin A-5"), ("UMLS:C0717758", "etanercept")],
                "biolink:Protein",
                "Pepsin A-5",
            ),
            _clique([("UniProtKB:Q9Y275", "TN13B")], "biolink:Protein", "TN13B"),
        ],
    )

    # --- Concords --------------------------------------------------------------------------------
    concord = str(tmp_path / "intermediate" / "chemicals" / "concords" / "DrugCentral")
    os.makedirs(os.path.dirname(concord), exist_ok=True)
    with open(concord, "w") as outf:
        # Crossing edge 1: structurally-defined chemical -> protein (chem_has_inchikey True).
        outf.write("CHEBI:24536\txref\tUniProtKB:P0DJD9\n")
        # Crossing edge 2: chemical (via DrugBank member of clique A) -> protein (no InChIKey).
        outf.write("DRUGBANK:DB00005\trelated_to\tUniProtKB:Q9Y275\n")
        # Non-crossing: chem -> chem (same side), must be ignored.
        outf.write("CHEBI:4875\txref\tDRUGBANK:DB00005\n")
        # Endpoint not in any compendium, must be ignored.
        outf.write("CHEBI:4875\txref\tFOOBAR:1\n")
        # References UMLS:C0717758 (a member of both clique A and clique P) so it enters the concord
        # CURIE set and is detected as a duplicate; the other endpoint is unknown so this is not a
        # boundary crossing on its own.
        outf.write("UMLS:C0717758\txref\tFOOBAR:2\n")
        # Malformed line, must be skipped.
        outf.write("CHEBI:4875\tonlytwo\n")

    # --- GeneProtein conflation: P0DJD9 reaches a gene; Q9Y275 does not. -------------------------
    geneprotein = str(tmp_path / "conflation" / "GeneProtein.txt")
    _write_jsonl(geneprotein, [["NCBIGene:5222", "UniProtKB:P0DJD9"], ["UniProtKB:Q9Y275"]])

    bridges = str(tmp_path / "out" / "bridges.tsv")
    pairs = str(tmp_path / "out" / "pairs.tsv")
    duplicates = str(tmp_path / "out" / "duplicates.tsv")
    summary = str(tmp_path / "out" / "summary.tsv")

    counts = generate_protein_chemical_overlap_report(
        chemical_compendia=[chemical_compendium],
        protein_compendia=[protein_compendium],
        concord_files=[concord],
        bridges_tsv=bridges,
        candidate_pairs_tsv=pairs,
        duplicate_curies_tsv=duplicates,
        summary_tsv=summary,
        geneprotein_conflation=geneprotein,
    )

    assert counts["bridge_edges"] == 2
    assert counts["candidate_pairs"] == 2
    assert counts["duplicate_curies"] == 1

    # --- Bridges -----------------------------------------------------------------------------
    bridge_rows = _read_tsv(bridges)
    assert len(bridge_rows) == 2
    by_chem = {row["chem_leader"]: row for row in bridge_rows}

    # CHEBI:24536 crossing: chem has an InChIKey, protein reaches a gene.
    assert by_chem["CHEBI:24536"]["chem_has_inchikey"] == "true"
    assert by_chem["CHEBI:24536"]["prot_reaches_gene"] == "true"
    assert by_chem["CHEBI:24536"]["prot_leader"] == "UniProtKB:P0DJD9"
    assert by_chem["CHEBI:24536"]["source_concord"] == "chemicals/DrugCentral"

    # CHEBI:4875 crossing (via its DrugBank member): no InChIKey, protein does not reach a gene.
    assert by_chem["CHEBI:4875"]["chem_has_inchikey"] == "false"
    assert by_chem["CHEBI:4875"]["prot_reaches_gene"] == "false"
    assert by_chem["CHEBI:4875"]["chem_curie"] == "DRUGBANK:DB00005"
    assert by_chem["CHEBI:4875"]["prot_leader"] == "UniProtKB:Q9Y275"

    # --- Candidate pairs ---------------------------------------------------------------------
    pair_rows = _read_tsv(pairs)
    pair_keys = {(row["chem_leader"], row["prot_leader"]) for row in pair_rows}
    assert pair_keys == {("CHEBI:24536", "UniProtKB:P0DJD9"), ("CHEBI:4875", "UniProtKB:Q9Y275")}

    # --- Duplicate CURIEs (#276/#513) --------------------------------------------------------
    dup_rows = _read_tsv(duplicates)
    assert len(dup_rows) == 1
    assert dup_rows[0]["curie"] == "UMLS:C0717758"
    assert dup_rows[0]["chem_leader"] == "CHEBI:4875"
    assert dup_rows[0]["prot_leader"] == "UniProtKB:P0DJD9"

    # --- Summary -----------------------------------------------------------------------------
    summary_rows = _read_tsv(summary)
    by_source = {row["source_concord"]: row for row in summary_rows}
    assert by_source["chemicals/DrugCentral"]["bridge_edges"] == "2"
    assert by_source["chemicals/DrugCentral"]["edges_with_chem_inchikey"] == "1"
    assert by_source["chemicals/DrugCentral"]["edges_without_chem_inchikey"] == "1"
    assert by_source["TOTAL"]["distinct_candidate_pairs"] == "2"


@pytest.mark.unit
def test_report_without_geneprotein_conflation(tmp_path):
    """prot_reaches_gene should simply be false everywhere when no conflation file is given."""
    chemical_compendium = str(tmp_path / "compendia" / "ChemicalEntity.txt")
    _write_jsonl(
        chemical_compendium,
        [_clique([("CHEBI:24536", "Pepsin")], "biolink:SmallMolecule", "Pepsin")],
    )
    protein_compendium = str(tmp_path / "compendia" / "Protein.txt")
    _write_jsonl(
        protein_compendium,
        [_clique([("UniProtKB:P0DJD9", "Pepsin A-5")], "biolink:Protein", "Pepsin A-5")],
    )
    concord = str(tmp_path / "intermediate" / "protein" / "concords" / "UMLS")
    os.makedirs(os.path.dirname(concord), exist_ok=True)
    with open(concord, "w") as outf:
        outf.write("CHEBI:24536\txref\tUniProtKB:P0DJD9\n")

    bridges = str(tmp_path / "out" / "bridges.tsv")
    counts = generate_protein_chemical_overlap_report(
        chemical_compendia=[chemical_compendium],
        protein_compendia=[protein_compendium],
        concord_files=[concord],
        bridges_tsv=bridges,
        candidate_pairs_tsv=str(tmp_path / "out" / "pairs.tsv"),
        duplicate_curies_tsv=str(tmp_path / "out" / "duplicates.tsv"),
        summary_tsv=str(tmp_path / "out" / "summary.tsv"),
        geneprotein_conflation=None,
    )
    assert counts["bridge_edges"] == 1
    assert _read_tsv(bridges)[0]["prot_reaches_gene"] == "false"
