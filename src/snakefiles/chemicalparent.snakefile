import src.createcompendia.chemicalparent as chemicalparent
import src.createcompendia.inchi_components as inchi_components
from src.createcompendia.drugchemical import chemical_conflation_prefix_sort_order
from src.metadata.provenance import write_metadata
import src.snakefiles.util as util

### ChemicalParent: chemical cliques that are one parent compound in different forms (issue #1173)


# Trivial done-marker rule runs locally so it doesn't consume a SLURM slot.
localrules:
    chemicalparent,


# Split every multi-component InChI in PubChem into its components with RDKit. Doesn't depend on any compendium,
# so it runs alongside the compendium builds.
rule chemicalparent_inchi_components:
    input:
        pubchem_inchi=config["download_directory"] + "/PUBCHEM.COMPOUND/CID-InChI-Key.gz",
    output:
        components=config["intermediate_directory"] + "/chemicalparent/inchi_components.tsv",
        metadata_yaml=config["intermediate_directory"] + "/chemicalparent/metadata-inchi_components.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/chemicalparent_inchi_components.tsv"
    # 11.8M multi-component InChIs at ~0.5 ms each is ~1.6 CPU-hours (2026-11-10); 16 processes keep it near ten
    # minutes. threads and cpus_per_task must match or SLURM gives the rule one CPU (see AGENTS.md).
    threads: 16
    resources:
        cpus_per_task=16,
        # Each worker holds a few thousand InChIs; a worker stuck on an InChI RDKit can't parse grows to ~1 GB
        # before write_inchi_components() kills it, so 16 such at once is the worst case.
        mem="32G",
        runtime="4h",
    run:
        counts = inchi_components.write_inchi_components(input.pubchem_inchi, output.components, threads)
        write_metadata(
            output.metadata_yaml,
            typ="transform",
            name="inchi_components.write_inchi_components()",
            description="Split each multi-component InChI in PubChem's CID-InChI-Key.gz into its components "
            "with RDKit.",
            sources=[{"type": "download", "name": "PubChem CID-InChI-Key", "filenames": [input.pubchem_inchi]}],
            counts=counts,
        )


# Apply the reviewed counterion/solvent list: InChIKey -> parent key for every salt or hydrate it resolves.
rule chemicalparent_salt_parents:
    input:
        components=config["intermediate_directory"] + "/chemicalparent/inchi_components.tsv",
        decisions=config["input_directory"] + "/chemical_parent_components.tsv",
    output:
        salt_parents=config["intermediate_directory"] + "/chemicalparent/salt_parents.tsv",
        metadata_yaml=config["intermediate_directory"] + "/chemicalparent/metadata-salt_parents.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/chemicalparent_salt_parents.tsv"
    run:
        counts = inchi_components.write_salt_parents(input.components, input.decisions, output.salt_parents)
        write_metadata(
            output.metadata_yaml,
            typ="transform",
            name="inchi_components.write_salt_parents()",
            description="Map each salt or hydrate to its parent component's parent key, dropping the reviewed "
            "counterions and solvents.",
            sources=[
                {"type": "Babel", "name": "InChI components", "filenames": [input.components]},
                {"type": "manual", "name": "Reviewed component list", "filenames": [input.decisions]},
            ],
            counts=counts,
        )


rule chemicalparent_conflation:
    input:
        chemical_compendia=expand("{do}/compendia/{co}", do=config["output_directory"], co=config["chemical_outputs"]),
        salt_parents=config["intermediate_directory"] + "/chemicalparent/salt_parents.tsv",
    output:
        outfile=config["output_directory"] + "/conflation/ChemicalParent.txt",
        metadata_yaml=config["output_directory"] + "/metadata/ChemicalParent.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/chemicalparent_conflation.tsv"
    resources:
        # Pass 1 holds one 8-byte hash per InChIKey clique (116M on 2025dec11: ~1 GB, twice that while sorting);
        # the salt-parents map holds 4.8M keys (~1 GB); pass 2 holds only the cliques that group. Not yet
        # benchmarked on the cluster.
        mem="16G",
    run:
        chemicalparent.build_conflation(
            input.chemical_compendia,
            input.salt_parents,
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
