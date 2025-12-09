import csv
import json
import os
from collections import Counter, defaultdict

from src import util
from src.exporters.duckdb_exporters import setup_duckdb

logger = util.get_logger(__name__)

def check_for_identically_labeled_cliques(parquet_root, duckdb_filename, identically_labeled_cliques_tsv, duckdb_config=None):
    """
    Generate a list of identically labeled cliques.

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param identically_labeled_cliques_csv: The output file listing identically labeled cliques.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)
    cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    results = db.sql("""
        SELECT
            LOWER(preferred_name) AS preferred_name_lc,
            LIST(clique_leader ORDER BY clique_leader ASC) AS clique_leaders,
            COUNT(clique_leader) AS clique_leader_count
        FROM cliques
        WHERE preferred_name <> '' AND preferred_name <> '""'
        GROUP BY preferred_name_lc HAVING clique_leader_count > 1
        ORDER BY clique_leader_count DESC
    """)
    results.write_csv(identically_labeled_cliques_tsv, sep="\t")


def check_for_duplicate_curies(parquet_root, duckdb_filename, duplicate_curies_tsv, duckdb_config=None):
    """
    Generate a list of duplicate CURIEs.

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param duplicate_curies_tsv: The output file listing duplicate CURIEs.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)
    edges = db.read_parquet(os.path.join(parquet_root, "**/Edge.parquet"), hive_partitioning=True)
    cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    # Look for CURIEs that are present in different cliques.
    db.sql("""SELECT
            curie,
            LIST(clique_leader) AS clique_leaders,
            LIST(filename) AS filenames,
            LIST(conflation) AS conflations,
            COUNT(clique_leader) AS clique_leader_count
        FROM
            edges
        GROUP BY curie HAVING clique_leader_count > 1
        ORDER BY clique_leader_count DESC
    """).write_csv(duplicate_curies_tsv, sep="\t")


def check_for_duplicate_clique_leaders(parquet_root, duckdb_filename, duplicate_clique_leaders_tsv, duckdb_config=None):
    """
    Generate a list of duplicate clique leaders.

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param duplicate_clique_leaders_tsv: The output file listing duplicate CURIEs.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)
    cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    # Look for duplicate clique leaders.
    # We would love to include the following columns, but they take up too much memory:
    # - LIST(clique_identifier_count) AS clique_identifier_counts,
    # - LIST(biolink_type) AS biolink_types
    results = db.sql(
        """
        SELECT
            clique_leader,
            LIST(filename) AS filenames,
            COUNT(clique_leader) AS clique_leader_count
        FROM
            cliques
        GROUP BY clique_leader HAVING clique_leader_count > 1
        ORDER BY clique_leader_count DESC
        """
    )
    results.write_csv(duplicate_clique_leaders_tsv, sep="\t")


def generate_curie_report(parquet_root, duckdb_filename, curie_report_json, duckdb_config=None):
    """
    Generate a report about all the prefixes within this system.

    See thoughts at https://github.com/TranslatorSRI/Babel/issues/359

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param curie_report_json: The prefix report as JSON.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)
    edges = db.read_parquet(os.path.join(parquet_root, "**/Edge.parquet"), hive_partitioning=True)

    # Step 1. Generate a by-prefix summary.
    logger.info("Generating prefix report...")
    curie_prefix_summary = db.sql("""
        SELECT
            split_part(curie, ':', 1) AS curie_prefix,
            filename,
            COUNT(curie) AS curie_count,
            COUNT(DISTINCT curie) AS curie_distinct_count,
            COUNT(DISTINCT clique_leader) AS clique_distinct_count,
        FROM
            edges
        GROUP BY
            curie_prefix,
            filename
    """)
    logger.info("Done generating prefix report, retrieving results...")
    all_rows = curie_prefix_summary.fetchall()
    logger.info("Done retrieving results.")

    # This is split up by filename, so we need to stitch it back together again.
    # This MUST be sorted by DuckDB, but sure, let's double-check.
    sorted_rows = sorted(all_rows, key=lambda x: (x[0], x[1]))
    by_curie_prefix_results = defaultdict(dict)
    for row in sorted_rows:
        by_curie_prefix_results[row[0]][row[1]] = {
            "curie_count": row[2],
            "curie_distinct_count": row[3],
            "clique_distinct_count": row[4],
        }

    # Calculate total counts.
    for curie_prefix in by_curie_prefix_results.keys():
        totals = {
            'curie_count': 0,
            'curie_distinct_count': 0,
            'clique_distinct_count': 0
        }

        filenames = by_curie_prefix_results[curie_prefix].keys()
        for filename in filenames:
            totals['curie_count'] += by_curie_prefix_results[curie_prefix][filename]['curie_count']
            totals['curie_distinct_count'] += by_curie_prefix_results[curie_prefix][filename]['curie_distinct_count']
            totals['clique_distinct_count'] += by_curie_prefix_results[curie_prefix][filename]['clique_distinct_count']

        by_curie_prefix_results[curie_prefix]['_totals'] = totals

    with open(curie_report_json, "w") as fout:
        json.dump(by_curie_prefix_results, fout, indent=2, sort_keys=True)


