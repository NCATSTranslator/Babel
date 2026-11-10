import src.createcompendia.chemicalparent as chemicalparent
from src.createcompendia.drugchemical import chemical_conflation_prefix_sort_order
import src.snakefiles.util as util

### ChemicalParent: chemical cliques that differ only in charge state (issue #1173)


# Trivial done-marker rule runs locally so it doesn't consume a SLURM slot.
localrules:
    chemicalparent,


rule chemicalparent_conflation:
    input:
        chemical_compendia=expand("{do}/compendia/{co}", do=config["output_directory"], co=config["chemical_outputs"]),
    output:
        outfile=config["output_directory"] + "/conflation/ChemicalParent.txt",
        metadata_yaml=config["output_directory"] + "/metadata/ChemicalParent.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/chemicalparent_conflation.tsv"
    resources:
        # Pass 1 holds one 8-byte hash per InChIKey clique (116M on 2025dec11: ~1 GB, twice that while sorting);
        # pass 2 holds only the ~2.7M cliques that group. Not yet benchmarked on the cluster.
        mem="16G",
    run:
        chemicalparent.build_conflation(
            input.chemical_compendia,
            chemical_conflation_prefix_sort_order(config["biolink_version"]),
            output.outfile,
            output.metadata_yaml,
        )


rule chemicalparent:
    input:
        config["output_directory"] + "/conflation/ChemicalParent.txt",
    output:
        done=config["output_directory"] + "/reports/chemicalparent_done",
    run:
        util.write_done(output.done)
