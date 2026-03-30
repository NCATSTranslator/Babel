import src.node as node
import src.datahandlers.mesh as mesh
import src.datahandlers.clo as clo
import src.datahandlers.obo as obo
import src.datahandlers.umls as umls
import src.datahandlers.ncbigene as ncbigene
import src.datahandlers.efo as efo
import src.datahandlers.ensembl as ensembl
import src.datahandlers.hgnc as hgnc
import src.datahandlers.omim as omim
import src.datahandlers.uniprotkb as uniprotkb
import src.datahandlers.mods as mods
import src.datahandlers.ncit as ncit
import src.datahandlers.doid as doid
import src.datahandlers.orphanet as orphanet
import src.datahandlers.reactome as reactome
import src.datahandlers.rhea as rhea
import src.datahandlers.ec as ec
import src.datahandlers.smpdb as smpdb
import src.datahandlers.pantherpathways as pantherpathways
import src.datahandlers.unichem as unichem
import src.datahandlers.chembl as chembl
import src.datahandlers.gtopdb as gtopdb
import src.datahandlers.kegg as kegg
import src.datahandlers.unii as unii
import src.datahandlers.hmdb as hmdb
import src.datahandlers.pubchem as pubchem
import src.datahandlers.drugcentral as drugcentral
import src.datahandlers.ncbitaxon as ncbitaxon
import src.datahandlers.chebi as chebi
import src.datahandlers.hgncfamily as hgncfamily
import src.datahandlers.pantherfamily as pantherfamily
import src.datahandlers.complexportal as complexportal
import src.datahandlers.drugbank as drugbank
from src.babel_utils import pull_via_wget


# No-op placeholder rules run locally and don't need a SLURM slot.
localrules:
    get_mesh_synonyms,


#####
#
# Data sets: pull data sets, and parse them to get labels and synonyms
#
####

### EFO


rule get_EFO:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/EFO" + "/efo.owl",
    benchmark:
        config["output_directory"] + "/benchmarks/get_EFO.tsv"
    run:
        efo.pull_efo()


rule get_EFO_labels:
    input:
        owlfile=config["download_directory"] + "/EFO/efo.owl",
    output:
        labelfile=config["download_directory"] + "/EFO/labels",
        synonymfile=config["download_directory"] + "/EFO/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/get_EFO_labels.tsv"
    run:
        efo.make_labels(input.owlfile, output.labelfile, output.synonymfile)


### Complex Portal
# https://www.ebi.ac.uk/complexportal/


rule get_complexportal:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/ComplexPortal" + "/559292.tsv",
    benchmark:
        config["output_directory"] + "/benchmarks/get_complexportal.tsv"
    run:
        complexportal.pull_complexportal()


rule get_complexportal_labels_and_synonyms:
    input:
        infile=config["download_directory"] + "/ComplexPortal" + "/559292.tsv",
    output:
        lfile=config["download_directory"] + "/ComplexPortal" + "/559292_labels.tsv",
        sfile=config["download_directory"] + "/ComplexPortal" + "/559292_synonyms.tsv",
        metadata_yaml=config["download_directory"] + "/ComplexPortal/metadata.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/get_complexportal_labels_and_synonyms.tsv"
    run:
        complexportal.make_labels_and_synonyms(input.infile, output.lfile, output.sfile, output.metadata_yaml)


### MODS


rule get_mods:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        expand(
            "{download_directory}/{mod}/GENE-DESCRIPTION-JSON_{mod}.json",
            download_directory=config["download_directory"],
            mod=config["mods"],
        ),
    benchmark:
        config["output_directory"] + "/benchmarks/get_mods.tsv"
    run:
        mods.pull_mods()


rule get_mods_labels:
    input:
        expand(
            "{download_directory}/{mod}/GENE-DESCRIPTION-JSON_{mod}.json",
            download_directory=config["download_directory"],
            mod=config["mods"],
        ),
    output:
        expand("{download_directory}/{mod}/labels", download_directory=config["download_directory"], mod=config["mods"]),
    benchmark:
        config["output_directory"] + "/benchmarks/get_mods_labels.tsv"
    run:
        mods.write_labels(config["download_directory"])


### UniProtKB


