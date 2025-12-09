import src.reports.duckdb_reports
from src.snakefiles.util import get_all_compendia, get_all_synonyms_with_drugchemicalconflated
import src.exporters.duckdb_exporters as duckdb_exporters
import os

### Write all compendia, synonym and conflation files into DuckDB databases.


# Write all compendia files to DuckDB and Parquet, then create `babel_outputs/duckdb/compendia_done` to signal that we're done.
rule export_all_compendia_to_duckdb:
    input:
        compendium_duckdb_files=expand(
            "{od}/duckdb/duckdbs/filename={fn}/compendium.duckdb",
            od=config["output_directory"],
            fn=map(lambda fn: os.path.splitext(fn)[0], get_all_compendia(config)),
        ),
    output:
        x=config["output_directory"] + "/duckdb/compendia_done",
    shell:
        "echo 'done' >> {output.x}"


# Generic rule for generating the Parquet files for a particular compendia file.
rule export_compendia_to_duckdb:
    resources:
        runtime="6h",
        mem="512G",
    input:
        compendium_file=config["output_directory"] + "/compendia/{filename}.txt",
    output:
        duckdb_filename=config["output_directory"] + "/duckdb/duckdbs/filename={filename}/compendium.duckdb",
        node_parquet_file=config["output_directory"] + "/duckdb/parquet/filename={filename}/Node.parquet",
        clique_parquet_file=config["output_directory"] + "/duckdb/parquet/filename={filename}/Clique.parquet",
    run:
        print(f"Exporting {input.compendium_file} to {output.duckdb_filename}...")
        duckdb_exporters.export_compendia_to_parquet(input.compendium_file, output.clique_parquet_file, output.duckdb_filename)


# Write all synonyms files to Parquet via DuckDB, then create `babel_outputs/duckdb/synonyms_done` to signal that we're done.
rule export_all_synonyms_to_duckdb:
    input:
        synonyms_duckdb_files=expand(
            "{od}/duckdb/duckdbs/filename={fn}/synonyms.duckdb",
            od=config["output_directory"],
            fn=map(lambda fn: os.path.splitext(fn)[0], get_all_synonyms_with_drugchemicalconflated(config)),
        ),
    output:
        x=config["output_directory"] + "/duckdb/synonyms_done",
    shell:
        "echo 'done' >> {output.x}"


# Generic rule for generating the Parquet files for a particular compendia file.
rule export_synonyms_to_duckdb:
    input:
        synonyms_file=config["output_directory"] + "/synonyms/{filename}.txt.gz",
    output:
        duckdb_filename=config["output_directory"] + "/duckdb/duckdbs/filename={filename}/synonyms.duckdb",
        synonyms_parquet_filename=config["output_directory"] + "/duckdb/parquet/filename={filename}/Synonyms.parquet",
    run:
        duckdb_exporters.export_synonyms_to_parquet(input.synonyms_file, output.duckdb_filename, output.synonyms_parquet_filename)


# TODO: convert all conflations to Parquet via DuckDB (https://github.com/TranslatorSRI/Babel/issues/378).


# Create `babel_outputs/duckdb/done` once all the files have been converted.
rule export_all_to_duckdb:
    input:
        compendia_done=config["output_directory"] + "/duckdb/compendia_done",
        synonyms_done=config["output_directory"] + "/duckdb/synonyms_done",
    output:
        x=config["output_directory"] + "/duckdb/done",
    shell:
        "echo 'done' >> {output.x}"


# There are some reports we want to run on the Parquet files that have been generated.
rule check_for_identically_labeled_cliques:
    resources:
        mem="1500G",
    input:
        config["output_directory"] + "/duckdb/done",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/identically_labeled_clique.duckdb"),
        identically_labeled_cliques_tsv=config["output_directory"] + "/reports/duckdb/identically_labeled_cliques.tsv.gz",
    run:
        src.reports.duckdb_reports.check_for_identically_labeled_cliques(params.parquet_dir, output.duckdb_filename, output.identically_labeled_cliques_tsv, {
            'memory_limit': '512G',
            'threads': 2,
            'preserve_insertion_order': False,
        })


rule check_for_duplicate_curies:
    resources:
        mem="1500G",
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/duplicate_curies.duckdb"),
        duplicate_curies=config["output_directory"] + "/reports/duckdb/duplicate_curies.tsv",
    run:
        src.reports.duckdb_reports.check_for_duplicate_curies(params.parquet_dir, output.duckdb_filename, output.duplicate_curies, {
            'memory_limit': '1500G',
            'threads': 1,
            'preserve_insertion_order': False,
        })


rule check_for_duplicate_clique_leaders:
    resources:
        mem="1500G",
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/duplicate_clique_leaders.duckdb"),
        duplicate_clique_leaders_tsv=config["output_directory"] + "/reports/duckdb/duplicate_clique_leaders.tsv",
    run:
        src.reports.duckdb_reports.check_for_duplicate_clique_leaders(params.parquet_dir, output.duckdb_filename, output.duplicate_clique_leaders_tsv, {
            'memory_limit': '512G',
            'threads': 2,
            'preserve_insertion_order': False,
        })

rule generate_curie_report:
    resources:
        mem="1500G",
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/curie_report.duckdb"),
        curie_report_json=config["output_directory"] + "/reports/duckdb/curie_report.json",
    run:
        src.reports.duckdb_reports.generate_curie_report(params.parquet_dir, output.duckdb_filename, output.curie_report_json, {
            'memory_limit': '1500G',
            'threads': 1,
            'preserve_insertion_order': False,
        })

rule generate_by_clique_report:
    resources:
        mem="1500G",
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/by_clique_report.duckdb"),
        by_clique_report_json=config["output_directory"] + "/reports/duckdb/by_clique_report.json",
    run:
        src.reports.duckdb_reports.generate_by_clique_report(params.parquet_dir, output.duckdb_filename, output.by_clique_report_json, {
            'memory_limit': '1500G',
            'threads': 1,
            'preserve_insertion_order': False,
        })


rule all_duckdb_reports:
    input:
        config["output_directory"] + "/duckdb/done",
        identically_labeled_cliques_tsv=config["output_directory"] + "/reports/duckdb/identically_labeled_cliques.tsv.gz",
        duplicate_curies=config["output_directory"] + "/reports/duckdb/duplicate_curies.tsv",
        duplicate_clique_leaders_tsv=config["output_directory"] + "/reports/duckdb/duplicate_clique_leaders.tsv",
        curie_report_json=config["output_directory"] + "/reports/duckdb/curie_report.json",
        by_clique_report_json=config["output_directory"] + "/reports/duckdb/by_clique_report.json",
    output:
        x=config["output_directory"] + "/reports/duckdb/done",
    shell:
        "echo 'done' >> {output.x}"