def generate_by_clique_report(parquet_root, duckdb_filename, by_clique_report_json, duckdb_config=None):
    """
    Generate a report about all the prefixes within this system.

    See thoughts at https://github.com/TranslatorSRI/Babel/issues/359

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param by_clique_report_json: The prefix report as JSON.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)
    edges = db.read_parquet(os.path.join(parquet_root, "**/Edge.parquet"), hive_partitioning=True)
    cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    # Step 1. Generate a by-clique summary.
    logger.info("Generating clique report...")
    clique_summary = db.sql("""
        SELECT
            split_part(clique_leader, ':', 1) AS clique_leader_prefix,
            split_part(curie, ':', 1) AS curie_prefix,
            LIST(DISTINCT filename) AS filenames,
            COUNT(DISTINCT clique_leader) AS distinct_clique_leader_count,
            COUNT(DISTINCT curie) AS distinct_clique_count,
            COUNT(curie) AS clique_count
        FROM
            edges
        GROUP BY
            clique_leader_prefix, curie_prefix
    """)
    logger.info("Done generating clique report, retrieving results...")
    all_rows = clique_summary.fetchall()
    logger.info("Done retrieving results.")

    by_clique_results = defaultdict(dict)
    sorted_rows = sorted(all_rows, key=lambda x: (x[0], x[1]))
    for row in sorted_rows:
        by_clique_results[row[0]][row[1]] = {
            "filenames": row[2],
            "distinct_clique_leader_count": row[3],
            "distinct_clique_count": row[4],
            "clique_count": row[5],
        }

    # Step 2. Write out by-clique report in JSON.
    with open(by_clique_report_json, "w") as fout:
        json.dump(by_clique_results,
            fout,
            indent=2,
            sort_keys=True,
        )

def get_label_distribution(duckdb_filename, output_filename):
    db = setup_duckdb(duckdb_filename)

    # Thanks, ChatGPT.
    db.sql("""
       WITH Lengths AS (
            SELECT
                curie,
                label,
                LENGTH(label) AS label_length
            FROM
                Cliques
        ), Examples AS (
            SELECT
                curie,
                label,
                label_length,
                ROW_NUMBER() OVER (PARTITION BY label_length ORDER BY label) AS rn
            FROM
                Lengths
        )
        SELECT
            label_length,
            COUNT(*) AS frequency,
            MAX(CASE WHEN rn = 1 THEN curie ELSE NULL END) AS example_curie,
            MAX(CASE WHEN rn = 1 THEN label ELSE NULL END) AS example_label
        FROM
            Examples
        GROUP BY
            label_length
        ORDER BY
            label_length ASC;
    """).write_csv(output_filename)
