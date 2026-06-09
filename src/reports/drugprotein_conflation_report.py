"""
Estimate what a prospective DrugProtein conflation would look like (issue #706).

Babel builds proteins and chemicals in two separate pipelines and deliberately keeps the
identifiers that could be either (UMLS, MESH) apart between them. Issue #706 asks whether we
should *optionally* re-join them through the conflation system. To decide, we need to quantify
the join: how many protein cliques would bridge to chemical/drug cliques, via which bridge
sources, the size distribution of the resulting merged cliques, and concrete examples.

This module computes that estimate without changing any compendium. It reuses the bridge edges
that already exist on disk -- the DrugChemical relationship concords
(``intermediate/drugchemical/concords/{RXNORM,UMLS,PUBCHEM_RXNORM}``) and the manual DrugChemical
concord -- which are the only artifacts that relate a protein-pipeline concept and a
chemical-pipeline concept in the same edge (each pipeline only ``glom()``s within itself, so no
compendium records a protein-clique -> chemical-clique edge). Both endpoints of every bridge edge
are resolved to their clique leader via the DuckDB ``Edge.parquet`` export; the pairs where one
endpoint landed in a protein clique and the other in a chemical/drug clique are exactly the
DrugChemical conflation *discards* today, and exactly the DrugProtein links we want to count. We
then merge those leader pairs with the same ``glom()`` union-find the real conflations use.

The bridge prefixes we restrict the Edge scan to are the only prefixes that can appear in the
bridge concords (RxCUI/UMLS relationships and the manual cross-links); restricting up front keeps
the Edge scan small, following the memory discipline in ``duckdb_reports.py``.
"""

import csv
import gzip
import json
import os
from collections import Counter, defaultdict

from src import util
from src.babel_utils import glom
from src.exporters.duckdb_exporters import log_duckdb_settings_on_error, setup_duckdb

logger = util.get_logger(__name__)

# Prefixes that can appear in the DrugChemical bridge concords (RxCUI/UMLS relationships and the
# manual cross-links). The Edge scan is restricted to these so it stays small.
DEFAULT_BRIDGE_PREFIXES = (
    "UMLS",
    "MESH",
    "UniProtKB",
    "PR",
    "CHEBI",
    "DRUGBANK",
    "CHEMBL.COMPOUND",
    "GTOPDB",
    "DrugCentral",
    "UNII",
    "PUBCHEM.COMPOUND",
    "RXCUI",
)

# The compendium that the protein pipeline emits. (Polypeptide.txt is a *chemical*-pipeline output,
# so it is intentionally not here.)
DEFAULT_PROTEIN_FILENAMES = ("Protein",)

# The compendia the chemical pipeline emits (config["chemical_outputs"], minus the .txt extension).
DEFAULT_CHEMICAL_FILENAMES = (
    "MolecularMixture",
    "SmallMolecule",
    "Polypeptide",
    "ComplexMolecularMixture",
    "ChemicalEntity",
    "ChemicalMixture",
    "Drug",
)


def _create_node_clique_table(db, parquet_root, bridge_prefixes):
    """Materialize a CURIE -> (clique_leader, biolink_type, filename) table from Edge.parquet,
    restricted to the bridge-relevant prefixes so the scan stays small. ``filename`` is the
    hive-partition value (the compendium basename, e.g. ``Protein`` or ``Drug``)."""
    edge_glob = os.path.join(parquet_root, "**/Edge.parquet")
    prefix_list = ", ".join(f"'{p}'" for p in bridge_prefixes)
    with log_duckdb_settings_on_error(db, "drugprotein: build node_clique table from Edge.parquet"):
        db.execute(f"""
            CREATE OR REPLACE TEMP TABLE node_clique AS
            SELECT curie, clique_leader, biolink_type, filename
            FROM read_parquet('{edge_glob}', hive_partitioning=true)
            WHERE conflation = 'None'
              AND curie_prefix IN ({prefix_list})
        """)