rule get_uniprotkb_idmapping:
    resources:
        mem="8G",
        cpus_per_task=1,
        runtime="6h",
    output:
        idmapping=config["download_directory"] + "/UniProtKB/idmapping.dat",
    benchmark:
        config["output_directory"] + "/benchmarks/get_uniprotkb_idmapping.tsv"
    run:
        pull_via_wget(
            "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/idmapping/",
            "idmapping.dat.gz",
            decompress=True,
            subpath="UniProtKB",
        )


rule get_uniprotkb_sprot:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        uniprot_sprot=config["download_directory"] + "/UniProtKB/uniprot_sprot.fasta",
    benchmark:
        config["output_directory"] + "/benchmarks/get_uniprotkb_sprot.tsv"
    run:
        pull_via_wget(
            "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/",
            "uniprot_sprot.fasta.gz",
            decompress=True,
            subpath="UniProtKB",
        )


rule get_uniprotkb_trembl:
    resources:
        mem="8G",
        cpus_per_task=1,
        runtime="6h",
    output:
        uniprot_trembl=config["download_directory"] + "/UniProtKB/uniprot_trembl.fasta",
    benchmark:
        config["output_directory"] + "/benchmarks/get_uniprotkb_trembl.tsv"
    run:
        pull_via_wget(
            "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/",
            "uniprot_trembl.fasta.gz",
            decompress=True,
            subpath="UniProtKB",
        )


rule get_uniprotkb_labels:
    input:
        sprot_input=config["download_directory"] + "/UniProtKB/uniprot_sprot.fasta",
        trembl_input=config["download_directory"] + "/UniProtKB/uniprot_trembl.fasta",
    output:
        outfile=config["download_directory"] + "/UniProtKB/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/get_uniprotkb_labels.tsv"
    run:
        uniprotkb.pull_uniprot_labels(input.sprot_input, input.trembl_input, output.outfile)


### MESH


rule get_mesh:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/MESH/mesh.nt",
    benchmark:
        config["output_directory"] + "/benchmarks/get_mesh.tsv"
    run:
        mesh.pull_mesh()


rule get_mesh_labels:
    input:
        config["download_directory"] + "/MESH/mesh.nt",
    output:
        config["download_directory"] + "/MESH/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/get_mesh_labels.tsv"
    run:
        mesh.pull_mesh_labels()


rule get_mesh_synonyms:
    # We don't actually get any.  Maybe we could from the nt?
    output:
        ofn=config["download_directory"] + "/MESH/synonyms",
    shell:
        "touch {output.ofn}"


### UMLS / SNOMEDCT


rule download_umls:
    resources:
        mem="8G",
        cpus_per_task=1,
        runtime="6h",
    output:
        config["download_directory"] + "/UMLS/MRCONSO.RRF",
        config["download_directory"] + "/UMLS/MRSTY.RRF",
        config["download_directory"] + "/UMLS/MRREL.RRF",
    benchmark:
        config["output_directory"] + "/benchmarks/download_umls.tsv"
    run:
        umls.download_umls(config["umls_version"], config["umls"]["subset"], config["download_directory"] + "/UMLS")


rule get_umls_labels_and_synonyms:
    input:
        mrconso=config["download_directory"] + "/UMLS/MRCONSO.RRF",
    output:
        config["download_directory"] + "/UMLS/labels",
        config["download_directory"] + "/UMLS/synonyms",
        config["download_directory"] + "/SNOMEDCT/labels",
        config["download_directory"] + "/SNOMEDCT/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/get_umls_labels_and_synonyms.tsv"
    run:
        umls.pull_umls(input.mrconso)


### OBO Ontologies


rule get_obo_labels:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        obo_labels=config["download_directory"] + "/common/ubergraph/labels",
        # A bunch of files depend on UberGraph labels being created in prefix directories (e.g. babel_downloads/GO/labels),
        # but these are now only included in the common labels file (i.e. babel_downloads/common/ubergraph/labels).
        # However, since they are needed to make Snakemake work, we'll generate these here.
        generated_labels=expand(
            "{download_directory}/{prefix}/labels",
            download_directory=config["download_directory"],
            prefix=config["generate_dirs_for_labels_and_synonyms_prefixes"],
        ),
    retries: 10  # Ubergraph sometimes fails mid-download, and then we need to retry.
    benchmark:
        config["output_directory"] + "/benchmarks/get_obo_labels.tsv"
    run:
        obo.pull_uber_labels(output.obo_labels, output.generated_labels)


