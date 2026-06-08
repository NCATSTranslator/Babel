# The DuckDB exporter can be used to export particular intermediate files into the
# in-process database engine DuckDB (https://duckdb.org) for future querying.
import os.path
import tempfile
from contextlib import contextmanager

import duckdb

from src.util import get_config, get_logger

logger = get_logger(__name__)

# The DuckDB settings most relevant to diagnosing an out-of-memory or spill failure. Kept short
# so the on-error log line stays readable; the full set is dumped by setup_duckdb() at connect.
_DUCKDB_DIAGNOSTIC_SETTINGS = (
    "memory_limit",
    "max_memory",
    "threads",
    "temp_directory",
    "max_temp_directory_size",
    "preserve_insertion_order",
)


@contextmanager
def log_duckdb_settings_on_error(db, operation):
    """Log the effective DuckDB memory/spill settings if the wrapped call raises.

    DuckDB's OutOfMemory and IO errors don't say which limits were in force or which step hit
    them, which makes the bare Snakemake traceback hard to act on. Wrapping a query in this
    context manager emits one ERROR line naming the `operation` and the relevant settings before
    re-raising the original exception unchanged.
    """
    try:
        yield
    except duckdb.Error as exc:
        try:
            placeholders = ", ".join("?" for _ in _DUCKDB_DIAGNOSTIC_SETTINGS)
            rows = db.execute(
                f"SELECT name, value FROM duckdb_settings() WHERE name IN ({placeholders})",
                list(_DUCKDB_DIAGNOSTIC_SETTINGS),
            ).fetchall()
            settings = ", ".join(f"{name}={value}" for name, value in sorted(rows))
        except Exception:  # diagnostics must never mask the real error
            settings = "<could not read duckdb_settings()>"
        logger.error(
            "DuckDB operation failed during %s (%s: %s); effective settings: %s",
            operation,
            type(exc).__name__,
            exc,
            settings,
        )
        raise


# Some configuration items for controlling loads.
MIN_FILE_SIZE_FOR_SPLITTING_LOAD = 44_000_000_000
CHUNK_LINE_SIZE = 60_000_000


def setup_duckdb(duckdb_filename, duckdb_config=None):
    """
    Set up a DuckDB instance using the settings in the config.

    :return: The DuckDB instance to be used.
    """
    if not duckdb_config:
        duckdb_config = {}

    # We want to use (1) the global duckdb_config, then (2) the duckdb_config passed to this function.
    complete_duckdb_config = {**get_config().get("duckdb_config", {}), **duckdb_config}

    # These two keys are Babel conveniences, not DuckDB connect() settings, so pull them out
    # before handing the rest to duckdb.connect(). They let an individual rule override where
    # DuckDB spills and how large that spill may grow.
    temp_directory_override = complete_duckdb_config.pop("temp_directory", None)
    max_temp_directory_size = complete_duckdb_config.pop("max_temp_directory_size", None)

    db = duckdb.connect(duckdb_filename, config=complete_duckdb_config)

    # Apply some Babel-wide settings to DuckDB.
    config = get_config()

    # Decide where DuckDB spills larger-than-memory intermediates. Precedence:
    #   1. an explicit per-call `temp_directory` (a rule that wants a specific scratch area),
    #   2. the BABEL_DUCKDB_TEMP_DIR environment variable (set per job at submission time),
    #   3. the global `tmp_directory` from config.yaml.
    # Hatteras has no large node-local disk we can use: /tmp is a ~16 GB rootfs, /dev/shm is
    # RAM (charged against the job's cgroup), and /scratch and /projects are both NFS. So the
    # default stays on the parallel filesystem; see slurm/README.md ("Temporary scratch space").
    temp_directory = temp_directory_override or os.environ.get("BABEL_DUCKDB_TEMP_DIR") or config.get("tmp_directory")
    if temp_directory:
        # Give every job its own spill subdirectory. Multiple report jobs previously shared a
        # single NFS temp directory, which produced "stale file handle" / "could not read
        # enough bytes" IO errors when one job's temp files raced against another's; per-job
        # isolation removes that contention regardless of which filesystem is used.
        job_id = os.environ.get("SLURM_JOB_ID") or str(os.getpid())
        temp_directory = os.path.join(temp_directory, f"duckdb-{job_id}")
        os.makedirs(temp_directory, exist_ok=True)
        db.execute(f"SET temp_directory = '{temp_directory}'")
        db.execute(f"SET max_temp_directory_size = '{max_temp_directory_size or '500GB'}'")

    # We need to set local settings after the connection has been opened.
    db.execute("SET enable_progress_bar=true")

    # Display all the settings.
    settings = db.sql("SELECT * FROM duckdb_settings()")
    logger.info("DuckDB connected with the following settings:")
    for row in settings.fetchall():
        logger.info(f" - {row[0]}: {row[1]}")

    return db


