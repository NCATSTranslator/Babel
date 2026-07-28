import src.createcompendia.transcript as transcript
import src.assess_compendia as assessments
import src.snakefiles.util as util


rule transcript_ensembl_ids:
    input:
        infile=config["download_directory"] + "/NCBIGene/gene2ensembl.gz",
    output:
        outfile=config["intermediate_directory"] + "/transcript/ids/ENSEMBL",
    benchmark:
        config["output_directory"] + "/benchmarks/transcript_ensembl_ids.tsv"
    run:
        transcript.write_transcript_ids(input.infile, output.outfile)


rule get_transcript_ensembl_relationships:
    input:
        infile=config["download_directory"] + "/NCBIGene/gene2ensembl.gz",
    output:
        outfile=config["intermediate_directory"] + "/transcript/concords/ENSEMBL",
        metadata_yaml=config["intermediate_directory"] + "/transcript/concords/metadata-ENSEMBL.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/get_transcript_ensembl_relationships.tsv"
    run:
        transcript.build_transcript_ensembl_relationships(input.infile, output.outfile, output.metadata_yaml)


rule transcript_compendia:
    input:
        concords=expand(
            "{dd}/transcript/concords/{ap}", dd=config["intermediate_directory"], ap=config["transcript_concords"]
        ),
        metadata_yamls=expand(
            "{dd}/transcript/concords/metadata-{ap}.yaml",
            dd=config["intermediate_directory"],
            ap=config["transcript_concords"],
        ),
        idlists=expand("{dd}/transcript/ids/{ap}", dd=config["intermediate_directory"], ap=config["transcript_ids"]),
        icrdf_filename=config["download_directory"] + "/icRDF.tsv",
    output:
        expand("{od}/compendia/{ap}", od=config["output_directory"], ap=config["transcript_outputs"]),
        temp(expand("{od}/synonyms/{ap}", od=config["output_directory"], ap=config["transcript_outputs"])),
        output_metadata=expand(
            "{od}/metadata/{ap}.yaml", od=config["output_directory"], ap=config["transcript_outputs"]
        ),
    benchmark:
        config["output_directory"] + "/benchmarks/transcript_compendia.tsv"
    run:
        transcript.build_compendia(input.concords, input.metadata_yamls, input.idlists, input.icrdf_filename)


rule check_transcript_completeness:
    input:
        input_compendia=expand("{od}/compendia/{ap}", od=config["output_directory"], ap=config["transcript_outputs"]),
    output:
        report_file=config["output_directory"] + "/reports/transcript_completeness.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/check_transcript_completeness.tsv"
    run:
        assessments.assess_completeness(
            config["intermediate_directory"] + "/transcript/ids", input.input_compendia, output.report_file
        )


rule check_transcript:
    input:
        infile=config["output_directory"] + "/compendia/Transcript.txt",
    output:
        outfile=config["output_directory"] + "/reports/Transcript.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/check_transcript.tsv"
    run:
        assessments.assess(input.infile, output.outfile)


rule transcript:
    input:
        config["output_directory"] + "/reports/transcript_completeness.txt",
        synonyms=expand("{od}/synonyms/{ap}", od=config["output_directory"], ap=config["transcript_outputs"]),
        reports=expand("{od}/reports/{ap}", od=config["output_directory"], ap=config["transcript_outputs"]),
    output:
        synonyms_gzipped=expand("{od}/synonyms/{ap}.gz", od=config["output_directory"], ap=config["transcript_outputs"]),
        x=config["output_directory"] + "/reports/transcript_done",
    benchmark:
        config["output_directory"] + "/benchmarks/transcript.tsv"
    run:
        util.gzip_files(input.synonyms)
        util.write_done(output.x)