def _create_bridges_table(db, bridge_concords, manual_concord):
    """Load the bridge concords into a ``bridges(source, subj, obj)`` table.

    :param bridge_concords: list of (source_label, path) for 3-column headerless TSV concords
        (subj, pred, obj), e.g. the DrugChemical RXNORM/UMLS/PUBCHEM_RXNORM relationship files.
    :param manual_concord: path to the manual DrugChemical concord (TSV *with* a header containing
        subject/predicate/object columns), or None.
    """
    db.execute("CREATE OR REPLACE TEMP TABLE bridges (source VARCHAR, subj VARCHAR, obj VARCHAR)")
    for source_label, path in bridge_concords:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            logger.warning(f"Bridge concord {source_label} ({path}) is missing or empty; skipping.")
            continue
        logger.info(f"Loading bridge concord {source_label} from {path}")
        db.execute(
            "INSERT INTO bridges SELECT ? AS source, subj, obj FROM "
            "read_csv(?, delim='\t', header=false, "
            "columns={'subj': 'VARCHAR', 'pred': 'VARCHAR', 'obj': 'VARCHAR'})",
            [source_label, path],
        )

    if manual_concord and os.path.exists(manual_concord) and os.path.getsize(manual_concord) > 0:
        logger.info(f"Loading manual concord from {manual_concord}")
        # The manual concord is read with the csv module rather than DuckDB so we validate the
        # named subject/object columns explicitly (same contract as drugchemical.build_conflation).
        rows = []
        with open(manual_concord) as manualf:
            reader = csv.DictReader(manualf, dialect=csv.excel_tab)
            for row in reader:
                if "subject" not in row or "object" not in row:
                    raise RuntimeError(f"Missing subject or object fields in {manual_concord}: {row}")
                subject = row["subject"].strip()
                obj = row["object"].strip()
                if subject and obj:
                    rows.append(("manual", subject, obj))
        db.executemany("INSERT INTO bridges VALUES (?, ?, ?)", rows)


def _fetch_cross_pipeline_pairs(db, protein_filenames, chemical_filenames):
    """Join both endpoints of every bridge edge to their clique, keep the edges that cross the
    protein/chemical boundary, and return distinct (protein_leader, chemical_leader, chemical_file,
    source) rows. A CURIE that landed in more than one clique simply contributes more than one row;
    SELECT DISTINCT collapses identical pairs."""
    protein_list = ", ".join(f"'{f}'" for f in protein_filenames)
    chemical_list = ", ".join(f"'{f}'" for f in chemical_filenames)
    with log_duckdb_settings_on_error(db, "drugprotein: join bridges to cliques and keep cross-pipeline pairs"):
        return db.execute(f"""
            WITH joined AS (
                SELECT b.source,
                       s.clique_leader AS subj_leader, s.filename AS subj_file,
                       o.clique_leader AS obj_leader, o.filename AS obj_file
                FROM bridges b
                JOIN node_clique s ON s.curie = b.subj
                JOIN node_clique o ON o.curie = b.obj
            )
            SELECT DISTINCT
                CASE WHEN subj_file IN ({protein_list}) THEN subj_leader ELSE obj_leader END AS protein_leader,
                CASE WHEN subj_file IN ({protein_list}) THEN obj_leader ELSE subj_leader END AS chemical_leader,
                CASE WHEN subj_file IN ({protein_list}) THEN obj_file ELSE subj_file END AS chemical_file,
                source
            FROM joined
            WHERE (subj_file IN ({protein_list}) AND obj_file IN ({chemical_list}))
               OR (obj_file IN ({protein_list}) AND subj_file IN ({chemical_list}))
        """).fetchall()


def _fetch_labels(db, parquet_root, leaders):
    """Return a clique_leader -> preferred_name dict for the given set of leaders, read from
    Clique.parquet. Returns an empty mapping for leaders without a label."""
    if not leaders:
        return {}
    clique_glob = os.path.join(parquet_root, "**/Clique.parquet")
    db.execute("CREATE OR REPLACE TEMP TABLE wanted_leaders (clique_leader VARCHAR)")
    db.executemany("INSERT INTO wanted_leaders VALUES (?)", [(curie,) for curie in leaders])
    with log_duckdb_settings_on_error(db, "drugprotein: fetch preferred names for involved leaders"):
        rows = db.execute(f"""
            SELECT c.clique_leader, ANY_VALUE(c.preferred_name)
            FROM read_parquet('{clique_glob}', hive_partitioning=true) c
            JOIN wanted_leaders w USING (clique_leader)
            GROUP BY c.clique_leader
        """).fetchall()
    return {row[0]: (row[1] or "") for row in rows}