def export_compendia_to_parquet(compendium_filename, clique_parquet_filename, edge_parquet_filename, duckdb_filename):
    """
    Export a compendium to a Parquet file via a DuckDB.

    :param compendium_filename: The compendium filename to read.
    :param clique_parquet_filename: The filename for the Clique.parquet file.
    :param edge_parquet_filename: The filename for the Edge.parquet file.
    :param duckdb_filename: The DuckDB filename to write.

    The Node.parquet file is written alongside clique_parquet_filename (same directory); the
    Clique and Edge Parquet paths are passed explicitly so the Snakemake rule and this function
    agree on them and Snakemake can track them as declared outputs.
    """

    # Make sure that duckdb_filename doesn't exist.
    if os.path.exists(duckdb_filename):
        raise RuntimeError(f"Will not overwrite existing file {duckdb_filename}")

    duckdb_dir = os.path.dirname(duckdb_filename)
    os.makedirs(duckdb_dir, exist_ok=True)

    # Node.parquet is written alongside the Clique.parquet file and is also declared as a rule
    # output; the Clique and Edge paths arrive as explicit arguments.
    parquet_dir = os.path.dirname(clique_parquet_filename)
    os.makedirs(parquet_dir, exist_ok=True)
    os.makedirs(os.path.dirname(edge_parquet_filename), exist_ok=True)
    node_parquet_filename = os.path.join(parquet_dir, "Node.parquet")

    compendium_basename = os.path.basename(compendium_filename)
    with setup_duckdb(duckdb_filename) as db:
        # Step 1. Create a Nodes table with all the nodes from compendium_filename.
        db.sql(
            """CREATE TABLE Node (curie STRING, curie_prefix STRING, label STRING, label_lc STRING, description STRING[], taxa STRING[])"""
        )

        compendium_filesize = os.path.getsize(compendium_filename)
        if compendium_filesize < MIN_FILE_SIZE_FOR_SPLITTING_LOAD:
            # This seems to be around the threshold where 500G is inadequate on Hatteras. So let's try splitting it.
            logger.info(
                f"Loading {compendium_filename} into DuckDB (size {compendium_filesize}) in a single direct ingest."
            )
            with log_duckdb_settings_on_error(
                db, f"export_compendia_to_parquet: load Node table from {compendium_basename} (single ingest)"
            ):
                db.execute(
                    """INSERT INTO Node
                          WITH extracted AS (
                              SELECT json_extract_string(identifier_row.value, ['i', 'l', 'd', 't']) AS extracted_list
                              FROM read_json($1, format='newline_delimited') AS clique,
                                   json_each(clique.identifiers) AS identifier_row
                          )
                          SELECT
                              extracted_list[1] AS curie,
                              split_part(extracted_list[1], ':', 1) AS curie_prefix,
                              extracted_list[2] AS label,
                              LOWER(label) AS label_lc,
                              extracted_list[3] AS description,
                              extracted_list[4] AS taxa
                          FROM extracted""",
                    [compendium_filename],
                )
        else:
            logger.info(
                f"Loading {compendium_filename} into DuckDB (size {compendium_filesize}) in multiple chunks of {CHUNK_LINE_SIZE:,} lines:"
            )
            chunk_filenames = []
            lines_added = 0
            lines_added_file = 0
            output_file = None
            with open(compendium_filename, encoding="utf-8") as inf:
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
                with log_duckdb_settings_on_error(
                    db,
                    f"export_compendia_to_parquet: load Node table from {compendium_basename} (chunk {chunk_filename})",
                ):
                    db.execute(
                        """INSERT INTO Node
                              WITH extracted AS (
                                  SELECT json_extract_string(identifier_row.value, ['i', 'l', 'd', 't']) AS extracted_list
                                  FROM read_json($1, format='newline_delimited') AS clique,
                                       json_each(clique.identifiers) AS identifier_row
                              )
                              SELECT
                                  extracted_list[1] AS curie,
                                  split_part(extracted_list[1], ':', 1) AS curie_prefix,
                                  extracted_list[2] AS label,
                                  LOWER(label) AS label_lc,
                                  extracted_list[3] AS description,
                                  extracted_list[4] AS taxa
                              FROM extracted""",
                        [chunk_filename],
                    )
                logger.info(f" - Loaded chunk file {chunk_filename} into DuckDB.")
                os.remove(chunk_filename)
                logger.info(f" - Deleted chunk file {chunk_filename}.")

            logger.info(f"Completed loading {compendium_filename} into DuckDB.")
            logger.info(f" - Line count: {lines_added:,}.")

            node_count = db.execute("SELECT COUNT(*) FROM Node").fetchone()[0]
            logger.info(f" - Identifier count: {node_count:,}.")

        with log_duckdb_settings_on_error(
            db, f"export_compendia_to_parquet: write Node Parquet for {compendium_basename}"
        ):
            db.table("Node").write_parquet(node_parquet_filename)

        # Step 2. Create a Cliques table with all the cliques from this file.
        db.sql("""CREATE TABLE Clique
                (clique_leader STRING, preferred_name STRING, clique_identifier_count INT, biolink_type STRING,
                information_content FLOAT)""")
        with log_duckdb_settings_on_error(
            db, f"export_compendia_to_parquet: build and write Clique table for {compendium_basename}"
        ):
            db.execute(
                """INSERT INTO Clique SELECT
                            json_extract_string(identifiers, '$[0].i') AS clique_leader,
                            preferred_name,
                            len(identifiers) AS clique_identifier_count,
                            type AS biolink_type,
                            ic AS information_content
                        FROM read_json(?, format='newline_delimited')""",
                [compendium_filename],
            )
            db.table("Clique").write_parquet(clique_parquet_filename)

        # Step 2. Create an Edge table with all the clique/CURIE relationships from this file.
        #
        # biolink_type is denormalized onto every edge here, where it is free: it is the same
        # top-level ``type`` field the Clique build above already reads, and each compendium record
        # carries it inline. Storing it per-edge lets the cross-compendium curie report group by
        # (curie_prefix, biolink_type) with a plain scan instead of joining the full Edge table
        # (~1.5B rows) against the Clique table (~200M rows) -- a large-vs-large join that OOM-killed
        # the report rule even on a largemem node.
        db.sql(
            """CREATE TABLE Edge (clique_leader STRING, curie STRING, conflation STRING,
                clique_leader_prefix STRING, curie_prefix STRING, biolink_type STRING)"""
        )
        with log_duckdb_settings_on_error(
            db, f"export_compendia_to_parquet: build and write Edge table for {compendium_basename}"
        ):
            db.execute(
                """INSERT INTO Edge
                    WITH unnested AS (
                        SELECT
                            json_extract_string(identifiers, '$[0].i') AS clique_leader,
                            UNNEST(json_extract_string(identifiers, '$[*].i')) AS curie,
                            'None' AS conflation,
                            type AS biolink_type
                        FROM read_json(?, format='newline_delimited')
                    )
                    SELECT
                        clique_leader,
                        curie,
                        conflation,
                        split_part(clique_leader, ':', 1) AS clique_leader_prefix,
                        split_part(curie, ':', 1) AS curie_prefix,
                        biolink_type
                    FROM unnested""",
                [compendium_filename],
            )
            db.table("Edge").write_parquet(edge_parquet_filename)


