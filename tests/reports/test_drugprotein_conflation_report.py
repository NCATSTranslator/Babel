"""Unit test for the prospective DrugProtein conflation estimate (issue #706).

The fixture is deliberately tiny: one protein clique and one chemical clique that share no CURIE
(proteins and chemicals are kept apart), bridged by a single DrugChemical relationship concord row
relating the protein's UMLS CURIE to the chemical's UMLS CURIE. The test confirms that the estimate
resolves both endpoints to their clique leaders, keeps the cross-pipeline pair, and merges the two
cliques into exactly one DrugProtein clique -- and that within-pipeline rows are not counted.
"""

import csv
import gzip
import json

import duckdb
import pytest

import src.reports.drugprotein_conflation_report as drugprotein_report


def _write_parquet(con, path, columns, rows):
    con.execute(f"CREATE OR REPLACE TABLE t({', '.join(f'{c} VARCHAR' for c in columns)})")
    if rows:
        placeholders = ", ".join(["(" + ", ".join(["?"] * len(columns)) + ")"] * len(rows))
        flat = [value for row in rows for value in row]
        con.execute(f"INSERT INTO t VALUES {placeholders}", flat)
    con.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")


@pytest.fixture
def parquet_root(tmp_path):
    """Hive-partitioned Parquet tree: a Protein clique and a Drug clique.

    ``filename`` is supplied by the partition directory, so it is absent from the columns.
    """
    con = duckdb.connect()

    protein_dir = tmp_path / "filename=Protein"
    drug_dir = tmp_path / "filename=Drug"
    protein_dir.mkdir()
    drug_dir.mkdir()

    edge_cols = ["curie", "clique_leader", "conflation", "curie_prefix", "clique_leader_prefix", "biolink_type"]
    # Protein clique led by UniProtKB:P01308 (insulin), with a UMLS member that the bridge points at.
    _write_parquet(
        con,
        str(protein_dir / "Edge.parquet"),
        edge_cols,
        [
            ("UniProtKB:P01308", "UniProtKB:P01308", "None", "UniProtKB", "UniProtKB", "biolink:Protein"),
            ("UMLS:C0021641", "UniProtKB:P01308", "None", "UMLS", "UniProtKB", "biolink:Protein"),
        ],
    )
    # Chemical (Drug) clique led by CHEBI:5931, with its own UMLS member.
    _write_parquet(
        con,
        str(drug_dir / "Edge.parquet"),
        edge_cols,
        [
            ("CHEBI:5931", "CHEBI:5931", "None", "CHEBI", "CHEBI", "biolink:Drug"),
            ("UMLS:C0202098", "CHEBI:5931", "None", "UMLS", "CHEBI", "biolink:Drug"),
        ],
    )

    clique_cols = ["clique_leader", "preferred_name", "biolink_type", "clique_identifier_count"]
    _write_parquet(
        con,
        str(protein_dir / "Clique.parquet"),
        clique_cols,
        [("UniProtKB:P01308", "Insulin", "biolink:Protein", "2")],
    )
    _write_parquet(
        con,
        str(drug_dir / "Clique.parquet"),
        clique_cols,
        [("CHEBI:5931", "insulin human", "biolink:Drug", "2")],
    )
    con.close()

    return str(tmp_path) + "/"


@pytest.mark.unit
def test_estimate_drugprotein_conflation(parquet_root, tmp_path):
    # Bridge concord: relate the protein's UMLS CURIE to the chemical's UMLS CURIE. Also include a
    # within-protein row (UMLS:C0021641 -> UniProtKB:P01308) which must NOT be counted as a bridge.
    bridge_path = tmp_path / "RXNORM"
    with open(bridge_path, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["UMLS:C0021641", "has_ingredient", "UMLS:C0202098"])  # protein <-> chemical
        writer.writerow(["UMLS:C0021641", "related_to", "UniProtKB:P01308"])  # protein <-> protein (ignored)

    summary_json = tmp_path / "summary.json"
    edges_tsv_gz = tmp_path / "bridge_edges.tsv.gz"
    top_cliques_csv = tmp_path / "top_cliques.csv"

    drugprotein_report.estimate_drugprotein_conflation(
        parquet_root,
        [("drugchemical/RXNORM", str(bridge_path))],
        None,  # no manual concord in this test
        str(tmp_path / "db.duckdb"),
        str(summary_json),
        str(edges_tsv_gz),
        str(top_cliques_csv),
    )

    summary = json.loads(summary_json.read_text())
    assert summary["distinct_protein_cliques_bridged"] == 1
    assert summary["distinct_chemical_cliques_bridged"] == 1
    assert summary["distinct_bridge_edges"] == 1
    assert summary["resulting_merged_cliques"] == 1
    # One merged clique of size 2 (the protein leader + the chemical leader).
    assert summary["merged_clique_size_histogram"] == {"2": 1}
    assert summary["by_bridge_source"]["drugchemical/RXNORM"]["edges"] == 1

    # The edge list carries both leaders with their labels.
    with gzip.open(edges_tsv_gz, "rt") as f:
        edge_rows = list(csv.DictReader(f, delimiter="\t"))
    assert len(edge_rows) == 1
    assert edge_rows[0]["protein_leader"] == "UniProtKB:P01308"
    assert edge_rows[0]["protein_label"] == "Insulin"
    assert edge_rows[0]["chemical_leader"] == "CHEBI:5931"
    assert edge_rows[0]["chemical_label"] == "insulin human"

    # The top-cliques sanity file lists the one merged clique with both members.
    top_rows = list(csv.DictReader(open(top_cliques_csv)))
    assert len(top_rows) == 1
    assert top_rows[0]["clique_size"] == "2"
    assert top_rows[0]["protein_count"] == "1"
    assert top_rows[0]["chemical_count"] == "1"
    assert "UniProtKB:P01308=Insulin" in top_rows[0]["members"]
    assert "CHEBI:5931=insulin human" in top_rows[0]["members"]