rule get_obo_synonyms:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        obo_synonyms=config["download_directory"] + "/common/ubergraph/synonyms.jsonl",
        # A bunch of files depend on UberGraph labels being created in prefix directories (e.g. babel_downloads/GO/labels),
        # but these are now only included in the common labels file (i.e. babel_downloads/common/ubergraph/labels).
        # However, since they are needed to make Snakemake work, we'll generate these here.
        generated_synonyms=expand(
            "{download_directory}/{prefix}/synonyms",
            download_directory=config["download_directory"],
            prefix=config["generate_dirs_for_labels_and_synonyms_prefixes"],
        ),
    retries: 10  # Ubergraph sometimes fails mid-download, and then we need to retry.
    benchmark:
        config["output_directory"] + "/benchmarks/get_obo_synonyms.tsv"
    run:
        obo.pull_uber_synonyms(output.obo_synonyms, output.generated_synonyms)


rule get_obo_descriptions:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        obo_descriptions=config["download_directory"] + "/common/ubergraph/descriptions.jsonl",
    retries: 10  # Ubergraph sometimes fails mid-download, and then we need to retry.
    benchmark:
        config["output_directory"] + "/benchmarks/get_obo_descriptions.tsv"
    run:
        obo.pull_uber_descriptions(output.obo_descriptions)


rule get_icrdf:
    input:
        # Ideally, we would correctly mark all the dependencies for Ubergraph labels, synonyms and descriptions
        # throughout the system, but that would require a bunch of rewriting. Luckily, we already have the icRDF file
        # marked as required for all compendia, so we just need to make sure that OBO/Ubergraph has been downloaded
        # before the icRDF file is downloaded.
        config["download_directory"] + "/common/ubergraph/labels",
        config["download_directory"] + "/common/ubergraph/synonyms.jsonl",
        config["download_directory"] + "/common/ubergraph/descriptions.jsonl",
    output:
        icrdf_filename=config["download_directory"] + "/icRDF.tsv",
    retries: 10  # Ubergraph sometimes fails mid-download, and then we need to retry.
    benchmark:
        config["output_directory"] + "/benchmarks/get_icrdf.tsv"
    run:
        obo.pull_uber_icRDF(output.icrdf_filename)

        # Try to load the icRDF.tsv file (this will produce an error if the file can't be read).
        node.InformationContentFactory(output.icrdf_filename)


### NCBIGene


rule get_ncbigene:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        getfiles=expand(
            "{download_directory}/NCBIGene/{ncbi_files}",
            download_directory=config["download_directory"],
            ncbi_files=config["ncbi_files"],
        ),
    benchmark:
        config["output_directory"] + "/benchmarks/get_ncbigene.tsv"
    run:
        ncbigene.pull_ncbigene(config["ncbi_files"])


rule get_ncbigene_labels_synonyms_and_taxa:
    input:
        gene_info_filename=config["download_directory"] + "/NCBIGene/gene_info.gz",
    output:
        labels_filename=config["download_directory"] + "/NCBIGene/labels",
        synonyms_filename=config["download_directory"] + "/NCBIGene/synonyms",
        taxa_filename=config["download_directory"] + "/NCBIGene/taxa",
        descriptions_filename=config["download_directory"] + "/NCBIGene/descriptions",
    benchmark:
        config["output_directory"] + "/benchmarks/get_ncbigene_labels_synonyms_and_taxa.tsv"
    run:
        ncbigene.pull_ncbigene_labels_synonyms_and_taxa(
            input.gene_info_filename,
            output.labels_filename,
            output.synonyms_filename,
            output.taxa_filename,
            output.descriptions_filename,
        )


### ENSEMBL


rule get_ensembl:
    resources:
        mem="8G",
        cpus_per_task=1,
        runtime="6h",
    output:
        ensembl_dir=directory(config["download_directory"] + "/ENSEMBL"),
        complete_file=config["download_directory"] + "/ENSEMBL/BioMartDownloadComplete",
    benchmark:
        config["output_directory"] + "/benchmarks/get_ensembl.tsv"
    run:
        ensembl.pull_ensembl(output.ensembl_dir, output.complete_file)


