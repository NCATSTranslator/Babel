# Shared code used by Snakemake files
import gzip
import os
import shutil

import src.util

logger = src.util.LoggingUtil.init_logging(__name__, level="INFO")


def common_download_files(config):
    """
    Return every shared label, synonym and description file under ``{download_directory}/common/``.

    ``write_compendium()`` reads all of them, through ``NodeFactory``, ``SynonymFactory`` and
    ``DescriptionFactory``, and ``leftover_umls``'s ``NodeFactory`` reads the labels, so every rule that
    reaches either must list these as inputs. They used to arrive only as ``get_icrdf``'s inputs, relying on
    every compendium rule declaring ``icRDF.tsv``. That stops working once ``icRDF.tsv`` exists without them
    (copied from a published build, say): Snakemake then has no reason to fetch them, and the compendium
    rule fails with ``FileNotFoundError``. ``tests/test_snakefile_util.py`` checks that every rule
    declaring ``icRDF.tsv`` declares these too.

    :param config: The Snakemake config, whose ``common`` section lists the files by kind.
    :return: A list of paths, labels first, then synonyms, then descriptions.
    """
    return [
        os.path.join(config["download_directory"], "common", filename)
        for kind in ("labels", "synonyms", "descriptions")
        for filename in config["common"][kind]
    ]


def duckdb_memory_limit_mb(mem_mb, fraction=0.75):
    """Convert a Snakemake `resources.mem_mb` value into a DuckDB memory limit in MB.

    DuckDB otherwise auto-sizes its memory limit to 75% of *total system* RAM, which can far exceed
    the SLURM allocation on a multi-tenant HPC node. We give it `fraction` of the allocation so that
    Python and OS overhead don't push total RSS over the job's cgroup limit.

    Use `resources.mem_mb`, not `resources.mem` -- Snakemake round-trips `resources.mem` through
    `humanfriendly.format_size()` for display (e.g. our "512G" rule setting comes back as "512 GB"),
    while `mem_mb` stays a plain int.

    :param mem_mb: A `resources.mem_mb` value (int, in MB).
    :param fraction: The fraction of the allocation to give DuckDB.
    :return: The memory limit in MB.
    """
    return int(int(mem_mb) * fraction)


def write_done(filename):
    """Write a file to indicate that we are done."""
    with open(filename, "w") as f:
        print("done", f)


def gzip_files(input_filenames):
    """Compress files using Gzip. Like with `gzip`, we compress the file by adding `.gz` to the end of the filename, but
    we do NOT delete the original file -- we'll leave that to the user.

    :param input_filenames: A list of Gzip files to compress.
    """
    logger.info(f"Compressing: {input_filenames}")
    for filename in input_filenames:
        output_filename = filename + ".gz"
        with open(filename, "rb") as f_in, gzip.open(output_filename, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        logger.info(f"Compressed {filename} to {output_filename} using the gzip module.")
    logger.info(f"Done compressing: {input_filenames}")


# List of all the compendia files that need to be converted.
def get_all_compendia(config):
    return (
        config["anatomy_outputs"]
        + config["chemical_outputs"]
        + config["disease_outputs"]
        + config["gene_outputs"]
        + config["genefamily_outputs"]
        + config["process_outputs"]
        + config["protein_outputs"]
        + config["taxon_outputs"]
        + config["cell_line_outputs"]
        + config["umls_outputs"]
        + config["macromolecularcomplex_outputs"]
        + config["publications"]["outputs"]
    )


def get_all_synonyms(config):
    """
    List of all the synonym files, including DrugChemicalConflated. Note that this duplicates synonyms: chemical output
    synonyms will be in both the individual chemical outputs and the DrugChemicalConflated file.

    :param config: The Babel config to use.
    :return: A list of filenames expected in the `synonyms/` directory.
    """
    return (
        config["anatomy_outputs"]
        + config["gene_outputs"]
        + config["protein_outputs"]
        + config["disease_outputs"]
        + config["process_outputs"]
        + config["chemical_outputs"]
        + config["taxon_outputs"]
        + config["cell_line_outputs"]
        + config["genefamily_outputs"]
        + config["drugchemicalconflated_synonym_outputs"]
        + config["geneproteinconflated_synonym_outputs"]
        + config["umls_outputs"]
        + config["macromolecularcomplex_outputs"]
        +
        # Publication.txt is empty, but it's still created, so it needs to be here.
        config["publications"]["outputs"]
    )


def get_all_synonyms_except_drugchemicalconflated(config):
    """
    List of all the synonym files, except DrugChemicalConflated.

    :param config: The Babel config to use.
    :return: A list of filenames expected in the `synonyms/` directory.
    """
    return (
        config["anatomy_outputs"]
        + config["gene_outputs"]
        + config["protein_outputs"]
        + config["disease_outputs"]
        + config["process_outputs"]
        + config["chemical_outputs"]
        + config["taxon_outputs"]
        + config["cell_line_outputs"]
        + config["genefamily_outputs"]
        +
        # config['drugchemicalconflated_synonym_outputs'] +
        config["geneproteinconflated_synonym_outputs"]
        + config["umls_outputs"]
        + config["macromolecularcomplex_outputs"]
    )


def get_all_synonyms_with_drugchemicalconflated(config):
    """
    List of all the synonym files including DrugChemicalConflated instead of the files it duplicates.

    :param config: The Babel config to use.
    :return: A list of filenames expected in the `synonyms/` directory.
    """
    return (
        config["anatomy_outputs"]
        + config["gene_outputs"]
        + config["protein_outputs"]
        + config["disease_outputs"]
        + config["process_outputs"]
        +
        # config['chemical_outputs'] +
        config["taxon_outputs"]
        + config["cell_line_outputs"]
        + config["genefamily_outputs"]
        + config["drugchemicalconflated_synonym_outputs"]
        + config["geneproteinconflated_synonym_outputs"]
        + config["umls_outputs"]
        + config["macromolecularcomplex_outputs"]
    )


def get_all_gzipped(file_list):
    """
    Helper method to add '.gz' to all the files in a list (presumably from get_all_synonyms_*()).

    :param file_list: List of filenames.
    :return: List of filenames with '.gz' appended.
    """
    return list(map(lambda x: x + ".gz", file_list))