def estimate_drugprotein_conflation(
    parquet_root,
    bridge_concords,
    manual_concord,
    duckdb_filename,
    out_summary_json,
    out_edges_tsv_gz,
    out_top_cliques_csv,
    protein_filenames=DEFAULT_PROTEIN_FILENAMES,
    chemical_filenames=DEFAULT_CHEMICAL_FILENAMES,
    bridge_prefixes=DEFAULT_BRIDGE_PREFIXES,
    top_n=200,
    duckdb_config=None,
):
    """Estimate a prospective DrugProtein conflation and write three reports.

    :param parquet_root: root of the DuckDB Parquet export (contains ``filename=*/Edge.parquet``
        and ``filename=*/Clique.parquet``).
    :param bridge_concords: list of (source_label, path) for the headerless 3-column DrugChemical
        relationship concords.
    :param manual_concord: path to the manual DrugChemical concord (header row), or None.
    :param duckdb_filename: a temporary DuckDB file to use.
    :param out_summary_json: JSON summary (counts, per-source breakdown, merged-clique size
        histogram).
    :param out_edges_tsv_gz: gzipped TSV of every cross-pipeline (protein_leader, chemical_leader,
        source) pair with labels -- the reviewable artifact for issue #706.
    :param out_top_cliques_csv: CSV of the largest prospective merged cliques with member CURIEs
        and labels, as a sanity check.
    :param top_n: how many of the largest merged cliques to write to out_top_cliques_csv.
    """
    db = setup_duckdb(duckdb_filename, duckdb_config)

    _create_node_clique_table(db, parquet_root, bridge_prefixes)
    _create_bridges_table(db, bridge_concords, manual_concord)
    pairs = _fetch_cross_pipeline_pairs(db, protein_filenames, chemical_filenames)
    logger.info(f"Found {len(pairs)} distinct cross-pipeline (protein, chemical) bridge rows.")

    # Collect distinct protein leaders, chemical leaders, and the pair edges for glom().
    protein_leaders = set()
    chemical_leaders = set()
    pair_edges = set()
    by_source = defaultdict(lambda: {"edges": 0, "protein_leaders": set(), "chemical_leaders": set()})
    chemical_file_for_leader = {}
    for protein_leader, chemical_leader, chemical_file, source in pairs:
        protein_leaders.add(protein_leader)
        chemical_leaders.add(chemical_leader)
        pair_edges.add((protein_leader, chemical_leader))
        chemical_file_for_leader[chemical_leader] = chemical_file
        s = by_source[source]
        s["edges"] += 1
        s["protein_leaders"].add(protein_leader)
        s["chemical_leaders"].add(chemical_leader)

    # Fetch labels for everything involved.
    labels = _fetch_labels(db, parquet_root, protein_leaders | chemical_leaders)
    db.close()

    # Write the full bridge-edge list (the reviewable artifact).
    with gzip.open(out_edges_tsv_gz, "wt", newline="") as edgef:
        writer = csv.writer(edgef, delimiter="\t")
        writer.writerow(
            ["protein_leader", "protein_label", "chemical_leader", "chemical_label", "chemical_file", "source"]
        )
        for protein_leader, chemical_leader, chemical_file, source in sorted(pairs):
            writer.writerow(
                [
                    protein_leader,
                    labels.get(protein_leader, ""),
                    chemical_leader,
                    labels.get(chemical_leader, ""),
                    chemical_file,
                    source,
                ]
            )

    # Merge the leader pairs into prospective DrugProtein cliques using the same union-find the real
    # conflations use. glom() mutates the dict it is handed; each pair is a 2-element set.
    gloms = {}
    glom(gloms, [set(edge) for edge in pair_edges])
    merged_cliques = {frozenset(members) for members in gloms.values()}

    # Size distribution and the protein/chemical makeup of each merged clique.
    size_histogram = Counter(len(members) for members in merged_cliques)
    merged_with_multiple_proteins = 0
    for members in merged_cliques:
        if len(members & protein_leaders) > 1:
            merged_with_multiple_proteins += 1

    summary = {
        "issue": "https://github.com/NCATSTranslator/Babel/issues/706",
        "description": "Estimate of a prospective DrugProtein conflation built from the existing "
        "DrugChemical bridge concords. Each merged clique unifies one or more protein cliques with "
        "one or more chemical/drug cliques.",
        "distinct_protein_cliques_bridged": len(protein_leaders),
        "distinct_chemical_cliques_bridged": len(chemical_leaders),
        "distinct_bridge_edges": len(pair_edges),
        "resulting_merged_cliques": len(merged_cliques),
        "merged_cliques_with_multiple_proteins": merged_with_multiple_proteins,
        "merged_clique_size_histogram": {str(size): count for size, count in sorted(size_histogram.items())},
        "by_bridge_source": {
            source: {
                "edges": stats["edges"],
                "distinct_protein_cliques": len(stats["protein_leaders"]),
                "distinct_chemical_cliques": len(stats["chemical_leaders"]),
            }
            for source, stats in sorted(by_source.items())
        },
    }
    with open(out_summary_json, "w") as summaryf:
        json.dump(summary, summaryf, indent=2, sort_keys=True)

    # Top-N largest merged cliques with labels, as a sanity check (insulin et al.).
    sorted_cliques = sorted(merged_cliques, key=len, reverse=True)[:top_n]
    with open(out_top_cliques_csv, "w", newline="") as topf:
        writer = csv.writer(topf)
        writer.writerow(["clique_size", "protein_count", "chemical_count", "members"])
        for members in sorted_cliques:
            proteins_here = members & protein_leaders
            chemicals_here = members - protein_leaders
            member_str = "; ".join(f"{curie}={labels.get(curie, '')}" for curie in sorted(members))
            writer.writerow([len(members), len(proteins_here), len(chemicals_here), member_str])

    logger.info(
        f"DrugProtein estimate: {len(protein_leaders)} protein cliques and {len(chemical_leaders)} "
        f"chemical cliques bridged into {len(merged_cliques)} merged cliques."
    )