### HGNC


rule get_hgnc:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/HGNC/hgnc_complete_set.json",
    benchmark:
        config["output_directory"] + "/benchmarks/get_hgnc.tsv"
    run:
        hgnc.pull_hgnc()


rule get_hgnc_labels_and_synonyms:
    output:
        config["download_directory"] + "/HGNC/labels",
        config["download_directory"] + "/HGNC/synonyms",
    input:
        infile=rules.get_hgnc.output.outfile,
    benchmark:
        config["output_directory"] + "/benchmarks/get_hgnc_labels_and_synonyms.tsv"
    run:
        hgnc.pull_hgnc_labels_and_synonyms(input.infile)


### HGNC.FAMILY


rule get_hgncfamily:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/HGNC.FAMILY/family.csv",
    benchmark:
        config["output_directory"] + "/benchmarks/get_hgncfamily.tsv"
    run:
        hgncfamily.pull_hgncfamily()


rule get_hgncfamily_labels:
    input:
        infile=config["download_directory"] + "/HGNC.FAMILY/family.csv",
    output:
        labelsfile=config["download_directory"] + "/HGNC.FAMILY/labels",
        descriptionsfile=config["download_directory"] + "/HGNC.FAMILY/descriptions",
        metadata_yaml=config["download_directory"] + "/HGNC.FAMILY/metadata.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/get_hgncfamily_labels.tsv"
    run:
        hgncfamily.pull_labels(input.infile, output.labelsfile, output.descriptionsfile, output.metadata_yaml)


### PANTHER.FAMILY


rule get_pantherfamily:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/PANTHER.FAMILY/family.csv",
    benchmark:
        config["output_directory"] + "/benchmarks/get_pantherfamily.tsv"
    run:
        pantherfamily.pull_pantherfamily()


rule get_pantherfamily_labels:
    input:
        infile=config["download_directory"] + "/PANTHER.FAMILY/family.csv",
    output:
        outfile=config["download_directory"] + "/PANTHER.FAMILY/labels",
        metadata_yaml=config["download_directory"] + "/PANTHER.FAMILY/metadata.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/get_pantherfamily_labels.tsv"
    run:
        pantherfamily.pull_labels(input.infile, output.outfile, output.metadata_yaml)


### OMIM


rule get_omim:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/OMIM/mim2gene.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/get_omim.tsv"
    run:
        omim.pull_omim()


### NCIT


rule get_ncit:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/NCIT/NCIt-SwissProt_Mapping.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/get_ncit.tsv"
    run:
        ncit.pull_ncit()


### DOID


rule get_doid:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/DOID/doid.json",
    benchmark:
        config["output_directory"] + "/benchmarks/get_doid.tsv"
    run:
        doid.pull_doid()


rule get_doid_labels_and_synonyms:
    input:
        infile=config["download_directory"] + "/DOID/doid.json",
    output:
        labelfile=config["download_directory"] + "/DOID/labels",
        synonymfile=config["download_directory"] + "/DOID/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/get_doid_labels_and_synonyms.tsv"
    run:
        doid.pull_doid_labels_and_synonyms(input.infile, output.labelfile, output.synonymfile)


### Orphanet


rule get_orphanet:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/Orphanet/Orphanet_Nomenclature_Pack_EN.zip",
    benchmark:
        config["output_directory"] + "/benchmarks/get_orphanet.tsv"
    run:
        orphanet.pull_orphanet()


rule get_orphanet_labels_and_synonyms:
    input:
        infile=config["download_directory"] + "/Orphanet/Orphanet_Nomenclature_Pack_EN.zip",
    output:
        labelfile=config["download_directory"] + "/Orphanet/labels",
        synonymfile=config["download_directory"] + "/Orphanet/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/get_orphanet_labels_and_synonyms.tsv"
    run:
        orphanet.pull_orphanet_labels_and_synonyms(input.infile, output.labelfile, output.synonymfile)


### Reactome


rule get_reactome:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/REACT/Events.json",
    benchmark:
        config["output_directory"] + "/benchmarks/get_reactome.tsv"
    run:
        reactome.pull_reactome(output.outfile)


