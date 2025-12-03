# The DuckDB exporter can be used to export particular intermediate files into the
# in-process database engine DuckDB (https://duckdb.org) for future querying.
import os.path
from pathlib import Path

import duckdb

from src.util import get_config, get_logger

logger = get_logger(__name__)

def setup_duckdb(duckdb_filename):
    """
    Set up a DuckDB instance using the settings in the config.

    :return: The DuckDB instance to be used.
    """
    db = duckdb.connect(duckdb_filename, config=get_config().get("duckdb_config", {}))

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
        # Step 1. Load the entire synonyms file.
        compendium_jsonl = db.read_json(compendium_filename, format="newline_delimited")

        # TODO: add props

        # Step 2. Create a Cliques table with all the cliques from this file.
        db.sql("""CREATE TABLE Clique
                (clique_leader STRING, preferred_name STRING, clique_identifier_count INT, biolink_type STRING,
                information_content FLOAT)""")
        db.sql("""INSERT INTO Clique SELECT
                        json_extract_string(identifiers, '$[0].i') AS clique_leader,
                        preferred_name,
                        len(identifiers) AS clique_identifier_count,
                        type AS biolink_type,
                        ic AS information_content
                    FROM compendium_jsonl""")

        # Step 3. Create an Edge table with all the clique/CURIE relationships from this file.
        db.sql("CREATE TABLE Edge (clique_leader STRING, curie STRING, conflation STRING)")
        db.sql("""INSERT INTO Edge SELECT
                json_extract_string(identifiers, '$[0].i') AS clique_leader,
                UNNEST(json_extract_string(identifiers, '$[*].i')) AS curie,
                'None' AS conflation
            FROM compendium_jsonl""")

        # Step 4. Create a Nodes table with all the nodes from this file.
        db.sql("""CREATE TABLE Node (curie STRING, label STRING, label_lc STRING, description STRING[])""")
        db.sql("""INSERT INTO Node
            SELECT
                json_extract_string(identifier, '$.identifiers.i') AS curie,
                json_extract_string(identifier, '$.identifiers.l') AS label,
                LOWER(label) AS label_lc,
                json_extract_string(identifier, '$.identifiers.d') AS description
            FROM compendium_jsonl, UNNEST(identifiers) AS identifier""")

        # Step 5. Export as Parquet files.
        db.sql("SELECT * FROM Clique").write_parquet(clique_parquet_filename)
        db.sql("SELECT * FROM Edge").write_parquet(edge_parquet_filename)
        db.sql("SELECT * FROM Node").write_parquet(node_parquet_filename)


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


