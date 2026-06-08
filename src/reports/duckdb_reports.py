import json
import os
from collections import defaultdict

from src import util
from src.exporters.duckdb_exporters import log_duckdb_settings_on_error, setup_duckdb

logger = util.get_logger(__name__)


def check_for_identically_labeled_cliques(
    parquet_root, duckdb_filename, identically_labeled_cliques_tsv, duckdb_config=None
):
    """
    Generate a list of identically labeled cliques.

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param identically_labeled_cliques_csv: The output file listing identically labeled cliques.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)
    cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    # Pass 1: identify names shared by more than one clique using only a COUNT.
    # A pure COUNT(*) GROUP BY can spill to disk, whereas a LIST() aggregate cannot:
    # DuckDB would build one list per group (including the single-clique groups that the
    # HAVING clause later discards), holding all of them in RAM and OOMing on the full set.
    with log_duckdb_settings_on_error(
        db, "check_for_identically_labeled_cliques pass 1 (GROUP BY LOWER(preferred_name))"
    ):
        db.execute("""
            CREATE OR REPLACE TEMP TABLE dup_names AS
            SELECT LOWER(preferred_name) AS preferred_name_lc, COUNT(*) AS clique_leader_count
            FROM cliques
            WHERE preferred_name <> '' AND preferred_name <> '""'
            GROUP BY preferred_name_lc HAVING clique_leader_count > 1
        """)

    # Pass 2: write one row per (duplicate name, clique_leader) pair, sorted so that the cliques
    # sharing a name are adjacent. The previous version aggregated the leaders into an in-SQL
    # ``LIST(... ORDER BY ...)``, which is not spillable: DuckDB buffers every group's sorted state
    # in RAM at once, and because many cliques can share a name (one name in a recent build was
    # shared by 92k cliques) it OOMed even on a full largemem node. A plain ``ORDER BY`` spills to
    # the temp directory, so peak RAM stays bounded; the flat output is just as easy to read.
    with log_duckdb_settings_on_error(db, "check_for_identically_labeled_cliques pass 2 (sorted duplicate pairs)"):
        db.sql("""
            SELECT d.preferred_name_lc, d.clique_leader_count, c.clique_leader
            FROM cliques c
            JOIN dup_names d ON LOWER(c.preferred_name) = d.preferred_name_lc
            WHERE c.preferred_name <> '' AND c.preferred_name <> '""'
            ORDER BY d.clique_leader_count DESC, d.preferred_name_lc ASC, c.clique_leader ASC
        """).write_csv(identically_labeled_cliques_tsv, sep="\t", header=True)

    cliques.close()


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

    # Pass 1: identify CURIEs present in more than one clique using only a COUNT.
    # A pure COUNT(*) GROUP BY can spill to disk; the LIST() aggregates below cannot, so
    # collecting them up front over every CURIE (most of which are not duplicated) would OOM.
    with log_duckdb_settings_on_error(db, "check_for_duplicate_curies pass 1 (GROUP BY curie over all edges)"):
        db.execute("""
            CREATE OR REPLACE TEMP TABLE dup_curies AS
            SELECT curie, COUNT(*) AS clique_leader_count
            FROM edges
            WHERE conflation = 'None'
            GROUP BY curie HAVING clique_leader_count > 1
        """)

    # Pass 2: collect LIST() only for the confirmed duplicate CURIEs (a small join target).
    with log_duckdb_settings_on_error(db, "check_for_duplicate_curies pass 2 (LIST over duplicate CURIEs)"):
        db.sql("""
            SELECT e.curie,
                LIST(e.clique_leader ORDER BY e.clique_leader) AS clique_leaders,
                LIST(e.filename ORDER BY e.clique_leader) AS filenames,
                LIST(e.conflation ORDER BY e.clique_leader) AS conflations,
                d.clique_leader_count
            FROM edges e
            JOIN dup_curies d USING (curie)
            WHERE e.conflation = 'None'
            GROUP BY e.curie, d.clique_leader_count
            ORDER BY d.clique_leader_count DESC
        """).write_csv(duplicate_curies_tsv, sep="\t")

    edges.close()


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

    # Pass 1: identify duplicate clique leaders using only a COUNT.
    # A pure COUNT(*) GROUP BY can spill to disk, but the LIST() aggregates below cannot, so
    # collecting them over every clique leader (almost all unique) would OOM on the full set.
    with log_duckdb_settings_on_error(db, "check_for_duplicate_clique_leaders pass 1 (GROUP BY clique_leader)"):
        db.execute("""
            CREATE OR REPLACE TEMP TABLE dup_leaders AS
            SELECT clique_leader, COUNT(*) AS clique_leader_count
            FROM cliques
            GROUP BY clique_leader HAVING clique_leader_count > 1
        """)

    # Pass 2: collect LIST() only for the confirmed duplicates (a small join target).
    # Because the LIST() materialization is now trivial we can also afford to keep
    # biolink_type and clique_identifier_count, which were previously dropped to save memory.
    with log_duckdb_settings_on_error(db, "check_for_duplicate_clique_leaders pass 2 (LIST over duplicate leaders)"):
        db.sql("""
            SELECT d.clique_leader,
                LIST(c.filename ORDER BY c.filename) AS filenames,
                LIST(c.biolink_type ORDER BY c.filename) AS biolink_types,
                LIST(c.clique_identifier_count ORDER BY c.filename) AS clique_identifier_counts,
                d.clique_leader_count
            FROM cliques c
            JOIN dup_leaders d USING (clique_leader)
            GROUP BY d.clique_leader, d.clique_leader_count
            ORDER BY d.clique_leader_count DESC
        """).write_csv(duplicate_clique_leaders_tsv, sep="\t")

    cliques.close()


def generate_curie_report(parquet_root, duckdb_filename, curie_report_json, duckdb_config=None):
    """
    Generate a report about all the prefixes within this system.

    See thoughts at https://github.com/NCATSTranslator/Babel/issues/359

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param curie_report_json: The prefix report as JSON.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)
    edges = db.read_parquet(os.path.join(parquet_root, "**/Edge.parquet"), hive_partitioning=True)
    cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    # Step 2. Generate a prefix report by Biolink type.
    #
    # A grouped COUNT(DISTINCT) over the full Edge set is not spillable (DuckDB keeps a distinct
    # hash set per group in RAM) and OOMed even on a full largemem node. Instead we pre-reduce to
    # the distinct grain with a plain ``SELECT DISTINCT`` -- a normal hash aggregation that spills
    # to the temp directory -- and then COUNT(*) over that. The distinct-curie and
    # distinct-clique_leader counts use different keys, so each gets its own spillable subquery and
    # they are joined back on (curie_prefix, biolink_type), which has only a few thousand rows.
    logger.info("Generating prefix report by Biolink type...")
    with log_duckdb_settings_on_error(
        db, "generate_curie_report: prefix report by Biolink type (spillable distinct counts)"
    ):
        curie_prefix_by_type = db.sql("""
            WITH edge_by_type AS (
                SELECT e.curie_prefix, c.biolink_type, e.curie, e.clique_leader
                FROM (SELECT clique_leader, curie_prefix, curie FROM edges WHERE conflation = 'None') e
                JOIN (SELECT clique_leader, biolink_type FROM cliques) c USING (clique_leader)
            ),
            totals AS (
                SELECT curie_prefix, biolink_type, COUNT(*) AS curie_count
                FROM edge_by_type GROUP BY curie_prefix, biolink_type
            ),
            distinct_curies AS (
                SELECT curie_prefix, biolink_type, COUNT(*) AS curie_distinct_count
                FROM (SELECT DISTINCT curie_prefix, biolink_type, curie FROM edge_by_type)
                GROUP BY curie_prefix, biolink_type
            ),
            distinct_cliques AS (
                SELECT curie_prefix, biolink_type, COUNT(*) AS clique_distinct_count
                FROM (SELECT DISTINCT curie_prefix, biolink_type, clique_leader FROM edge_by_type)
                GROUP BY curie_prefix, biolink_type
            )
            SELECT t.curie_prefix, t.biolink_type, t.curie_count,
                   dc.curie_distinct_count, dl.clique_distinct_count
            FROM totals t
            JOIN distinct_curies dc USING (curie_prefix, biolink_type)
            JOIN distinct_cliques dl USING (curie_prefix, biolink_type)
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

    # Step 1. Generate a prefix total report. Same spillable distinct-then-count pattern as Step 2,
    # grouped by curie prefix alone.
    logger.info("Generating prefix totals report...")
    with log_duckdb_settings_on_error(db, "generate_curie_report: prefix totals (spillable distinct counts)"):
        curie_prefix_totals = db.sql("""
            WITH base AS (
                SELECT split_part(curie, ':', 1) AS curie_prefix, curie, clique_leader
                FROM edges WHERE conflation = 'None'
            ),
            totals AS (
                SELECT curie_prefix, COUNT(*) AS curie_count FROM base GROUP BY curie_prefix
            ),
            distinct_curies AS (
                SELECT curie_prefix, COUNT(*) AS curie_distinct_count
                FROM (SELECT DISTINCT curie_prefix, curie FROM base) GROUP BY curie_prefix
            ),
            distinct_cliques AS (
                SELECT curie_prefix, COUNT(*) AS clique_distinct_count
                FROM (SELECT DISTINCT curie_prefix, clique_leader FROM base) GROUP BY curie_prefix
            )
            SELECT t.curie_prefix, t.curie_count, dc.curie_distinct_count, dl.clique_distinct_count
            FROM totals t
            JOIN distinct_curies dc USING (curie_prefix)
            JOIN distinct_cliques dl USING (curie_prefix)
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

    edges.close()
    cliques.close()


def generate_clique_leaders_report(parquet_root, duckdb_filename, by_clique_report_json, duckdb_config=None):
    """
    Generate a report about all the prefixes within this system, grouped by filename.

    See thoughts at https://github.com/NCATSTranslator/Babel/issues/359

    :param parquet_root: The root directory for the Parquet files. We expect these to have subdirectories named
        e.g. `filename=AnatomicalEntity/Clique.parquet`, etc.
    :param duckdb_filename: A temporary DuckDB file to use.
    :param by_clique_report_json: The prefix report as JSON.
    """

    db = setup_duckdb(duckdb_filename, duckdb_config)

    edges = db.read_parquet(os.path.join(parquet_root, "**/Edge.parquet"), hive_partitioning=True)
    # cliques = db.read_parquet(os.path.join(parquet_root, "**/Clique.parquet"), hive_partitioning=True)

    # Step 1. Generate a by-clique report.
    #
    # As in generate_curie_report, grouped COUNT(DISTINCT) over the full Edge set is not spillable,
    # so we pre-reduce each distinct count with a ``SELECT DISTINCT`` (a spillable hash aggregation)
    # and COUNT(*) over it, joining the per-key results back together.
    logger.info("Generating clique report...")
    with log_duckdb_settings_on_error(
        db, "generate_clique_leaders_report: per-filename totals (spillable distinct counts)"
    ):
        cliques = db.sql("""
            WITH base AS (
                SELECT filename, clique_leader, curie FROM edges WHERE conflation = 'None'
            ),
            totals AS (
                SELECT filename, COUNT(*) AS curie_count FROM base GROUP BY filename
            ),
            distinct_curies AS (
                SELECT filename, COUNT(*) AS distinct_curie_count
                FROM (SELECT DISTINCT filename, curie FROM base) GROUP BY filename
            ),
            distinct_cliques AS (
                SELECT filename, COUNT(*) AS distinct_clique_count
                FROM (SELECT DISTINCT filename, clique_leader FROM base) GROUP BY filename
            )
            SELECT t.filename, dl.distinct_clique_count, dc.distinct_curie_count, t.curie_count
            FROM totals t
            JOIN distinct_curies dc USING (filename)
            JOIN distinct_cliques dl USING (filename)
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
    with log_duckdb_settings_on_error(
        db, "generate_clique_leaders_report: per-prefix breakdown (COUNT(DISTINCT) over all edges)"
    ):
        clique_per_curie = db.sql("""
            WITH base AS (
                SELECT filename, clique_leader_prefix, curie_prefix, curie
                FROM edges WHERE conflation = 'None'
            ),
            totals AS (
                SELECT filename, clique_leader_prefix, curie_prefix, COUNT(*) AS curie_count
                FROM base GROUP BY filename, clique_leader_prefix, curie_prefix
            ),
            distinct_curies AS (
                SELECT filename, clique_leader_prefix, curie_prefix, COUNT(*) AS distinct_curie_count
                FROM (SELECT DISTINCT filename, clique_leader_prefix, curie_prefix, curie FROM base)
                GROUP BY filename, clique_leader_prefix, curie_prefix
            )
            SELECT t.filename, t.clique_leader_prefix, t.curie_prefix,
                   dc.distinct_curie_count, t.curie_count
            FROM totals t
            JOIN distinct_curies dc USING (filename, clique_leader_prefix, curie_prefix)
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

    edges.close()
    # cliques.close()


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
