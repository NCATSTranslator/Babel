from src.createcompendia.manual import build_manual, write_manual_labels_and_synonyms
import src.snakefiles.util as util


rule manual_labels_synonyms:
    input:
        terms="input_data/manual_terms.ndjson",
    output:
        labels=expand("{dd}/{prefix}/labels", dd=config["download_directory"], prefix=config["manual_prefixes"]),
        synonyms=expand("{dd}/{prefix}/synonyms", dd=config["download_directory"], prefix=config["manual_prefixes"]),
    benchmark:
        config["output_directory"] + "/benchmarks/manual_labels_synonyms.tsv"
    run:
        write_manual_labels_and_synonyms(input.terms, config["download_directory"], config["manual_prefixes"])


rule manual_compendia:
    input:
        terms="input_data/manual_terms.ndjson",
        labels=expand("{dd}/{prefix}/labels", dd=config["download_directory"], prefix=config["manual_prefixes"]),
        synonyms=expand("{dd}/{prefix}/synonyms", dd=config["download_directory"], prefix=config["manual_prefixes"]),
        icrdf_filename=config["download_directory"] + "/icRDF.tsv",
    output:
        config["output_directory"] + "/compendia/Manual.txt",
        temp(config["output_directory"] + "/synonyms/Manual.txt"),
        output_metadata_yaml=config["output_directory"] + "/metadata/Manual.txt.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/manual_compendia.tsv"
    run:
        build_manual([], input.icrdf_filename, input.terms)


rule manual:
    input:
        synonym=config["output_directory"] + "/synonyms/Manual.txt",
        output_metadata_yaml=config["output_directory"] + "/metadata/Manual.txt.yaml",
    output:
        synonym_gzipped=config["output_directory"] + "/synonyms/Manual.txt.gz",
        x=config["output_directory"] + "/reports/manual_done",
    benchmark:
        config["output_directory"] + "/benchmarks/manual.tsv"
    run:
        util.gzip_files([input.synonym])
        util.write_done(output.x)