def export_intermediates_to_parquet(intermediate_directory, duckdb_filename, ids_parquet_filename, concords_parquet_filename, metadata_parquet_filename):
    """
    Export all the intermediate files into Parquet files, which will be easier to download and manipulate
    than the multiple original files.

    :param intermediate_directory: The intermediate directory containing the concords.
    :param duckdb_filename: A DuckDB file to temporarily store data in.
    :param ids_parquet_filename: The Parquet file to store the IDs.
    :param concords_parquet_filename: The Parquet file to store the concords.
    :param metadata_parquet_filename: The Parquet file to store the ID and concord metadata in.
    """

    # Make sure that duckdb_filename doesn't exist.
    if os.path.exists(duckdb_filename):
        raise RuntimeError(f"Will not overwrite existing file {duckdb_filename}")

    duckdb_dir = os.path.dirname(duckdb_filename)
    os.makedirs(duckdb_dir, exist_ok=True)

    with setup_duckdb(duckdb_filename) as db:
        db.sql("""CREATE TABLE Concord (filename STRING, subj STRING, pred STRING, obj STRING)""")
        db.sql("""CREATE TABLE Identifier (filename STRING, curie STRING, biolink_type STRING)""")
        db.sql("""CREATE TABLE Metadata (filename STRING, subject_filename STRING, subject_file_path STRING, metadata_json STRING)""")

        intermediate_path = Path(intermediate_directory)

        # Load concord files.
        for concord_path in intermediate_path.glob("*/concords/*"):
            if os.path.isdir(concord_path):
                logger.info(f"Skipping directory {concord_path}")
                continue

            if os.path.getsize(concord_path) == 0:
                logger.warning(f"Skipping empty concord file {concord_path}")
                continue

            filename = concord_path.name
            if filename.lower().startswith("metadata-") or filename.lower() == "metadata.yaml":
                subject_filename = filename
                if subject_filename.startswith("metadata-") and subject_filename.endswith(".yaml"):
                    subject_filename = subject_filename[9:]
                    subject_filename = subject_filename[:-5]

                logger.info(f"Loading concord metadata from {concord_path} to subject file {subject_filename}")
                db.execute("INSERT INTO Metadata VALUES (?, ?, ?, ?)", [
                    str(concord_path),
                    subject_filename,
                    str(concord_path.parent / subject_filename),
                    concord_path.read_text()
                ])
                continue

            logger.info(f"Loading concords from {concord_path}")
            db.execute(
                "INSERT INTO Concord SELECT $1 AS filename, subj, pred, obj FROM read_csv($1, delim='\\t', header=false, " +
                "columns={'subj': 'VARCHAR', 'pred': 'VARCHAR', 'obj': 'VARCHAR'})",
                [str(concord_path)])

        del concord_path

        # Load identifier files.
        for ids_path in intermediate_path.glob("*/ids/*"):
            if os.path.isdir(ids_path):
                logger.info(f"Skipping directory {ids_path}")
                continue

            if os.path.getsize(ids_path) == 0:
                logger.warning(f"Skipping empty concord file {ids_path}")
                continue

            filename = ids_path.name
            if filename.lower().startswith("metadata-") or filename.lower() == "metadata.yaml":
                subject_filename = filename
                if subject_filename.startswith("metadata-") and subject_filename.endswith(".yaml"):
                    subject_filename = subject_filename[9:]
                    subject_filename = subject_filename[:-5]

                logger.info(f"Loading concord metadata from {ids_path} to subject file {subject_filename}")
                db.execute("INSERT INTO Metadata VALUES (?, ?, ?, ?)", [
                    str(ids_path),
                    subject_filename,
                    str(ids_path.parent / subject_filename),
                    ids_path.read_text()
                ])
                continue

            logger.info(f"Loading identifiers from {ids_path}")

            # ID files sometimes have a single column and sometimes have two, so we need to determine which one this is.
            with open(ids_path, "r") as f:
                first_line = f.readline()
                second_line = f.readline()
                num_cols = len(first_line.split("\t"))
                if len(second_line.split("\t")) != num_cols:
                    raise RuntimeError(f"Inconsistent number of columns in {ids_path}: {num_cols} (first line: '{first_line}', second line: '{second_line}').")

            if num_cols == 1:
                db.execute(
                    "INSERT INTO Identifier SELECT $1 AS filename, curie, NULL AS biolink_type FROM read_csv($1, delim='\\t', header=false, " +
                    "columns={'curie': 'VARCHAR'})",
                    [str(ids_path)])
            elif num_cols == 2:
                db.execute(
                    "INSERT INTO Identifier SELECT $1 AS filename, curie, biolink_type FROM read_csv($1, delim='\\t', header=false, " +
                    "columns={'curie': 'VARCHAR', 'biolink_type': 'VARCHAR'})",
                    [str(ids_path)])
            else:
                raise RuntimeError(f"Unexpected number of columns in {ids_path}: {num_cols} (first line: '{first_line}').")

        db.table('Concord').write_parquet(concords_parquet_filename)
        db.table('Identifier').write_parquet(ids_parquet_filename)
        db.table('Metadata').write_parquet(metadata_parquet_filename)
