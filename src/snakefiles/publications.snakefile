import os

import src.createcompendia.publications as publications
import src.assess_compendia as assessments
from src.snakefiles import util


# Trivial done-marker rule runs locally so it doesn't consume a SLURM slot.
localrules:
    publications,


### PubMed


# The baseline/ and updatefiles/ directories are deliberately NOT declared as directory() outputs:
# Snakemake recursively deletes existing directory() outputs before running a job, which would wipe
# any PubMed files preloaded from a previous run. Keeping them undeclared lets wget --timestamping
# skip files we already have (see docs/RunningBabel.md, "Preloading PubMed downloads"). The done
# marker is what the downstream rules depend on.
rule download_pubmed:
    output:
        done_file=config["download_directory"] + "/PubMed/downloaded",
    benchmark:
        config["output_directory"] + "/benchmarks/download_pubmed.tsv"
    resources:
        mem="8G",
        cpus_per_task=1,
        # Two hours got ~50% through ~1500 files; parallelizing baseline+updatefiles should halve
        # that, so 6h is conservative. Tighten once benchmark TSVs give real-world data.
        runtime="6h",
    run:
        publications.download_pubmed(output.done_file)


rule verify_pubmed:
    input:
        config["download_directory"] + "/PubMed/downloaded",
    output:
        done_file=config["download_directory"] + "/PubMed/verified",
    benchmark:
        config["output_directory"] + "/benchmarks/verify_pubmed.tsv"
    run:
        publications.verify_pubmed_downloads(
            [
                config["download_directory"] + "/PubMed/baseline",
                config["download_directory"] + "/PubMed/updatefiles",
            ],
            output.done_file,
        )


rule generate_pubmed_concords:
    input:
        config["download_directory"] + "/PubMed/verified",
    output:
        titles_file=config["download_directory"] + "/PubMed/titles.tsv",
        status_file=config["download_directory"] + "/PubMed/statuses.jsonl.gz",
        pmid_id_file=config["intermediate_directory"] + "/publications/ids/PMID",
        pmid_doi_concord_file=config["intermediate_directory"] + "/publications/concords/PMID_DOI",
        metadata_yaml=config["intermediate_directory"] + "/publications/concords/metadata.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/generate_pubmed_concords.tsv"
    resources:
        runtime="24h",
        mem="128G",
    params:
        # Not inputs: see the comment on download_pubmed for why these directories are untracked.
        baseline_dir=config["download_directory"] + "/PubMed/baseline",
        updatefiles_dir=config["download_directory"] + "/PubMed/updatefiles",
    run:
        publications.parse_pubmed_into_tsvs(
            params.baseline_dir,
            params.updatefiles_dir,
            output.titles_file,
            output.status_file,
            output.pmid_id_file,
            output.pmid_doi_concord_file,
            output.metadata_yaml,
        )


rule generate_pubmed_compendia:
    input:
        pmid_id_file=config["intermediate_directory"] + "/publications/ids/PMID",
        pmid_doi_concord_file=config["intermediate_directory"] + "/publications/concords/PMID_DOI",
        titles=[
            config["download_directory"] + "/PubMed/titles.tsv",
        ],
        metadata_yaml=config["intermediate_directory"] + "/publications/concords/metadata.yaml",
        icrdf_filename=config["download_directory"] + "/icRDF.tsv",
    output:
        publication_compendium=config["output_directory"] + "/compendia/Publication.txt",
        # We generate an empty Publication Synonyms files, but we still need to generate one.
        publication_synonyms_gz=config["output_directory"] + "/synonyms/Publication.txt.gz",
        publication_metadata_yaml=config["output_directory"] + "/metadata/Publication.txt.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/generate_pubmed_compendia.tsv"
    resources:
        mem="128G",
    run:
        publications.generate_compendium(
            [input.pmid_doi_concord_file],
            [input.metadata_yaml],
            [input.pmid_id_file],
            input.titles,
            output.publication_compendium,
            input.icrdf_filename,
        )
        # generate_compendium() will generate an (empty) Publication.txt file, but we need
        # to compress it.
        publication_synonyms = os.path.splitext(output.publication_synonyms_gz)[0]
        util.gzip_files([publication_synonyms])
        os.remove(publication_synonyms)


rule check_publications_completeness:
    input:
        input_compendia=expand("{od}/compendia/{ap}", od=config["output_directory"], ap=config["publication_outputs"]),
    output:
        report_file=config["output_directory"] + "/reports/publication_completeness.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/check_publications_completeness.tsv"
    run:
        assessments.assess_completeness(
            config["intermediate_directory"] + "/publications/ids", input.input_compendia, output.report_file
        )


rule check_publications:
    input:
        infile=config["output_directory"] + "/compendia/Publication.txt",
    output:
        outfile=config["output_directory"] + "/reports/Publication.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/check_publications.tsv"
    run:
        assessments.assess(input.infile, output.outfile)


rule publications:
    input:
        config["output_directory"] + "/reports/publication_completeness.txt",
        synonyms=expand("{od}/synonyms/{ap}.gz", od=config["output_directory"], ap=config["publication_outputs"]),
        reports=expand("{od}/reports/{ap}", od=config["output_directory"], ap=config["publication_outputs"]),
    output:
        x=config["output_directory"] + "/reports/publications_done",
    shell:
        "echo 'done' >> {output.x}"
