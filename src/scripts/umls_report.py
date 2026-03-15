"""CLI script to report on UMLS identifiers found across all compendia Parquet files."""

import os
import tempfile

import click

from src.exporters.duckdb_exporters import setup_duckdb
from src.scripts.common import check_compendia_parquet_ready
from src.util import get_config, get_logger

logger = get_logger(__name__)


@click.command()
@click.option("--output", "-o", default="umls_report.csv", show_default=True, help="Output CSV file path.")
@click.option(
    "--duckdb-file",
    default=None,
    help="Temporary DuckDB file path. Defaults to an auto-generated temp file deleted after use.",
)
@click.option("--memory-limit", default="10G", show_default=True, help="DuckDB memory limit.")
def main(output, duckdb_file, memory_limit):
    """Report on UMLS identifiers found across all compendia Parquet files.

    Queries Edge.parquet and Clique.parquet to produce one row per (UMLS ID, clique) pairing,
    written to a CSV file.
    """
    config = get_config()
    parquet_dir = check_compendia_parquet_ready(config)

    auto_temp = duckdb_file is None
    if auto_temp:
        tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
        tmp.close()
        duckdb_file = tmp.name
        logger.info(f"Using temporary DuckDB file: {duckdb_file}")

    try:
        db = setup_duckdb(duckdb_file, {"memory_limit": memory_limit})

        edges = db.read_parquet(os.path.join(parquet_dir, "**/Edge.parquet"), hive_partitioning=True)
        cliques = db.read_parquet(os.path.join(parquet_dir, "**/Clique.parquet"), hive_partitioning=True)

        logger.info("Building UMLS report table...")
        db.sql("""
            CREATE TABLE umls_report AS
            SELECT
                e.curie AS umls_id,
                'https://uts.nlm.nih.gov/uts/umls/concept/' || split_part(e.curie, ':', 2) AS url,
                e.filename AS filename,
                e.clique_leader AS clique_leader,
                e.clique_leader_prefix AS clique_leader_prefix,
                c.biolink_type AS biolink_type
            FROM edges e
            JOIN cliques c
              ON e.clique_leader = c.clique_leader
             AND e.filename = c.filename
            WHERE e.curie_prefix = 'UMLS'
              AND e.conflation = 'None'
            ORDER BY e.curie, e.filename
        """)

        logger.info(f"Writing UMLS report to {output}...")
        db.sql("SELECT * FROM umls_report").write_csv(output)

        total_rows = db.sql("SELECT COUNT(*) FROM umls_report").fetchone()[0]
        unique_ids = db.sql("SELECT COUNT(DISTINCT umls_id) FROM umls_report").fetchone()[0]
        duplicates = db.sql("""
            SELECT COUNT(*) FROM (
                SELECT umls_id
                FROM umls_report
                GROUP BY umls_id
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]

        click.echo(f"Output written to: {output}")
        click.echo(f"Total UMLS ID occurrences (rows): {total_rows:,}")
        click.echo(f"Unique UMLS IDs:                  {unique_ids:,}")
        click.echo(f"UMLS IDs in more than one clique: {duplicates:,}")

        edges.close()
        cliques.close()
        db.close()

    finally:
        if auto_temp and os.path.exists(duckdb_file):
            os.unlink(duckdb_file)
            logger.info(f"Removed temporary DuckDB file: {duckdb_file}")


if __name__ == "__main__":
    main()