rule get_reactome_labels:
    input:
        infile=config["download_directory"] + "/REACT/Events.json",
    output:
        labelfile=config["download_directory"] + "/REACT/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/get_reactome_labels.tsv"
    run:
        reactome.make_labels(input.infile, output.labelfile)


### RHEA


rule get_rhea:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/RHEA/rhea.rdf",
    benchmark:
        config["output_directory"] + "/benchmarks/get_rhea.tsv"
    run:
        rhea.pull_rhea()


rule get_rhea_labels:
    input:
        infile=config["download_directory"] + "/RHEA/rhea.rdf",
    output:
        labelfile=config["download_directory"] + "/RHEA/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/get_rhea_labels.tsv"
    run:
        rhea.make_labels(output.labelfile)


### EC


rule get_EC:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/EC/enzyme.rdf",
    benchmark:
        config["output_directory"] + "/benchmarks/get_EC.tsv"
    run:
        ec.pull_ec()


rule get_EC_labels:
    input:
        infile=config["download_directory"] + "/EC/enzyme.rdf",
    output:
        labelfile=config["download_directory"] + "/EC/labels",
        synonymfile=config["download_directory"] + "/EC/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/get_EC_labels.tsv"
    run:
        ec.make_labels(output.labelfile, output.synonymfile)


### SMPDB


rule get_SMPDB:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/SMPDB/smpdb_pathways.csv",
    benchmark:
        config["output_directory"] + "/benchmarks/get_SMPDB.tsv"
    run:
        smpdb.pull_smpdb()


rule get_SMPDB_labels:
    input:
        infile=config["download_directory"] + "/SMPDB/smpdb_pathways.csv",
    output:
        labelfile=config["download_directory"] + "/SMPDB/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/get_SMPDB_labels.tsv"
    run:
        smpdb.make_labels(input.infile, output.labelfile)


### PantherPathways


rule get_panther_pathways:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/PANTHER.PATHWAY/SequenceAssociationPathway3.6.8.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/get_panther_pathways.tsv"
    run:
        pantherpathways.pull_panther_pathways()


rule get_panther_pathway_labels:
    input:
        infile=config["download_directory"] + "/PANTHER.PATHWAY/SequenceAssociationPathway3.6.8.txt",
    output:
        labelfile=config["download_directory"] + "/PANTHER.PATHWAY/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/get_panther_pathway_labels.tsv"
    run:
        pantherpathways.make_pathway_labels(input.infile, output.labelfile)


### Unichem


rule get_unichem:
    resources:
        mem="8G",
        cpus_per_task=1,
    retries: 5
    output:
        config["download_directory"] + "/UNICHEM/structure.tsv.gz",
        config["download_directory"] + "/UNICHEM/reference.tsv.gz",
    benchmark:
        config["output_directory"] + "/benchmarks/get_unichem.tsv"
    run:
        unichem.pull_unichem()


rule filter_unichem:
    input:
        reffile=config["download_directory"] + "/UNICHEM/reference.tsv.gz",
    output:
        filteredreffile=config["download_directory"] + "/UNICHEM/reference.filtered.tsv",
    benchmark:
        config["output_directory"] + "/benchmarks/filter_unichem.tsv"
    run:
        unichem.filter_unichem(input.reffile, output.filteredreffile)


### CHEMBL


rule get_chembl:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        moleculefile=config["download_directory"] + "/CHEMBL.COMPOUND/chembl_latest_molecule.ttl",
        ccofile=config["download_directory"] + "/CHEMBL.COMPOUND/cco.ttl",
    benchmark:
        config["output_directory"] + "/benchmarks/get_chembl.tsv"
    run:
        chembl.pull_chembl(output.moleculefile)


rule chembl_labels_and_smiles:
    resources:
        mem="128G",
    input:
        infile=config["download_directory"] + "/CHEMBL.COMPOUND/chembl_latest_molecule.ttl",
        ccofile=config["download_directory"] + "/CHEMBL.COMPOUND/cco.ttl",
    output:
        outfile=config["download_directory"] + "/CHEMBL.COMPOUND/labels",
        smifile=config["download_directory"] + "/CHEMBL.COMPOUND/smiles",
    benchmark:
        config["output_directory"] + "/benchmarks/chembl_labels_and_smiles.tsv"
    run:
        chembl.pull_chembl_labels_and_smiles(input.infile, input.ccofile, output.outfile, output.smifile)


