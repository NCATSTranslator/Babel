from src.snakefiles.util import get_all_compendia, get_sapbert_training_synonyms
import src.exporters.kgx as kgx
import src.exporters.sapbert as sapbert
import os

### Export compendia/synonyms into downstream outputs


# Trivial aggregation rules run locally so they don't consume a SLURM slot.
localrules:
    export_all_to_kgx,
    export_all_to_sapbert_training,


# Export all compendia to KGX, then create `babel_outputs/kgx/done` to signal that we're done.
rule export_all_to_kgx:
    input:
        nodes_files=expand(
            "{od}/kgx/{fn}",
            od=config["output_directory"],
            fn=map(lambda fn: os.path.splitext(fn)[0] + "_nodes.jsonl.gz", get_all_compendia(config)),
        ),
        edges_files=expand(
            "{od}/kgx/{fn}",
            od=config["output_directory"],
            fn=map(lambda fn: os.path.splitext(fn)[0] + "_edges.jsonl.gz", get_all_compendia(config)),
        ),
    output:
        x=config["output_directory"] + "/kgx/done",
    shell:
        "echo 'done' >> {output.x}"


# Generic rule for generating the KGX files for a particular compendia file.
rule generate_kgx:
    input:
        compendium_file=config["output_directory"] + "/compendia/{filename}.txt",
    output:
        nodes_file=config["output_directory"] + "/kgx/{filename}_nodes.jsonl.gz",
        edges_file=config["output_directory"] + "/kgx/{filename}_edges.jsonl.gz",
    benchmark:
        config["output_directory"] + "/benchmarks/generate_kgx_{filename}.tsv"
    resources:
        # Slowest of the 25 wildcard instances on 2026jul22 was SmallMolecule at 2.7h.
        runtime="4h",
    run:
        kgx.convert_compendium_to_kgx(input.compendium_file, output.nodes_file, output.edges_file)


# Export the synonym files to SAPBERT export, then create `babel_outputs/sapbert-training-data/done` to signal that we're done.
# config.yaml's sapbert_excluded_synonym_outputs leaves GeneProteinConflated out.
rule export_all_to_sapbert_training:
    input:
        sapbert_training_file=expand(
            "{od}/sapbert-training-data/{fn}.gz",
            od=config["output_directory"],
            fn=get_sapbert_training_synonyms(config),
        ),
    output:
        x=config["output_directory"] + "/sapbert-training-data/done",
    shell:
        "echo 'done' >> {output.x}"


# Generic rule for generating the SAPBERT training file for a particular synonym file.
rule generate_sapbert_training_data:
    input:
        synonym_file_gz=config["output_directory"] + "/synonyms/{filename}.gz",
    output:
        sapbert_training_data_file=config["output_directory"] + "/sapbert-training-data/{filename}.gz",
    benchmark:
        config["output_directory"] + "/benchmarks/generate_sapbert_training_data_{filename}.tsv"
    resources:
        # Sized on 2026jul22, when GeneProteinConflated was still exported and was the slowest of the
        # 18 wildcard instances at 1.9h. Of the 17 exported now, the slowest then was
        # DrugChemicalConflated at 1.6h.
        runtime="3h",
        # The exporter remembers a digest of every synonym pair it writes so it can skip duplicates,
        # so memory grows with the size of the output. This estimate was made for GeneProteinConflated,
        # the largest output at roughly 300M pairs x ~95 bytes per set entry, which is no longer
        # exported, so it is generous for the files that are. Recheck against the benchmark TSVs
        # after the first run that includes the deduplication (see docs/tools/Resources.md).
        mem="64G",
    run:
        sapbert.convert_synonyms_to_sapbert(input.synonym_file_gz, output.sapbert_training_data_file)
