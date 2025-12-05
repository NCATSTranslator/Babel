# The DuckDB exporter can be used to export particular intermediate files into the
# in-process database engine DuckDB (https://duckdb.org) for future querying.
import os.path
import tempfile

import duckdb

from src.util import get_config, get_logger

logger = get_logger(__name__)

# Some configuration items for controlling loads.
MIN_FILE_SIZE_FOR_SPLITTING_LOAD = 44_000_000_000
CHUNK_LINE_SIZE = 60_000_000

def setup_duckdb(duckdb_filename):
    """
    Set up a DuckDB instance using the settings in the config.

    :return: The DuckDB instance to be used.
    """
    db = duckdb.connect(duckdb_filename, config=get_config().get("duckdb_config", {}))

    # Set up some Babel-wide settings.
    config = get_config()
    if 'tmp_directory' in config:
        db.execute(f"SET temp_directory = '{config['tmp_directory']}'")
        db.execute("SET max_temp_directory_size = '500GB';")

    # Turn on a progress bar.
    db.sql("PRAGMA enable_progress_bar=true")

    return db


def export_compendia_to_parquet(compendium_filename, clique_parquet_filename, duckdb_filename):
    """
    Export a compendium to a Parquet file via a DuckDB.

    :param compendium_filename: The compendium filename to read.
    :param clique_parquet_filename: The filename for the Clique.parquet file.
    :param duckdb_filename: The DuckDB filename to write. We will write the Parquet files into the directory that
        this file is located in.
    """

    # Make sure that duckdb_filename doesn't exist.
    if os.path.exists(duckdb_filename):
        raise RuntimeError(f"Will not overwrite existing file {duckdb_filename}")

    duckdb_dir = os.path.dirname(duckdb_filename)
    os.makedirs(duckdb_dir, exist_ok=True)

    # We'll create these two files as well, but we don't report them back to Snakemake for now.
    parquet_dir = os.path.dirname(clique_parquet_filename)
    os.makedirs(parquet_dir, exist_ok=True)
    edge_parquet_filename = os.path.join(parquet_dir, "Edge.parquet")
    node_parquet_filename = os.path.join(parquet_dir, "Node.parquet")

    with setup_duckdb(duckdb_filename) as db:
        # Step 1. Create a Nodes table with all the nodes from this file.
        db.sql("""CREATE TABLE Node (curie STRING, label STRING, label_lc STRING, description STRING[], taxa STRING[])""")

        compendium_filesize = os.path.getsize(compendium_filename)
        if compendium_filesize < MIN_FILE_SIZE_FOR_SPLITTING_LOAD:
            # This seems to be around the threshold where 500G is inadequate on Hatteras. So let's try splitting it.
            logger.info(f"Loading {compendium_filename} into DuckDB (size {compendium_filesize}) in a single direct ingest.")
            db.execute("""INSERT INTO Node
                          WITH extracted AS (
                              SELECT json_extract_string(identifier_row.value, ['i', 'l', 'd', 't']) AS extracted_list
                              FROM read_json($1, format='newline_delimited') AS clique,
                                   json_each(clique.identifiers) AS identifier_row
                          )
                          SELECT
                              extracted_list[1] AS curie,
                              extracted_list[2] AS label,
                              LOWER(label) AS label_lc,
                              extracted_list[3] AS description,
                              extracted_list[4] AS taxa
                          FROM extracted""", [compendium_filename])
        else:
            logger.info(f"Loading {compendium_filename} into DuckDB (size {compendium_filesize}) in multiple chunks of {CHUNK_LINE_SIZE:,} lines:")
            chunk_filenames = []
            lines_added = 0
            lines_added_file = 0
            output_file = None
            with open(compendium_filename, "r", encoding="utf-8") as inf:
                for line in inf:
                    if output_file is None:
                        output_file = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8")
                        chunk_filenames.append(output_file.name)
                        logger.info(f" - Created chunk file {output_file.name}.")
                    output_file.write(line)
                    lines_added += 1
                    lines_added_file += 1
                    if lines_added % CHUNK_LINE_SIZE == 0:
                        logger.info(f" - Wrote {lines_added_file:,} lines into {output_file.name}.")
                        lines_added_file = 0
                        output_file.close()
                        output_file = None

            if output_file is not None:
                output_file.close()

            logger.info(f"Loaded {len(chunk_filenames)} containing {lines_added:,} lines into chunk files.")
            for chunk_filename in chunk_filenames:
                db.execute("""INSERT INTO Node
                              WITH extracted AS (
                                  SELECT json_extract_string(identifier_row.value, ['i', 'l', 'd', 't']) AS extracted_list
                                  FROM read_json($1, format='newline_delimited') AS clique,
                                       json_each(clique.identifiers) AS identifier_row
                              )
                              SELECT
                                  extracted_list[1] AS curie,
                                  extracted_list[2] AS label,
                                  LOWER(label) AS label_lc,
                                  extracted_list[3] AS description,
                                  extracted_list[4] AS taxa
                              FROM extracted""", [chunk_filename])
                logger.info(f" - Loaded chunk file {chunk_filename} into DuckDB.")
                os.remove(chunk_filename)
                logger.info(f" - Deleted chunk file {chunk_filename}.")

            logger.info(f"Completed loading {compendium_filename} into DuckDB.")
            logger.info(f" - Line count: {lines_added:,}.")

            node_count = db.execute('SELECT COUNT(*) FROM Node').fetchone()[0]
            logger.info(f" - Identifier count: {node_count:,}.")

        db.table("Node").write_parquet(node_parquet_filename)

        # Step 2. Create a Cliques table with all the cliques from this file.
        db.sql("""CREATE TABLE Clique
                (clique_leader STRING, preferred_name STRING, clique_identifier_count INT, biolink_type STRING,
                information_content FLOAT)""")
        db.execute("""INSERT INTO Clique SELECT
                        json_extract_string(identifiers, '$[0].i') AS clique_leader,
                        preferred_name,
                        len(identifiers) AS clique_identifier_count,
                        type AS biolink_type,
                        ic AS information_content
                    FROM read_json(?, format='newline_delimited')""", [compendium_filename])
        db.table("Clique").write_parquet(clique_parquet_filename)

        # Step 2. Create an Edge table with all the clique/CURIE relationships from this file.
        db.sql("CREATE TABLE Edge (clique_leader STRING, curie STRING, conflation STRING)")
        db.execute("""INSERT INTO Edge SELECT
                json_extract_string(identifiers, '$[0].i') AS clique_leader,
                UNNEST(json_extract_string(identifiers, '$[*].i')) AS curie,
                'None' AS conflation
            FROM read_json(?, format='newline_delimited')""", [compendium_filename])
        db.table("Edge").write_parquet(edge_parquet_filename)


