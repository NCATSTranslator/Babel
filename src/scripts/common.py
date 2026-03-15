"""Shared utilities for Babel analysis scripts that require generated DuckDB/Parquet files."""

import os
import sys

from src.util import get_config, get_logger

logger = get_logger(__name__)


def get_parquet_dir(config=None) -> str:
    """Return the path to the DuckDB Parquet output directory."""
    if config is None:
        config = get_config()
    return os.path.join(config["output_directory"], "duckdb", "parquet")


def check_compendia_parquet_ready(config=None) -> str:
    """
    Check that the compendia Parquet export is complete and return the parquet directory path.

    Exits with an error message if the `duckdb/compendia_done` signal file does not exist
    or if the parquet directory is missing.
    """
    if config is None:
        config = get_config()

    signal_file = os.path.join(config["output_directory"], "duckdb", "compendia_done")
    if not os.path.exists(signal_file):
        print(
            f"Error: DuckDB compendia export not complete. Expected signal file: {signal_file}\n"
            "Run `uv run snakemake --cores N export_all_compendia_to_duckdb` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    parquet_dir = get_parquet_dir(config)
    if not os.path.isdir(parquet_dir):
        print(
            f"Error: Parquet directory not found: {parquet_dir}\n"
            "Run `uv run snakemake --cores N export_all_compendia_to_duckdb` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    return parquet_dir


def check_all_parquet_ready(config=None) -> str:
    """
    Check that both compendia and synonyms Parquet exports are complete and return the parquet directory path.

    Exits with an error message if the `duckdb/done` signal file does not exist
    or if the parquet directory is missing.
    """
    if config is None:
        config = get_config()

    signal_file = os.path.join(config["output_directory"], "duckdb", "done")
    if not os.path.exists(signal_file):
        print(
            f"Error: DuckDB export not complete. Expected signal file: {signal_file}\n"
            "Run `uv run snakemake --cores N duckdb` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    parquet_dir = get_parquet_dir(config)
    if not os.path.isdir(parquet_dir):
        print(
            f"Error: Parquet directory not found: {parquet_dir}\n"
            "Run `uv run snakemake --cores N duckdb` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    return parquet_dir