def export_conflation_to_parquet(conflation_filename, conflation_type, duckdb_filename, parquet_filename):
    """
    Export a conflation file to a Parquet file via DuckDB.

    The conflation file is NDJSON where each line is a JSON array of CURIEs; the first element
    is the conflation group leader.

    :param conflation_filename: The conflation file (NDJSON) to read.
    :param conflation_type: A string identifying the conflation type, e.g. 'GeneProtein'.
    :param duckdb_filename: A temporary DuckDB file to use during export.
    :param parquet_filename: The output Parquet file path.
    """
    if os.path.exists(duckdb_filename):
        raise RuntimeError(f"Will not overwrite existing file {duckdb_filename}")

    os.makedirs(os.path.dirname(duckdb_filename), exist_ok=True)
    os.makedirs(os.path.dirname(parquet_filename), exist_ok=True)

    with setup_duckdb(duckdb_filename) as db:
        db.sql(
            "CREATE TABLE Conflation (conflation_type STRING, conflation_leader STRING, curie STRING, curie_prefix STRING)"
        )
        with log_duckdb_settings_on_error(
            db,
            f"export_conflation_to_parquet: build and write {conflation_type} Conflation from {os.path.basename(conflation_filename)}",
        ):
            db.execute(
                """INSERT INTO Conflation
                WITH raw AS (
                    SELECT column0 AS line_text
                    FROM read_csv(?, header=False, columns={'column0': 'VARCHAR'})
                    WHERE trim(column0) != ''
                ),
                unnested AS (
                    SELECT
                        ? AS conflation_type,
                        json_extract_string(line_text::JSON, '$[0]') AS conflation_leader,
                        UNNEST(json_extract_string(line_text::JSON, '$[*]')) AS curie
                    FROM raw
                )
                SELECT
                    conflation_type,
                    conflation_leader,
                    curie,
                    split_part(curie, ':', 1) AS curie_prefix
                FROM unnested""",
                [conflation_filename, conflation_type],
            )
            db.table("Conflation").write_parquet(parquet_filename)