def export_synonyms_to_parquet(synonyms_filename_gz, duckdb_filename, synonyms_parquet_filename):
    """
    Export a synonyms file to a DuckDB directory.

    :param synonyms_filename: The synonym file (in JSONL) to export to Parquet.
    :param duckdb_filename: A DuckDB file to temporarily store data in.
    :param synonyms_parquet_filename: The Parquet file to store the synoynms in.
    """

    # Make sure that duckdb_filename doesn't exist.
    if os.path.exists(duckdb_filename):
        raise RuntimeError(f"Will not overwrite existing file {duckdb_filename}")

    duckdb_dir = os.path.dirname(duckdb_filename)
    os.makedirs(duckdb_dir, exist_ok=True)

    with setup_duckdb(duckdb_filename) as db:
        # Step 1. Load the entire synonyms file.
        synonyms_jsonl = db.read_json(synonyms_filename_gz, format="newline_delimited")

        # Step 2. Create a Cliques table with all the cliques from this file.
        # db.sql("CREATE TABLE Cliques (curie TEXT PRIMARY KEY, label TEXT, clique_identifier_count INT, biolink_type TEXT)")
        # db.sql("INSERT INTO Cliques (curie, label, clique_identifier_count, biolink_type) " +
        #       "SELECT curie, replace(preferred_name, '\"\"\"', '\"') AS label, clique_identifier_count, " +
        #       "CONCAT('biolink:', json_extract_string(types, '$[0]')) AS biolink_type FROM synonyms_jsonl")

        # Step 3. Create a Synonyms table with all the cliques from this file.
        db.sql("""CREATE TABLE Synonym (clique_leader STRING, preferred_name STRING, preferred_name_lc STRING,
            biolink_type STRING, label STRING, label_lc STRING)""")

        # We can't execute the following INSERT statement unless we have at least one row in the input data.
        # So let's test that now.
        result = db.execute("SELECT COUNT(*) AS row_count FROM synonyms_jsonl").fetchone()
        row_count = result[0]

        # Assuming we have data in synonyms_jsonl, write it out now.
        if row_count > 0:
            db.sql("""INSERT INTO Synonym
                SELECT curie AS clique_leader, preferred_name,
                    LOWER(preferred_name) AS preferred_name_lc,
                    CONCAT('biolink:', json_extract_string(types, '$[0]')) AS biolink_type,
                    unnest(names) AS label, LOWER(label) AS label_lc
                FROM synonyms_jsonl""")

        # Step 3. Export as Parquet files.
        db.sql("SELECT clique_leader, preferred_name, preferred_name_lc, biolink_type, label, label_lc FROM Synonym").write_parquet(synonyms_parquet_filename)