### DrugBank requires a login... but not for basic vocabulary information.
rule get_drugbank_labels_and_synonyms:
    output:
        outfile=config["download_directory"] + "/DRUGBANK/drugbank vocabulary.csv",
        labels=config["download_directory"] + "/DRUGBANK/labels",
        synonyms=config["download_directory"] + "/DRUGBANK/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/get_drugbank_labels_and_synonyms.tsv"
    run:
        drugbank.download_drugbank_vocabulary(config["drugbank_version"], output.outfile)
        drugbank.extract_drugbank_labels_and_synonyms(output.outfile, output.labels, output.synonyms)


### GTOPDB We're only pulling ligands.  Maybe one day we'll want the whole db?


rule get_gtopdb:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/GTOPDB/ligands.tsv",
    benchmark:
        config["output_directory"] + "/benchmarks/get_gtopdb.tsv"
    run:
        gtopdb.pull_gtopdb_ligands()


rule gtopdb_labels_and_synonyms:
    input:
        infile=config["download_directory"] + "/GTOPDB/ligands.tsv",
    output:
        labelfile=config["download_directory"] + "/GTOPDB/labels",
        synfile=config["download_directory"] + "/GTOPDB/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/gtopdb_labels_and_synonyms.tsv"
    run:
        gtopdb.make_labels_and_synonyms(input.infile, output.labelfile, output.synfile)


# KEGG We're also only getting compounds now.  And we're going through the api b/c data files are not available
# so no data pull, just making labels


rule keggcompound_labels:
    output:
        labelfile=config["download_directory"] + "/KEGG.COMPOUND/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/keggcompound_labels.tsv"
    run:
        kegg.pull_kegg_compound_labels(output.labelfile)


# UNII


rule get_unii:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/UNII/Latest_UNII_Names.txt",
        config["download_directory"] + "/UNII/Latest_UNII_Records.txt",
    benchmark:
        config["output_directory"] + "/benchmarks/get_unii.tsv"
    run:
        unii.pull_unii()


rule unii_labels_and_synonyms:
    input:
        infile=config["download_directory"] + "/UNII/Latest_UNII_Names.txt",
    output:
        labelfile=config["download_directory"] + "/UNII/labels",
        synfile=config["download_directory"] + "/UNII/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/unii_labels_and_synonyms.tsv"
    run:
        unii.make_labels_and_synonyms(input.infile, output.labelfile, output.synfile)


# HMDB


rule get_HMDB:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        outfile=config["download_directory"] + "/HMDB/hmdb_metabolites.xml",
    benchmark:
        config["output_directory"] + "/benchmarks/get_HMDB.tsv"
    run:
        hmdb.pull_hmdb()


rule hmdb_labels_and_synonyms:
    input:
        infile=config["download_directory"] + "/HMDB/hmdb_metabolites.xml",
    output:
        labelfile=config["download_directory"] + "/HMDB/labels",
        synfile=config["download_directory"] + "/HMDB/synonyms",
        smifile=config["download_directory"] + "/HMDB/smiles",
    benchmark:
        config["output_directory"] + "/benchmarks/hmdb_labels_and_synonyms.tsv"
    run:
        hmdb.make_labels_and_synonyms_and_smiles(input.infile, output.labelfile, output.synfile, output.smifile)


# PUBCHEM:


rule get_pubchem:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/PUBCHEM.COMPOUND/CID-MeSH",
        config["download_directory"] + "/PUBCHEM.COMPOUND/CID-Synonym-filtered.gz",
        config["download_directory"] + "/PUBCHEM.COMPOUND/CID-Title.gz",
    benchmark:
        config["output_directory"] + "/benchmarks/get_pubchem.tsv"
    run:
        pubchem.pull_pubchem()


rule get_pubchem_structures:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/PUBCHEM.COMPOUND/CID-InChI-Key.gz",
        config["download_directory"] + "/PUBCHEM.COMPOUND/CID-SMILES.gz",
    benchmark:
        config["output_directory"] + "/benchmarks/get_pubchem_structures.tsv"
    run:
        pubchem.pull_pubchem_structures()


