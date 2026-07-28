import src.createcompendia.clinicalfinding as clinicalfinding
import src.datahandlers.loinc as loinc
import src.assess_compendia as assessments
import src.snakefiles.util as util


rule loinc_labels:
    input:
        infile=config["download_directory"] + "/LOINC/loinc.csv",
    output:
        labels=config["download_directory"] + "/LOINC/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/loinc_labels.tsv"
    run:
        loinc.write_loinc_labels(input.infile, output.labels)


rule loinc_ids:
    input:
        infile=config["download_directory"] + "/LOINC/loinc.csv",
    output:
        outfile=config["intermediate_directory"] + "/clinicalfinding/ids/LOINC",
    benchmark:
        config["output_directory"] + "/benchmarks/loinc_ids.tsv"
    run:
        loinc.write_loinc_ids(input.infile, output.outfile)


rule clinicalfinding_compendia:
    input:
        labels=expand("{dd}/{ap}/labels", dd=config["download_directory"], ap=config["clinicalfinding_labels"]),
        idlists=expand(
            "{dd}/clinicalfinding/ids/{ap}", dd=config["intermediate_directory"], ap=config["clinicalfinding_ids"]
        ),
        icrdf_filename=config["download_directory"] + "/icRDF.tsv",
    output:
        expand("{od}/compendia/{ap}", od=config["output_directory"], ap=config["clinicalfinding_outputs"]),
        temp(expand("{od}/synonyms/{ap}", od=config["output_directory"], ap=config["clinicalfinding_outputs"])),
        output_metadata=expand(
            "{od}/metadata/{ap}.yaml", od=config["output_directory"], ap=config["clinicalfinding_outputs"]
        ),
    benchmark:
        config["output_directory"] + "/benchmarks/clinicalfinding_compendia.tsv"
    run:
        # LOINC has no concords in v1, so the concord/metadata lists are empty (singleton cliques).
        clinicalfinding.build_compendia([], [], input.idlists, input.icrdf_filename)


rule check_clinicalfinding_completeness:
    input:
        input_compendia=expand(
            "{od}/compendia/{ap}", od=config["output_directory"], ap=config["clinicalfinding_outputs"]
        ),
    output:
        report_file=config["output_directory"] + "/reports/clinicalfinding_completeness.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/check_clinicalfinding_completeness.tsv"
    run:
        assessments.assess_completeness(
            config["intermediate_directory"] + "/clinicalfinding/ids", input.input_compendia, output.report_file
        )


rule check_clinicalfinding:
    input:
        infile=config["output_directory"] + "/compendia/ClinicalFinding.txt",
    output:
        outfile=config["output_directory"] + "/reports/ClinicalFinding.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/check_clinicalfinding.tsv"
    run:
        assessments.assess(input.infile, output.outfile)


rule clinicalfinding:
    input:
        config["output_directory"] + "/reports/clinicalfinding_completeness.txt",
        synonyms=expand("{od}/synonyms/{ap}", od=config["output_directory"], ap=config["clinicalfinding_outputs"]),
        reports=expand("{od}/reports/{ap}", od=config["output_directory"], ap=config["clinicalfinding_outputs"]),
    output:
        synonyms_gzipped=expand(
            "{od}/synonyms/{ap}.gz", od=config["output_directory"], ap=config["clinicalfinding_outputs"]
        ),
        x=config["output_directory"] + "/reports/clinicalfinding_done",
    benchmark:
        config["output_directory"] + "/benchmarks/clinicalfinding.tsv"
    run:
        util.gzip_files(input.synonyms)
        util.write_done(output.x)
