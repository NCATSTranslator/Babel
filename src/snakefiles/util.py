# Shared code used by Snakemake files
import gzip
import shutil

from snakemake.exceptions import WorkflowError

import src.util

logger = src.util.LoggingUtil.init_logging(__name__, level="INFO")


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


# Each config.yaml list of identifier prefixes, mapped to the directory (under intermediate_directory) that holds one
# ids file per prefix. The compendium rules read `<intermediate_directory>/<dir>/ids/<prefix>` for every prefix in
# the list, so each one needs a rule that writes it. The directory names differ from the config key in places
# (chemical_ids → chemicals); see also compendium_directories in config.yaml.
ID_PREFIX_LISTS = {
    "anatomy_ids": "anatomy",
    "chemical_ids": "chemicals",
    "disease_ids": "disease",
    "gene_ids": "gene",
    "genefamily_ids": "genefamily",
    "process_ids": "process",
    "protein_ids": "protein",
    "taxon_ids": "taxon",
}


def find_missing_id_prefixes(workflow, ids_dir, config_key, prefixes):
    """Return the sorted prefixes in `prefixes` that no rule in `workflow` can produce as `ids_dir/<prefix>`.

    Each path is checked the way Snakemake itself resolves a target: it is passed through the workflow's path
    modifier (so a `--prefix`/`replace_prefix` or a default storage provider is applied, as it is to rule outputs)
    and then matched against every rule's outputs with `Rule.is_producer()`, so a wildcard output such as
    `ids/{prefix}` counts as covering every prefix it matches.

    :param workflow: The Snakemake `workflow` object of a fully parsed Snakefile.
    :param ids_dir: The ids directory, e.g. `config["intermediate_directory"] + "/gene/ids"`.
    :param config_key: The config.yaml key the prefixes came from; only used in error messages.
    :param prefixes: The list of prefixes from config.yaml.
    :raises WorkflowError: If `prefixes` is a string rather than a list (e.g. from `--config gene_ids=HGNC`), which
        would otherwise be checked one character at a time.
    """
    if not isinstance(prefixes, (list, tuple)):
        message = f"config {config_key} must be a list of prefixes, not {type(prefixes).__name__} {prefixes!r}."
        if isinstance(prefixes, str):
            message += f" On the command line, write it as a YAML list: --config '{config_key}=[\"{prefixes}\"]'."
        raise WorkflowError(message)

    path_modifier = workflow.modifier.path_modifier
    ids_dir = ids_dir.rstrip("/")
    missing = set()
    for prefix in prefixes:
        target = path_modifier.modify(f"{ids_dir}/{prefix}", "output")
        if not any(rule.is_producer(target) for rule in workflow.rules):
            missing.add(prefix)
    return sorted(missing)


def check_id_prefix_rules(workflow, config):
    """Raise WorkflowError if any prefix in a config.yaml `*_ids` list has no rule producing its ids file.

    This catches drift between config.yaml and the snakefiles when Snakemake loads the workflow, instead of hours
    into a run when a compendium rule finally asks for the missing file.

    Call this from the top-level Snakefile *after every `include:`*. It can only see rules that have already been
    defined, so calling it from an individual snakefile would report a false error for any ids rule that lives in a
    snakefile included later.

    :param workflow: The Snakemake `workflow` object.
    :param config: The Snakemake `config` dictionary.
    """
    problems = []
    for config_key, directory in ID_PREFIX_LISTS.items():
        ids_dir = f"{config['intermediate_directory']}/{directory}/ids"
        missing = find_missing_id_prefixes(workflow, ids_dir, config_key, config[config_key])
        if missing:
            problems.append(f"  {config_key}: no rule produces {ids_dir}/<prefix> for {', '.join(missing)}")
    if problems:
        raise WorkflowError(
            "config.yaml lists identifier prefixes that no Snakemake rule produces an ids file for:\n"
            + "\n".join(problems)
            + "\nEither add a rule that writes each of these files or remove the prefix from config.yaml."
        )