def export_synonyms_to_parquet(synonyms_filename_gz, duckdb_filename, synonyms_parquet_filename, memory_limit_mb=None):
    """
    Export a synonyms file to a DuckDB directory.

    :param synonyms_filename_gz: The synonym file (gzipped JSONL) to export to Parquet.
    :param duckdb_filename: A DuckDB file to temporarily store data in.
    :param synonyms_parquet_filename: The Parquet file to store the synonyms in.
    :param memory_limit_mb: DuckDB memory limit in MB. When set, overrides DuckDB's default
        (75% of system RAM), which can exceed the SLURM allocation on shared HPC nodes.
    """

    # Make sure that duckdb_filename doesn't exist.
    if os.path.exists(duckdb_filename):
        raise RuntimeError(f"Will not overwrite existing file {duckdb_filename}")

    duckdb_dir = os.path.dirname(duckdb_filename)
    os.makedirs(duckdb_dir, exist_ok=True)

    duckdb_config = {}
    if memory_limit_mb is not None:
        duckdb_config["memory_limit"] = f"{memory_limit_mb}MB"

    with setup_duckdb(duckdb_filename, duckdb_config=duckdb_config) as db:
        synonyms_jsonl = db.read_json(synonyms_filename_gz, format="newline_delimited")

        # We can't execute the following query unless we have at least one row in the input data.
        result = db.execute("SELECT COUNT(*) AS row_count FROM synonyms_jsonl").fetchone()
        row_count = result[0]

        if row_count > 0:
            # Write directly to Parquet without an intermediate in-memory Synonym table.
            # INSERT INTO a table would materialise all unnested rows in RAM; .write_parquet()
            # streams row groups to disk so peak memory stays proportional to one row group.
            with log_duckdb_settings_on_error(
                db, f"export_synonyms_to_parquet: write Parquet from {os.path.basename(synonyms_filename_gz)}"
            ):
                db.sql("""
                    SELECT curie AS clique_leader, preferred_name,
                        LOWER(preferred_name) AS preferred_name_lc,
                        CONCAT('biolink:', json_extract_string(types, '$[0]')) AS biolink_type,
                        unnest(names) AS label, LOWER(label) AS label_lc
                    FROM synonyms_jsonl
                """).write_parquet(synonyms_parquet_filename)
        else:
            db.sql("""
                SELECT NULL::VARCHAR AS clique_leader, NULL::VARCHAR AS preferred_name,
                    NULL::VARCHAR AS preferred_name_lc, NULL::VARCHAR AS biolink_type,
                    NULL::VARCHAR AS label, NULL::VARCHAR AS label_lc
                WHERE FALSE
            """).write_parquet(synonyms_parquet_filename)

        synonyms_jsonl.close()
