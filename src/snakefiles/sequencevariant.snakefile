import src.createcompendia.sequencevariant as sequencevariant
import src.datahandlers.clinvar as clinvar
import src.assess_compendia as assessments
import src.snakefiles.util as util


rule clinvar_labels:
    input:
        infile=config["download_directory"] + "/CLINVAR/variant_summary.txt",
    output:
        labels=config["download_directory"] + "/CLINVAR/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/clinvar_labels.tsv"
    run:
        clinvar.write_clinvar_labels(input.infile, output.labels)


rule clinvar_ids:
    input:
        infile=config["download_directory"] + "/CLINVAR/variant_summary.txt",
    output:
        outfile=config["intermediate_directory"] + "/sequencevariant/ids/CLINVAR",
    benchmark:
        config["output_directory"] + "/benchmarks/clinvar_ids.tsv"
    run:
        clinvar.write_clinvar_ids(input.infile, output.outfile)


rule get_clinvar_dbsnp_relationships:
    input:
        infile=config["download_directory"] + "/CLINVAR/variant_summary.txt",
    output:
        outfile=config["intermediate_directory"] + "/sequencevariant/concords/CLINVAR",
        metadata_yaml=config["intermediate_directory"] + "/sequencevariant/concords/metadata-CLINVAR.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/get_clinvar_dbsnp_relationships.tsv"
    run:
        clinvar.build_clinvar_dbsnp_relationships(input.infile, output.outfile, output.metadata_yaml)


rule sequencevariant_compendia:
    input:
        labels=expand("{dd}/{ap}/labels", dd=config["download_directory"], ap=config["sequencevariant_labels"]),
        concords=expand(
            "{dd}/sequencevariant/concords/{ap}",
            dd=config["intermediate_directory"],
            ap=config["sequencevariant_concords"],
        ),
        metadata_yamls=expand(
            "{dd}/sequencevariant/concords/metadata-{ap}.yaml",
            dd=config["intermediate_directory"],
            ap=config["sequencevariant_concords"],
        ),
        idlists=expand(
            "{dd}/sequencevariant/ids/{ap}", dd=config["intermediate_directory"], ap=config["sequencevariant_ids"]
        ),
        icrdf_filename=config["download_directory"] + "/icRDF.tsv",
    output:
        expand("{od}/compendia/{ap}", od=config["output_directory"], ap=config["sequencevariant_outputs"]),
        temp(expand("{od}/synonyms/{ap}", od=config["output_directory"], ap=config["sequencevariant_outputs"])),
        output_metadata=expand(
            "{od}/metadata/{ap}.yaml", od=config["output_directory"], ap=config["sequencevariant_outputs"]
        ),
    benchmark:
        config["output_directory"] + "/benchmarks/sequencevariant_compendia.tsv"
    run:
        sequencevariant.build_compendia(input.concords, input.metadata_yamls, input.idlists, input.icrdf_filename)


rule check_sequencevariant_completeness:
    input:
        input_compendia=expand(
            "{od}/compendia/{ap}", od=config["output_directory"], ap=config["sequencevariant_outputs"]
        ),
    output:
        report_file=config["output_directory"] + "/reports/sequencevariant_completeness.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/check_sequencevariant_completeness.tsv"
    run:
        assessments.assess_completeness(
            config["intermediate_directory"] + "/sequencevariant/ids", input.input_compendia, output.report_file
        )


rule check_sequencevariant:
    input:
        infile=config["output_directory"] + "/compendia/SequenceVariant.txt",
    output:
        outfile=config["output_directory"] + "/reports/SequenceVariant.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/check_sequencevariant.tsv"
    run:
        assessments.assess(input.infile, output.outfile)


rule sequencevariant:
    input:
        config["output_directory"] + "/reports/sequencevariant_completeness.txt",
        synonyms=expand("{od}/synonyms/{ap}", od=config["output_directory"], ap=config["sequencevariant_outputs"]),
        reports=expand("{od}/reports/{ap}", od=config["output_directory"], ap=config["sequencevariant_outputs"]),
    output:
        synonyms_gzipped=expand(
            "{od}/synonyms/{ap}.gz", od=config["output_directory"], ap=config["sequencevariant_outputs"]
        ),
        x=config["output_directory"] + "/reports/sequencevariant_done",
    benchmark:
        config["output_directory"] + "/benchmarks/sequencevariant.tsv"
    run:
        util.gzip_files(input.synonyms)
        util.write_done(output.x)