rule pubchem_labels:
    input:
        infile=config["download_directory"] + "/PUBCHEM.COMPOUND/CID-Title.gz",
    output:
        outfile=config["download_directory"] + "/PUBCHEM.COMPOUND/labels",
    benchmark:
        config["output_directory"] + "/benchmarks/pubchem_labels.tsv"
    run:
        pubchem.make_labels_or_synonyms(input.infile, output.outfile)


rule pubchem_synonyms:
    input:
        infile=config["download_directory"] + "/PUBCHEM.COMPOUND/CID-Synonym-filtered.gz",
    output:
        outfile=config["download_directory"] + "/PUBCHEM.COMPOUND/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/pubchem_synonyms.tsv"
    run:
        pubchem.make_labels_or_synonyms(input.infile, output.outfile)


rule download_rxnorm:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/RxNorm/RXNCONSO.RRF",
        config["download_directory"] + "/RxNorm/RXNREL.RRF",
    benchmark:
        config["output_directory"] + "/benchmarks/download_rxnorm.tsv"
    run:
        umls.download_rxnorm(config["rxnorm_version"], config["download_directory"] + "/RxNorm")


rule pubchem_rxnorm_annotations:
    output:
        outfile=config["download_directory"] + "/PUBCHEM.COMPOUND/RXNORM.json",
    benchmark:
        config["output_directory"] + "/benchmarks/pubchem_rxnorm_annotations.tsv"
    run:
        pubchem.pull_rxnorm_annotations(output.outfile)


# DRUGCENTRAL


rule get_drugcentral:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        structfile=config["download_directory"] + "/DrugCentral/structures",
        labelfile=config["download_directory"] + "/DrugCentral/labels",
        xreffile=config["download_directory"] + "/DrugCentral/xrefs",
    benchmark:
        config["output_directory"] + "/benchmarks/get_drugcentral.tsv"
    run:
        drugcentral.pull_drugcentral(output.structfile, output.labelfile, output.xreffile)


# NCBITaxon


rule get_ncbitaxon:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/NCBITaxon/taxdump.tar",
    benchmark:
        config["output_directory"] + "/benchmarks/get_ncbitaxon.tsv"
    run:
        ncbitaxon.pull_ncbitaxon()


rule ncbitaxon_labels_and_synonyms:
    input:
        infile=config["download_directory"] + "/NCBITaxon/taxdump.tar",
    output:
        lfile=config["download_directory"] + "/NCBITaxon/labels",
        sfile=config["download_directory"] + "/NCBITaxon/synonyms",
        propfilegz=config["download_directory"] + "/NCBITaxon/properties.tsv.gz",
    benchmark:
        config["output_directory"] + "/benchmarks/ncbitaxon_labels_and_synonyms.tsv"
    run:
        ncbitaxon.make_labels_and_synonyms(input.infile, output.lfile, output.sfile, output.propfilegz)


# CHEBI: some comes via obo, but we need the SDF file too


rule get_chebi:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/CHEBI/ChEBI_complete.sdf",
        config["download_directory"] + "/CHEBI/database_accession.tsv",
    benchmark:
        config["output_directory"] + "/benchmarks/get_chebi.tsv"
    run:
        chebi.pull_chebi()


# CLO: Cell Line Ontology


rule get_clo:
    resources:
        mem="8G",
        cpus_per_task=1,
    output:
        config["download_directory"] + "/CLO/clo.owl",
        metadata=config["download_directory"] + "/CLO/metadata.yaml",
    benchmark:
        config["output_directory"] + "/benchmarks/get_clo.tsv"
    run:
        clo.pull_clo(output.metadata)


rule get_CLO_labels:
    input:
        infile=config["download_directory"] + "/CLO/clo.owl",
    output:
        labelfile=config["download_directory"] + "/CLO/labels",
        synonymfile=config["download_directory"] + "/CLO/synonyms",
    benchmark:
        config["output_directory"] + "/benchmarks/get_CLO_labels.tsv"
    run:
        clo.make_labels(input.infile, output.labelfile, output.synonymfile)
