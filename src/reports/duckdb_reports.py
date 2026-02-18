import json
import os
from collections import defaultdict

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
        WHERE
            edges.conflation = 'None'
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
    cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    # Step 2. Generate a prefix report by Biolink type.
    logger.info("Generating prefix report by Biolink type...")
    curie_prefix_by_type = db.sql("""
        WITH C AS (
            SELECT clique_leader, biolink_type
            FROM cliques
        )
        SELECT
            curie_prefix,
            biolink_type,
            COUNT(e.curie) AS curie_count,
            COUNT(DISTINCT e.curie) AS curie_distinct_count,
            COUNT(DISTINCT e.clique_leader) AS clique_distinct_count
        FROM (
             SELECT clique_leader,
                    split_part(curie, ':', 1) AS curie_prefix,
                    curie
             FROM edges
             WHERE edges.conflation = 'None'
        ) e
        JOIN C USING (clique_leader)
        GROUP BY curie_prefix, biolink_type
    """)
    logger.info("Done generating prefix report by Biolink type, retrieving results...")
    prefix_by_type_report = curie_prefix_by_type.fetchall()
    logger.info("Done retrieving prefix report by Biolink type.")

    # This is split up by filename, so we need to stitch it back together again.
    sorted_rows = sorted(prefix_by_type_report, key=lambda x: (x[0], x[1]))
    by_curie_prefix_results = defaultdict(dict)
    for row in sorted_rows:
        by_curie_prefix_results[row[0]][row[1]] = {
            "curie_count": row[2],
            "curie_distinct_count": row[3],
            "clique_distinct_count": row[4],
        }

    # Step 1. Generate a prefix total report.
    logger.info("Generating prefix totals report...")
    curie_prefix_totals = db.sql("""
                                 SELECT
                                     split_part(curie, ':', 1) AS curie_prefix,
                                     COUNT(curie) AS curie_count,
                                     COUNT(DISTINCT curie) AS curie_distinct_count,
                                     COUNT(DISTINCT clique_leader) AS clique_distinct_count,
                                 FROM
                                     edges
                                 WHERE
                                     edges.conflation = 'None'
                                 GROUP BY
                                     curie_prefix
                                 """)
    logger.info("Done generating prefix totals report, retrieving results...")
    prefix_totals_report = curie_prefix_totals.fetchall()
    prefix_totals_report_by_curie_prefix = defaultdict(dict)
    for row in prefix_totals_report:
        prefix_totals_report_by_curie_prefix[row[0]] = {
            "curie_count": row[1],
            "curie_distinct_count": row[2],
            "clique_distinct_count": row[3],
        }
    logger.info("Done retrieving prefix totals report.")

    # Add total counts back in.
    for curie_prefix in by_curie_prefix_results.keys():
        by_curie_prefix_results[curie_prefix]["_totals"] = prefix_totals_report_by_curie_prefix[curie_prefix]

    with open(curie_report_json, "w") as fout:
        json.dump(by_curie_prefix_results, fout, indent=2, sort_keys=True)


def generate_clique_leaders_report(parquet_root, duckdb_filename, by_clique_report_json, duckdb_config=None):
    """
    Generate a report about all the prefixes within this system, grouped by filename.

    See thoughts at https://github.com/TranslatorSRI/Babel/issues/359

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param by_clique_report_json: The prefix report as JSON.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)
    edges = db.read_parquet(os.path.join(parquet_root, "**/Edge.parquet"), hive_partitioning=True)
    # cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    # Step 1. Generate a by-clique report.
    logger.info("Generating clique report...")
    cliques = db.sql("""
        SELECT
            filename,
            COUNT(DISTINCT clique_leader) AS distinct_clique_count,
            COUNT(DISTINCT curie) AS distinct_curie_count,
            COUNT(curie) AS curie_count
        FROM
            edges
        WHERE
            conflation = 'None'
        GROUP BY
            filename
    """)
    logger.info("Done generating clique report, retrieving results...")
    clique_totals = cliques.fetchall()
    clique_totals_by_curie_prefix = defaultdict(dict)
    for row in clique_totals:
        clique_totals_by_curie_prefix[row[0]] = {
            "distinct_clique_count": row[1],
            "distinct_curie_count": row[2],
            "curie_count": row[3],
        }
    logger.info("Done retrieving results.")

    # Step 2. Generate a by-clique report .
    logger.info("Generating clique report for each CURIE prefix...")
    clique_per_curie = db.sql("""
        SELECT
            filename,
            split_part(clique_leader, ':', 1) AS clique_leader_prefix,
            split_part(curie, ':', 1) AS curie_prefix,
            COUNT(DISTINCT curie) AS distinct_curie_count,
            COUNT(curie) AS curie_count
        FROM
            edges
        WHERE
            conflation = 'None'
        GROUP BY
            filename, clique_leader_prefix, curie_prefix
    """)
    logger.info("Done generating clique report, retrieving results...")
    all_rows = clique_per_curie.fetchall()
    logger.info("Done retrieving results.")

    clique_leaders_by_filename = dict()
    sorted_rows = sorted(all_rows, key=lambda x: (x[0], x[1], x[2]))
    for row in sorted_rows:
        filename = row[0]
        clique_leader_prefix = row[1]
        curie_prefix = row[2]

        if filename not in clique_leaders_by_filename:
            clique_leaders_by_filename[filename] = defaultdict(dict)

        clique_leaders_by_filename[filename][clique_leader_prefix][curie_prefix] = {
            "distinct_curie_count": row[3],
            "curie_count": row[4],
        }

    # Step 3. Add total counts back in.
    for filename, clique_leader_prefix_entries in clique_leaders_by_filename.items():
        if filename in clique_totals_by_curie_prefix:
            clique_leaders_by_filename[filename]["_totals"] = clique_totals_by_curie_prefix[filename]

    # Step 4. Write out by-clique report in JSON.
    with open(by_clique_report_json, "w") as fout:
        json.dump(
            clique_leaders_by_filename,
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
