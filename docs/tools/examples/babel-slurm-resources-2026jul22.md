<!-- Captured output of `babel-slurm-resources` on the 2026jul22 run, BEFORE the sizing changes
     it prompted. Kept as the evidence behind the current `resources:` blocks and the hotspot
     table in slurm/README.md. See docs/tools/Resources.md.

     UNITS: captured before the mebibyte/megabyte fix, so every "actual RSS" here is in mebibytes
     while every "req mem" is decimal MB rendered as if binary. Read the actual-RSS figures as
     ~4.9% LOW relative to the request, and the req-mem figures as ~4.9% low in absolute terms
     (`500.0G` is a rule declaring `mem="512G"`). The mem% column is correspondingly optimistic:
     `untyped_chemical_compendia` is the case that mattered. Re-running the tool today prints
     decimal throughout; the numbers quoted in slurm/README.md are the corrected ones. -->

# SLURM resource analysis

Rules with benchmarks: 355  |  over-provisioned: 34  |  at-risk: 5  |  no request data: 227
Wasted reservation (requested minus used): 21252 GB across rules with a known request.

Proposed new default: mem=16G, cpus=1. Detected run default: mem=15.6G.
1 of 44 exceeding rule(s) ran on the default and need a *new* block; 34 already carry one; 9 have no request data (check manually).

## Rules exceeding the proposed default

`ran on default` = **yes** → needs a new `resources:` block; **no** → already has one; **?** → unknown.

rule | actual RSS | rec mem | rec cpus | ran on default
---- | ---------- | ------- | -------- | --------------
check_chemical_completeness | 13.7G | 24.0G | 1 | yes
export_synonyms_to_duckdb_GeneProteinConflated | 127.5G | 192.0G | 3 | ?
export_synonyms_to_duckdb_Protein | 96.1G | 192.0G | 2 | ?
export_synonyms_to_duckdb_DrugChemicalConflated | 85.2G | 128.0G | 3 | ?
export_synonyms_to_duckdb_Gene | 25.8G | 48.0G | 3 | ?
taxon_compendia | 14.1G | 24.0G | 1 | ?
export_synonyms_to_duckdb_OrganismTaxon | 1.3G | 8.0G | 3 | ?
export_synonyms_to_duckdb_umls | 1.1G | 8.0G | 2 | ?
export_synonyms_to_duckdb_Disease | 0.7G | 8.0G | 2 | ?
generate_kgx_ChemicalEntity | 0.3G | 8.0G | 2 | ?
chemical_compendia | 335.1G | 512.0G | 1 | no
protein_compendia | 246.0G | 384.0G | 1 | no
gene_compendia | 178.8G | 384.0G | 1 | no
untyped_chemical_compendia | 132.1G | 256.0G | 1 | no
generate_pubmed_compendia | 123.4G | 192.0G | 1 | no
chemical_unichem_concordia | 111.6G | 192.0G | 1 | no
generate_curie_report | 103.6G | 192.0G | 1 | no
geneprotein_conflated_synonyms | 98.2G | 192.0G | 1 | no
check_for_duplicate_curies | 97.3G | 192.0G | 1 | no
generate_prefix_report | 89.9G | 192.0G | 1 | no
generate_clique_leader_report | 88.7G | 192.0G | 1 | no
chembl_labels_and_smiles | 85.0G | 128.0G | 1 | no
check_for_identically_labeled_cliques | 60.3G | 96.0G | 1 | no
drugchemical_conflation | 57.0G | 96.0G | 1 | no
check_for_duplicate_clique_leaders | 52.0G | 96.0G | 2 | no
geneprotein_conflation | 41.4G | 64.0G | 1 | no
export_compendia_to_duckdb_SmallMolecule | 40.2G | 64.0G | 2 | no
generate_pubmed_concords | 31.3G | 48.0G | 1 | no
hmdb_labels_and_synonyms | 28.9G | 48.0G | 1 | no
get_uniprotkb_labels | 27.8G | 48.0G | 1 | no
export_compendia_to_duckdb_Protein | 25.5G | 48.0G | 2 | no
export_compendia_to_duckdb_Gene | 25.4G | 48.0G | 2 | no
get_chemical_unichem_relationships | 20.9G | 32.0G | 1 | no
export_compendia_to_duckdb_Publication | 19.3G | 32.0G | 2 | no
check_protein_completeness | 13.9G | 24.0G | 1 | no
export_compendia_to_duckdb_MolecularMixture | 7.3G | 16.0G | 2 | no
export_compendia_to_duckdb_OrganismTaxon | 1.1G | 8.0G | 2 | no
export_compendia_to_duckdb_MolecularActivity | 0.6G | 8.0G | 2 | no
export_compendia_to_duckdb_Drug | 0.5G | 8.0G | 2 | no
export_compendia_to_duckdb_Disease | 0.5G | 8.0G | 2 | no
export_compendia_to_duckdb_BiologicalProcess | 0.4G | 8.0G | 2 | no
export_compendia_to_duckdb_Pathway | 0.4G | 8.0G | 2 | no
export_compendia_to_duckdb_GeneFamily | 0.3G | 8.0G | 2 | no
export_compendia_to_duckdb_CellLine | 0.3G | 8.0G | 2 | no

## Runtime fit

Wall time against the declared `runtime` limit (from the rule's log, else its snakefile, else the cluster default). **at-risk** rules are close to being killed; **over** rules have a limit at least twice what they need, which makes Snakemake's remaining-time estimate useless and hides a job that has become pathologically slow.

Rules at risk of timing out: 3  |  declaring more time than they need: 90
256 rules ran on the default runtime; the slowest was `chemical` at 1.9h, so the default could drop to 2.0h before any of them is at risk.

rule | wall | limit | wall% | rec runtime | class
---- | ---- | ----- | ----- | ----------- | -----
chemical | 1.9h | 2.0h | 93% | 3.0h | at-risk
generate_pubmed_compendia | 1.8h | 2.0h | 88% | 3.0h | at-risk
generate_pubmed_concords | 20.0h | 24.0h | 83% | 36.0h | at-risk
generate_sapbert_training_data_GeneProteinConflated.txt | 1.9h | 6.0h | 31% | 3.0h | over
get_ensembl | 1.9h | 6.0h | 31% | 3.0h | over
protein | 1.6h | 6.0h | 27% | 3.0h | over
generate_sapbert_training_data_DrugChemicalConflated.txt | 1.6h | 6.0h | 27% | 3.0h | over
export_compendia_to_duckdb_Gene | 1.6h | 6.0h | 27% | 3.0h | over
generate_kgx_Protein | 90m | 6.0h | 25% | 3.0h | over
download_unichem_structure | 58m | 4.0h | 24% | 2.0h | over
generate_sapbert_training_data_Protein.txt | 78m | 6.0h | 22% | 2.0h | over
generate_kgx_Publication | 71m | 6.0h | 20% | 2.0h | over
generate_kgx_Gene | 51m | 6.0h | 14% | 2.0h | over
generate_sapbert_training_data_Gene.txt | 38m | 6.0h | 10% | 60m | over
export_compendia_to_duckdb_Publication | 35m | 6.0h | 10% | 60m | over
export_synonyms_to_duckdb_GeneProteinConflated | 13m | 3.0h | 7% | 30m | over
get_uniprotkb_trembl | 23m | 6.0h | 6% | 60m | over
export_synonyms_to_duckdb_Protein | 10m | 3.0h | 5% | 30m | over
generate_kgx_MolecularMixture | 18m | 6.0h | 5% | 30m | over
export_synonyms_to_duckdb_DrugChemicalConflated | 9m | 3.0h | 5% | 30m | over
download_unichem_reference | 3m | 60m | 5% | 30m | over
get_uniprotkb_idmapping | 11m | 6.0h | 3% | 30m | over
download_pubmed | 11m | 6.0h | 3% | 30m | over
export_compendia_to_duckdb_MolecularMixture | 10m | 6.0h | 3% | 30m | over
export_synonyms_to_duckdb_Gene | 4m | 3.0h | 2% | 30m | over
export_compendia_to_duckdb_OrganismTaxon | 3m | 6.0h | 1% | 30m | over
generate_kgx_OrganismTaxon | 2m | 6.0h | 1% | 30m | over
generate_sapbert_training_data_OrganismTaxon.txt | 2m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_umls.txt | 1m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_umls | 1m | 6.0h | 0% | 30m | over
generate_kgx_Disease | 1m | 6.0h | 0% | 30m | over
generate_kgx_umls | 1m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_Disease.txt | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_OrganismTaxon | 0m | 3.0h | 0% | 30m | over
generate_kgx_ChemicalEntity | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_Disease | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_ChemicalEntity | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_umls | 0m | 3.0h | 0% | 30m | over
generate_kgx_Drug | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_Disease | 0m | 3.0h | 0% | 30m | over
export_compendia_to_duckdb_Drug | 0m | 6.0h | 0% | 30m | over
generate_kgx_AnatomicalEntity | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_MolecularActivity | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_MolecularActivity.txt | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_AnatomicalEntity | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_AnatomicalEntity.txt | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_MolecularActivity | 0m | 3.0h | 0% | 30m | over
generate_kgx_MolecularActivity | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_AnatomicalEntity | 0m | 3.0h | 0% | 30m | over
export_compendia_to_duckdb_PhenotypicFeature | 0m | 6.0h | 0% | 30m | over
generate_kgx_PhenotypicFeature | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_PhenotypicFeature | 0m | 3.0h | 0% | 30m | over
generate_sapbert_training_data_PhenotypicFeature.txt | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_BiologicalProcess.txt | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_Pathway | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_BiologicalProcess | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_BiologicalProcess | 0m | 3.0h | 0% | 30m | over
export_synonyms_to_duckdb_Pathway | 0m | 3.0h | 0% | 30m | over
export_compendia_to_duckdb_CellLine | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_GeneFamily | 0m | 6.0h | 0% | 30m | over
generate_kgx_BiologicalProcess | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_Pathway.txt | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_CellLine | 0m | 3.0h | 0% | 30m | over
export_synonyms_to_duckdb_GeneFamily | 0m | 3.0h | 0% | 30m | over
export_compendia_to_duckdb_MacromolecularComplex | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_MacromolecularComplex | 0m | 3.0h | 0% | 30m | over
generate_kgx_GrossAnatomicalStructure | 0m | 6.0h | 0% | 30m | over
generate_kgx_Pathway | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_GrossAnatomicalStructure | 0m | 3.0h | 0% | 30m | over
export_compendia_to_duckdb_GrossAnatomicalStructure | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_CellLine.txt | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_CellularComponent | 0m | 3.0h | 0% | 30m | over
generate_sapbert_training_data_GrossAnatomicalStructure.txt | 0m | 6.0h | 0% | 30m | over
export_synonyms_to_duckdb_Cell | 0m | 3.0h | 0% | 30m | over
export_compendia_to_duckdb_Cell | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_CellularComponent | 0m | 6.0h | 0% | 30m | over
generate_kgx_CellLine | 0m | 6.0h | 0% | 30m | over
generate_kgx_GeneFamily | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_GeneFamily.txt | 0m | 6.0h | 0% | 30m | over
generate_kgx_Cell | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_Cell.txt | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_MacromolecularComplex.txt | 0m | 6.0h | 0% | 30m | over
generate_kgx_CellularComponent | 0m | 6.0h | 0% | 30m | over
generate_sapbert_training_data_CellularComponent.txt | 0m | 6.0h | 0% | 30m | over
generate_kgx_MacromolecularComplex | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_ComplexMolecularMixture | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_ChemicalMixture | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_Food | 0m | 6.0h | 0% | 30m | over
generate_kgx_Food | 0m | 6.0h | 0% | 30m | over
export_compendia_to_duckdb_Polypeptide | 0m | 6.0h | 0% | 30m | over
generate_kgx_ComplexMolecularMixture | 0m | 6.0h | 0% | 30m | over
generate_kgx_ChemicalMixture | 0m | 6.0h | 0% | 30m | over
generate_kgx_Polypeptide | 0m | 6.0h | 0% | 30m | over

## All rules (by actual peak RSS)

rule | actual RSS | req mem | mem% | cores | req cpus | wall | rec mem | rec cpus | class
---- | ---------- | ------- | ---- | ----- | -------- | ---- | ------- | -------- | -----
chemical_compendia | 335.1G | 500.0G | 67% | 1.0 | 1 | 18979s | 512.0G | 1 | ok
protein_compendia | 246.0G | 500.0G | 49% | 1.0 | - | 19876s | 384.0G | 1 | ok
gene_compendia | 178.8G | 250.0G | 72% | 1.0 | - | 15400s | 384.0G | 1 | ok
untyped_chemical_compendia | 132.1G | 500.0G | 26% | 0.9 | 1 | 3494s | 256.0G | 1 | ok
export_synonyms_to_duckdb_GeneProteinConflated | 127.5G | - | - | 2.1 | - | 776s | 192.0G | 3 | no-request-data
generate_pubmed_compendia | 123.4G | 125.0G | 99% | 1.0 | - | 6308s | 192.0G | 1 | at-risk
chemical_unichem_concordia | 111.6G | 125.0G | 89% | 0.9 | 1 | 2755s | 192.0G | 1 | at-risk
generate_curie_report | 103.6G | 1464.8G | 7% | 0.8 | 1 | 352s | 192.0G | 1 | over
geneprotein_conflated_synonyms | 98.2G | 500.0G | 20% | 1.0 | - | 15719s | 192.0G | 1 | over
check_for_duplicate_curies | 97.3G | 1464.8G | 7% | 0.4 | 1 | 782s | 192.0G | 1 | over
export_synonyms_to_duckdb_Protein | 96.1G | - | - | 1.9 | - | 591s | 192.0G | 2 | no-request-data
generate_prefix_report | 89.9G | 1464.8G | 6% | 0.4 | 1 | 879s | 192.0G | 1 | over
generate_clique_leader_report | 88.7G | 1464.8G | 6% | 0.8 | 1 | 311s | 192.0G | 1 | over
export_synonyms_to_duckdb_DrugChemicalConflated | 85.2G | - | - | 2.6 | - | 533s | 128.0G | 3 | no-request-data
chembl_labels_and_smiles | 85.0G | 125.0G | 68% | 0.8 | - | 1915s | 128.0G | 1 | ok
check_for_identically_labeled_cliques | 60.3G | 500.0G | 12% | 0.6 | 1 | 1077s | 96.0G | 1 | over
drugchemical_conflation | 57.0G | 62.5G | 91% | 0.9 | 1 | 1867s | 96.0G | 1 | at-risk
check_for_duplicate_clique_leaders | 52.0G | 500.0G | 10% | 1.1 | 1 | 195s | 96.0G | 2 | over
geneprotein_conflation | 41.4G | 62.5G | 66% | 1.0 | - | 2200s | 64.0G | 1 | ok
export_compendia_to_duckdb_SmallMolecule | 40.2G | 500.0G | 8% | 1.7 | - | 8246s | 64.0G | 2 | over
generate_pubmed_concords | 31.3G | 125.0G | 25% | 1.0 | - | 71947s | 48.0G | 1 | over
hmdb_labels_and_synonyms | 28.9G | 46.9G | 62% | 0.9 | 1 | 631s | 48.0G | 1 | ok
get_uniprotkb_labels | 27.8G | 46.9G | 59% | 0.8 | - | 590s | 48.0G | 1 | ok
export_synonyms_to_duckdb_Gene | 25.8G | - | - | 2.9 | - | 257s | 48.0G | 3 | no-request-data
export_compendia_to_duckdb_Protein | 25.5G | 500.0G | 5% | 1.3 | - | 8873s | 48.0G | 2 | over
export_compendia_to_duckdb_Gene | 25.4G | 500.0G | 5% | 2.0 | - | 5742s | 48.0G | 2 | over
get_chemical_unichem_relationships | 20.9G | 23.4G | 89% | 1.0 | 1 | 921s | 32.0G | 1 | at-risk
export_compendia_to_duckdb_Publication | 19.3G | 500.0G | 4% | 1.3 | - | 2110s | 32.0G | 2 | over
taxon_compendia | 14.1G | - | - | 1.0 | - | 416s | 24.0G | 1 | no-request-data
check_protein_completeness | 13.9G | 23.4G | 59% | 1.0 | - | 901s | 24.0G | 1 | ok
check_chemical_completeness | 13.7G | 15.6G | 88% | 1.0 | 1 | 894s | 24.0G | 1 | at-risk
leftover_umls | 9.7G | 15.6G | 62% | 0.9 | 1 | 1876s | 16.0G | 1 | ok
umls_relationships | 9.2G | - | - | 0.8 | - | 195s | 16.0G | 1 | no-request-data
disease_compendia | 8.6G | - | - | 0.9 | - | 243s | 16.0G | 1 | no-request-data
geneprotein_uniprot_relationships | 7.8G | - | - | 1.0 | - | 837s | 16.0G | 1 | no-request-data
anatomy_compendia | 7.7G | - | - | 0.9 | - | 328s | 16.0G | 1 | no-request-data
export_intermediate_files_to_duckdb | 7.7G | 125.0G | 6% | 0.8 | 1 | 1265s | 16.0G | 1 | over
export_compendia_to_duckdb_MolecularMixture | 7.3G | 500.0G | 1% | 1.1 | - | 607s | 16.0G | 2 | over
get_gene_ncbigene_ensembl_relationships | 7.1G | - | - | 0.7 | - | 130s | 16.0G | 1 | no-request-data
check_gene_completeness | 6.9G | - | - | 0.9 | - | 450s | 16.0G | 1 | no-request-data
process_compendia | 6.5G | 15.6G | 42% | 0.9 | 1 | 218s | 16.0G | 1 | ok
get_mesh_labels | 6.4G | - | - | 0.8 | - | 137s | 16.0G | 1 | no-request-data
get_gene_ncbigene_relationships | 6.4G | - | - | 0.9 | - | 255s | 16.0G | 1 | no-request-data
get_chemical_mesh_relationships | 6.3G | - | - | 1.0 | - | 109s | 16.0G | 1 | no-request-data
get_taxon_relationships | 6.2G | - | - | 1.0 | - | 114s | 16.0G | 1 | no-request-data
chemical_mesh_ids | 6.2G | - | - | 0.8 | - | 135s | 16.0G | 1 | no-request-data
taxon_mesh_ids | 6.1G | - | - | 0.7 | - | 107s | 16.0G | 1 | no-request-data
disease_mesh_ids | 6.1G | - | - | 0.7 | - | 115s | 16.0G | 1 | no-request-data
anatomy_mesh_ids | 6.1G | - | - | 1.0 | - | 116s | 16.0G | 1 | no-request-data
check_publications_completeness | 4.6G | - | - | 0.9 | - | 280s | 8.0G | 1 | no-request-data
get_umls_labels_and_synonyms | 3.7G | - | - | 0.7 | - | 70s | 8.0G | 1 | no-request-data
get_anatomy_obo_relationships | 3.3G | - | - | 0.2 | - | 309s | 8.0G | 1 | no-request-data
anatomy_uberon_ids | 3.2G | - | - | 0.2 | - | 273s | 8.0G | 1 | no-request-data
get_mods | 3.1G | 7.8G | 40% | 0.7 | - | 17s | 8.0G | 1 | ok
cell_line_compendia | 2.9G | - | - | 1.0 | - | 48s | 8.0G | 1 | no-request-data
macromolecular_complex_compendia | 2.8G | - | - | 1.0 | - | 50s | 8.0G | 1 | no-request-data
genefamily_compendia | 2.8G | - | - | 0.9 | - | 49s | 8.0G | 1 | no-request-data
get_mods_labels | 2.2G | - | - | 0.7 | - | 24s | 8.0G | 1 | no-request-data
get_chebi_concord | 2.2G | - | - | 0.9 | - | 21s | 8.0G | 1 | no-request-data
get_obo_synonyms | 2.0G | 7.8G | 25% | 0.1 | - | 683s | 8.0G | 1 | ok
get_EFO_labels | 1.7G | - | - | 0.7 | - | 24s | 8.0G | 1 | no-request-data
disease_efo_ids | 1.6G | - | - | 0.7 | - | 24s | 8.0G | 1 | no-request-data
taxon_umls_ids | 1.6G | - | - | 0.7 | - | 13s | 8.0G | 1 | no-request-data
get_obo_labels | 1.6G | 7.8G | 20% | 0.1 | - | 580s | 8.0G | 1 | ok
ncbitaxon_labels_and_synonyms | 1.6G | - | - | 0.8 | - | 52s | 8.0G | 1 | no-request-data
get_disease_efo_relationships | 1.6G | - | - | 0.6 | - | 27s | 8.0G | 1 | no-request-data
chemical_umls_ids | 1.6G | - | - | 0.9 | - | 15s | 8.0G | 1 | no-request-data
protein_umls_ids | 1.5G | - | - | 0.8 | - | 12s | 8.0G | 1 | no-request-data
anatomy_umls_ids | 1.4G | - | - | 0.8 | - | 12s | 8.0G | 1 | no-request-data
process_umls_ids | 1.4G | - | - | 0.7 | - | 12s | 8.0G | 1 | no-request-data
disease_umls_ids | 1.4G | - | - | 0.8 | - | 12s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_OrganismTaxon | 1.3G | - | - | 2.3 | - | 10s | 8.0G | 3 | no-request-data
get_ensembl | 1.3G | 7.8G | 17% | 0.0 | - | 6665s | 8.0G | 1 | ok
export_compendia_to_duckdb_OrganismTaxon | 1.1G | 500.0G | 0% | 2.0 | - | 201s | 8.0G | 2 | over
get_rhea_labels | 1.1G | - | - | 0.9 | - | 13s | 8.0G | 1 | no-request-data
get_process_rhea_relationships | 1.1G | - | - | 0.8 | - | 12s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_umls | 1.1G | - | - | 1.7 | - | 8s | 8.0G | 2 | no-request-data
rxnorm_relationships | 0.9G | - | - | 0.9 | - | 17s | 8.0G | 1 | no-request-data
chemical_chembl_ids | 0.8G | - | - | 0.8 | - | 6s | 8.0G | 1 | no-request-data
export_conflation_to_duckdb_GeneProtein | 0.7G | - | - | 0.8 | - | 93s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_umls | 0.7G | 500.0G | 0% | 0.9 | - | 55s | 8.0G | 1 | over
export_synonyms_to_duckdb_Disease | 0.7G | - | - | 1.3 | - | 6s | 8.0G | 2 | no-request-data
drugchemical_conflated_synonyms | 0.6G | 15.6G | 4% | 1.0 | 1 | 9884s | 8.0G | 1 | ok
get_obo_descriptions | 0.6G | 7.8G | 8% | 0.0 | - | 361s | 8.0G | 1 | ok
export_compendia_to_duckdb_MolecularActivity | 0.6G | 500.0G | 0% | 1.1 | - | 10s | 8.0G | 2 | over
export_synonyms_to_duckdb_MolecularActivity | 0.6G | - | - | 1.0 | - | 3s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_ChemicalEntity | 0.5G | 500.0G | 0% | 0.9 | - | 17s | 8.0G | 1 | over
check_taxon_completeness | 0.5G | - | - | 1.0 | - | 20s | 8.0G | 1 | no-request-data
generate_kgx_MolecularMixture | 0.5G | - | - | 1.0 | - | 1088s | 8.0G | 1 | no-request-data
generate_kgx_SmallMolecule | 0.5G | - | - | 1.0 | - | 9773s | 8.0G | 1 | no-request-data
get_icrdf | 0.5G | - | - | 0.1 | - | 457s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_Drug | 0.5G | 500.0G | 0% | 1.1 | - | 12s | 8.0G | 2 | over
generate_kgx_Publication | 0.5G | - | - | 1.0 | - | 4277s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_Disease | 0.5G | 500.0G | 0% | 1.6 | - | 19s | 8.0G | 2 | over
get_clo_ids | 0.5G | - | - | 0.6 | - | 3s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_AnatomicalEntity | 0.5G | 500.0G | 0% | 1.0 | - | 8s | 8.0G | 1 | over
get_CLO_labels | 0.5G | - | - | 0.7 | - | 3s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_BiologicalProcess | 0.5G | - | - | 0.9 | - | 2s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_AnatomicalEntity | 0.4G | - | - | 0.6 | - | 3s | 8.0G | 1 | no-request-data
generate_kgx_Disease | 0.4G | - | - | 0.5 | - | 40s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_PhenotypicFeature | 0.4G | 500.0G | 0% | 0.9 | - | 5s | 8.0G | 1 | over
export_synonyms_to_duckdb_PhenotypicFeature | 0.4G | - | - | 0.8 | - | 2s | 8.0G | 1 | no-request-data
verify_pubmed | 0.4G | - | - | 0.3 | - | 723s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_BiologicalProcess | 0.4G | 500.0G | 0% | 1.3 | - | 3s | 8.0G | 2 | over
get_chemical_umls_relationships | 0.4G | - | - | 1.0 | - | 36s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_Pathway | 0.4G | 500.0G | 0% | 1.5 | - | 4s | 8.0G | 2 | over
get_chemical_pubchem_mesh_concord | 0.4G | - | - | 0.3 | - | 3s | 8.0G | 1 | no-request-data
generate_kgx_Protein | 0.4G | - | - | 1.0 | - | 5388s | 8.0G | 1 | no-request-data
generate_kgx_Gene | 0.3G | - | - | 1.0 | - | 3071s | 8.0G | 1 | no-request-data
generate_kgx_AnatomicalEntity | 0.3G | - | - | 0.9 | - | 10s | 8.0G | 1 | no-request-data
chemical_chebi_ids | 0.3G | - | - | 0.1 | - | 54s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_Pathway | 0.3G | - | - | 0.6 | - | 1s | 8.0G | 1 | no-request-data
generate_kgx_ChemicalEntity | 0.3G | - | - | 1.0 | - | 20s | 8.0G | 2 | no-request-data
export_conflation_to_duckdb_DrugChemical | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_disease_umls_relationships | 0.3G | - | - | 0.9 | - | 36s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_GeneFamily | 0.3G | 500.0G | 0% | 1.2 | - | 2s | 8.0G | 2 | over
generate_kgx_OrganismTaxon | 0.3G | - | - | 0.8 | - | 108s | 8.0G | 1 | no-request-data
generate_kgx_Drug | 0.3G | - | - | 1.0 | - | 13s | 8.0G | 1 | no-request-data
get_taxon_umls_relationships | 0.3G | - | - | 0.9 | - | 35s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_GrossAnatomicalStructure | 0.3G | 500.0G | 0% | 0.6 | - | 1s | 8.0G | 1 | over
generate_kgx_PhenotypicFeature | 0.3G | - | - | 0.9 | - | 5s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_CellLine | 0.3G | 500.0G | 0% | 1.2 | - | 2s | 8.0G | 2 | over
generate_kgx_MolecularActivity | 0.3G | - | - | 0.9 | - | 6s | 8.0G | 1 | no-request-data
generate_kgx_umls | 0.3G | - | - | 0.8 | - | 32s | 8.0G | 1 | no-request-data
get_anatomy_umls_relationships | 0.3G | - | - | 0.9 | - | 35s | 8.0G | 1 | no-request-data
get_reactome | 0.3G | 7.8G | 3% | 0.2 | - | 8s | 8.0G | 1 | ok
export_synonyms_to_duckdb_GrossAnatomicalStructure | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_Cell | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_protein_pr_uniprotkb_relationships | 0.3G | - | - | 0.0 | - | 358s | 8.0G | 1 | no-request-data
get_EC_labels | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_Cell | 0.3G | 500.0G | 0% | 0.0 | - | 1s | 8.0G | 1 | over
export_compendia_to_duckdb_MacromolecularComplex | 0.3G | 500.0G | 0% | 0.5 | - | 2s | 8.0G | 1 | over
process_ec_ids | 0.3G | 15.6G | 2% | 0.0 | 1 | 1s | 8.0G | 1 | ok
generate_kgx_BiologicalProcess | 0.2G | - | - | 0.5 | - | 2s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_GeneFamily | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_CellLine | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_CellularComponent | 0.2G | 500.0G | 0% | 0.0 | - | 1s | 8.0G | 1 | over
generate_kgx_Pathway | 0.2G | - | - | 0.4 | - | 1s | 8.0G | 1 | no-request-data
protein_pr_ids | 0.2G | - | - | 0.0 | - | 30s | 8.0G | 1 | no-request-data
check_disease_completeness | 0.2G | - | - | 0.0 | - | 3s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_MacromolecularComplex | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
protein_ensembl_ids | 0.2G | - | - | 1.0 | - | 23s | 8.0G | 1 | no-request-data
get_protein_umls_relationships | 0.2G | - | - | 0.4 | - | 40s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_CellularComponent | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_process_completeness | 0.2G | 15.6G | 1% | 0.0 | 1 | 2s | 8.0G | 1 | ok
get_process_umls_relationships | 0.2G | - | - | 0.9 | - | 34s | 8.0G | 1 | no-request-data
get_drugcentral | 0.2G | 7.8G | 3% | 0.1 | - | 1s | 8.0G | 1 | ok
generate_kgx_GrossAnatomicalStructure | 0.2G | - | - | 0.4 | - | 2s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_DrugChemicalConflated.txt | 0.2G | - | - | 1.0 | - | 5761s | 8.0G | 1 | no-request-data
get_gene_umls_relationships | 0.2G | - | - | 0.9 | - | 32s | 8.0G | 1 | no-request-data
process_go_ids | 0.2G | - | - | 0.1 | - | 5s | 8.0G | 1 | no-request-data
disease_ncit_ids | 0.2G | - | - | 0.1 | - | 10s | 8.0G | 1 | no-request-data
disease_mondo_ids | 0.2G | - | - | 0.1 | - | 7s | 8.0G | 1 | no-request-data
get_protein_ncit_umls_relationships | 0.2G | - | - | 0.9 | - | 33s | 8.0G | 1 | no-request-data
pubchem_rxnorm_annotations | 0.2G | - | - | 0.1 | - | 10s | 8.0G | 1 | no-request-data
generate_kgx_CellLine | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_uniprotkb_trembl | 0.2G | 7.8G | 3% | 0.8 | - | 1386s | 8.0G | 1 | ok
get_complexportal | 0.2G | 7.8G | 3% | 0.1 | - | 15s | 8.0G | 1 | ok
get_hgnc_labels_and_synonyms | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_pubchem | 0.2G | 7.8G | 3% | 0.2 | - | 23s | 8.0G | 1 | ok
unii_labels_and_synonyms | 0.2G | - | - | 0.5 | - | 2s | 8.0G | 1 | no-request-data
get_uniprotkb_sprot | 0.2G | 7.8G | 3% | 0.6 | - | 5s | 8.0G | 1 | ok
generate_kgx_GeneFamily | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_uniprotkb_idmapping | 0.2G | 7.8G | 3% | 0.7 | - | 669s | 8.0G | 1 | ok
get_pubchem_structures | 0.2G | 7.8G | 3% | 0.1 | - | 55s | 8.0G | 1 | ok
check_anatomy_completeness | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_kgx_Cell | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
anatomy_emapa_ids | 0.2G | - | - | 0.1 | - | 1s | 8.0G | 1 | no-request-data
get_complexportal_labels_and_synonyms | 0.2G | - | - | 0.1 | - | 1s | 8.0G | 1 | no-request-data
gene_umls_ids | 0.2G | - | - | 1.0 | - | 27s | 8.0G | 1 | no-request-data
generate_kgx_CellularComponent | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
chemical_drugbank_food_extracts | 0.2G | 15.6G | 1% | 0.0 | 1 | 1s | 8.0G | 1 | ok
protein | 0.2G | - | - | 1.0 | - | 5815s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_GeneProteinConflated.txt | 0.2G | - | - | 1.0 | - | 6706s | 8.0G | 1 | no-request-data
download_unichem_structure | 0.2G | 7.8G | 3% | 0.1 | 1 | 3453s | 8.0G | 1 | ok
disease_mp_ids | 0.2G | - | - | 0.2 | - | 4s | 8.0G | 1 | no-request-data
anatomy_go_ids | 0.2G | - | - | 0.1 | - | 3s | 8.0G | 1 | no-request-data
get_chebi | 0.2G | 7.8G | 3% | 0.1 | - | 84s | 8.0G | 1 | ok
get_orphanet_labels_and_synonyms | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
anatomy_ncit_ids | 0.2G | - | - | 0.1 | - | 2s | 8.0G | 1 | no-request-data
get_chemical_rxnorm_relationships | 0.2G | - | - | 0.4 | - | 2s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_AnatomicalEntity.txt | 0.2G | - | - | 0.9 | - | 7s | 8.0G | 1 | no-request-data
disease_hp_ids | 0.2G | - | - | 0.1 | - | 5s | 8.0G | 1 | no-request-data
get_chembl | 0.2G | 7.8G | 2% | 0.3 | - | 345s | 8.0G | 1 | ok
generate_sapbert_training_data_BiologicalProcess.txt | 0.2G | - | - | 0.8 | - | 4s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_Protein.txt | 0.2G | - | - | 1.0 | - | 4688s | 8.0G | 1 | no-request-data
gene_ensembl_ids | 0.2G | - | - | 0.9 | - | 23s | 8.0G | 1 | no-request-data
download_pubmed | 0.2G | 7.8G | 2% | 0.0 | - | 643s | 8.0G | 1 | ok
compress_umls | 0.2G | 15.6G | 1% | 0.3 | 1 | 45s | 8.0G | 1 | ok
get_orphanet | 0.2G | 7.8G | 2% | 0.0 | - | 8s | 8.0G | 1 | ok
chemical_pubchem_ids | 0.2G | - | - | 0.9 | - | 333s | 8.0G | 1 | no-request-data
gene | 0.2G | - | - | 1.0 | - | 3328s | 8.0G | 1 | no-request-data
anatomy_cl_ids | 0.2G | - | - | 0.1 | - | 3s | 8.0G | 1 | no-request-data
download_unichem_reference | 0.2G | 7.8G | 2% | 0.2 | - | 167s | 8.0G | 1 | ok
generate_sapbert_training_data_Gene.txt | 0.2G | - | - | 1.0 | - | 2259s | 8.0G | 1 | no-request-data
get_disease_obo_relationships | 0.2G | - | - | 0.0 | - | 74s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_GrossAnatomicalStructure.txt | 0.2G | - | - | 0.4 | - | 1s | 8.0G | 1 | no-request-data
taxon | 0.2G | - | - | 1.0 | - | 138s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_OrganismTaxon.txt | 0.2G | - | - | 0.8 | - | 93s | 8.0G | 1 | no-request-data
check_disease | 0.2G | - | - | 0.4 | - | 3s | 8.0G | 1 | no-request-data
check_activity | 0.2G | 15.6G | 1% | 0.0 | 1 | 1s | 8.0G | 1 | ok
generate_kgx_ComplexMolecularMixture | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_Pathway.txt | 0.2G | - | - | 0.7 | - | 2s | 8.0G | 1 | no-request-data
check_anatomical_entity | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_small_molecule | 0.2G | 15.6G | 1% | 1.0 | 1 | 912s | 8.0G | 1 | ok
check_pathway | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
chemical_ncit_nonfood_codes | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_SmallMolecule | 0.2G | 15.6G | 1% | 1.0 | 1 | 1088s | 8.0G | 1 | ok
export_compendia_to_duckdb_Food | 0.2G | 500.0G | 0% | 0.0 | - | 0s | 8.0G | 1 | over
generate_prefix_comparison | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
get_chemical_drugcentral_relationships | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_cell_line | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_mapping_sources_table | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
get_process_go_relationships | 0.2G | - | - | 0.0 | - | 55s | 8.0G | 1 | no-request-data
anatomy | 0.2G | - | - | 1.0 | - | 8s | 8.0G | 1 | no-request-data
check_conflation_files | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
check_synonyms_gzipped_files | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_cliques_table | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_sapbert_training_data_MolecularActivity.txt | 0.2G | - | - | 0.9 | - | 8s | 8.0G | 1 | no-request-data
genefamily | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_ncbigene | 0.2G | 7.8G | 2% | 0.3 | - | 27s | 8.0G | 1 | ok
chemical_drugcentral_ids | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_drugbank_labels_and_synonyms | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
check_chemical_entity | 0.2G | 15.6G | 1% | 0.4 | 1 | 3s | 8.0G | 1 | ok
filter_unichem | 0.2G | - | - | 0.8 | - | 188s | 8.0G | 1 | no-request-data
process | 0.2G | 15.6G | 1% | 1.0 | 1 | 12s | 8.0G | 1 | ok
generate_compendia_summary_report | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
get_mesh | 0.2G | 7.8G | 2% | 0.4 | - | 46s | 8.0G | 1 | ok
get_SMPDB | 0.2G | 7.8G | 2% | 0.4 | - | 1s | 8.0G | 1 | ok
check_gene | 0.2G | - | - | 1.0 | - | 492s | 8.0G | 1 | no-request-data
check_compendia_files | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
export_compendia_to_duckdb_Polypeptide | 0.2G | 500.0G | 0% | 0.0 | - | 0s | 8.0G | 1 | over
export_compendia_to_duckdb_ChemicalMixture | 0.2G | 500.0G | 0% | 0.0 | - | 0s | 8.0G | 1 | over
generate_content_report_for_compendium_Publication | 0.2G | - | - | 1.0 | - | 410s | 8.0G | 1 | no-request-data
chemical_hmdb_ids | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_content_report_for_compendium_Gene | 0.2G | - | - | 1.0 | - | 649s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_umls.txt | 0.2G | - | - | 0.8 | - | 60s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Pathway | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_content_report_for_compendium_umls | 0.2G | 15.6G | 1% | 0.9 | 1 | 10s | 8.0G | 1 | ok
generate_content_report_for_compendium_GrossAnatomicalStructure | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
cell_line | 0.2G | - | - | 0.4 | - | 1s | 8.0G | 1 | no-request-data
get_protein_uniprotkb_ensembl_relationships | 0.2G | - | - | 0.9 | - | 817s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_Cell.txt | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_hgncfamily_labels | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_disease_doid_relationships | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_ncbigene_labels_synonyms_and_taxa | 0.2G | - | - | 0.9 | - | 729s | 8.0G | 1 | no-request-data
check_food | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
get_ncit | 0.2G | 7.8G | 2% | 0.0 | - | 1s | 8.0G | 1 | ok
gene_omim_ids | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_MolecularActivity | 0.2G | 15.6G | 1% | 0.0 | 1 | 2s | 8.0G | 1 | ok
generate_content_report_for_compendium_BiologicalProcess | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_prefix_table | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_sapbert_training_data_GeneFamily.txt | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_Disease.txt | 0.2G | - | - | 0.7 | - | 23s | 8.0G | 1 | no-request-data
pubchem_synonyms | 0.2G | - | - | 0.8 | - | 165s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_ComplexMolecularMixture | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
disease | 0.2G | - | - | 0.7 | - | 22s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_MacromolecularComplex.txt | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_macromolecular_complex_completeness | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
gtopdb_labels_and_synonyms | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_CellularComponent.txt | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_protein | 0.2G | - | - | 1.0 | - | 994s | 8.0G | 1 | no-request-data
get_panther_pathways | 0.2G | 7.8G | 2% | 0.1 | - | 5s | 8.0G | 1 | ok
get_EFO | 0.2G | 7.8G | 2% | 0.2 | - | 6s | 8.0G | 1 | ok
check_publications | 0.2G | - | - | 0.9 | - | 337s | 8.0G | 1 | no-request-data
get_EC | 0.2G | 7.8G | 2% | 0.0 | - | 2s | 8.0G | 1 | ok
check_polypeptide | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_content_report_for_compendium_Disease | 0.2G | - | - | 0.3 | - | 4s | 8.0G | 1 | no-request-data
check_complex_mixture | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
chemical | 0.2G | 15.6G | 1% | 1.0 | 1 | 6682s | 8.0G | 1 | ok
chemical_rxnorm_ids | 0.2G | - | - | 0.4 | - | 2s | 8.0G | 1 | no-request-data
check_macromolecular_complex | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_chemical_mixture | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
pubchem_rxnorm_relationships | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_process | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
check_phenotypic_feature | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
chemical_drugbank_ids | 0.2G | - | - | 0.4 | - | 52s | 8.0G | 1 | no-request-data
chemical_ncit_food_codes | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_OrganismTaxon | 0.2G | - | - | 0.7 | - | 31s | 8.0G | 1 | no-request-data
check_cellular_component | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_kgx_MacromolecularComplex | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
extract_taxon_ids_from_uniprotkb | 0.2G | - | - | 1.0 | - | 782s | 8.0G | 1 | no-request-data
get_gtopdb | 0.2G | 7.8G | 2% | 0.0 | - | 22s | 8.0G | 1 | ok
generate_content_report_for_compendium_CellularComponent | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_kgx_Polypeptide | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_genefamily_completeness | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_pantherfamily | 0.2G | 7.8G | 2% | 0.0 | - | 263s | 8.0G | 1 | ok
get_protein_ncit_uniprotkb_relationships | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_PhenotypicFeature.txt | 0.2G | - | - | 0.8 | - | 4s | 8.0G | 1 | no-request-data
get_chemical_wikipedia_relationships | 0.2G | - | - | 0.0 | - | 2s | 8.0G | 1 | no-request-data
pubchem_labels | 0.2G | - | - | 0.9 | - | 276s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_CellLine | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_pantherfamily_labels | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Food | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_sapbert_training_data_CellLine.txt | 0.2G | - | - | 0.4 | - | 1s | 8.0G | 1 | no-request-data
get_omim | 0.2G | 7.8G | 2% | 0.0 | - | 1s | 8.0G | 1 | ok
check_taxon | 0.2G | - | - | 0.9 | - | 23s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Protein | 0.2G | - | - | 1.0 | - | 1331s | 8.0G | 1 | no-request-data
get_doid | 0.2G | 7.8G | 2% | 0.0 | - | 1s | 8.0G | 1 | ok
get_rhea | 0.2G | 7.8G | 2% | 0.6 | - | 5s | 8.0G | 1 | ok
export_compendia_to_duckdb_ComplexMolecularMixture | 0.2G | 500.0G | 0% | 0.0 | - | 0s | 8.0G | 1 | over
get_panther_pathway_labels | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Cell | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_unii | 0.2G | 7.8G | 2% | 0.2 | - | 11s | 8.0G | 1 | ok
gene_hgnc_ids | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_GeneFamily | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_kgx_Food | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_AnatomicalEntity | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_ncbitaxon | 0.2G | 7.8G | 2% | 0.1 | - | 20s | 8.0G | 1 | ok
get_gene_medgen_relationships | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_gtopdb_inchikey_concord | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_gross_anatomical_structure | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Polypeptide | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_kgx_ChemicalMixture | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_molecular_mixture | 0.2G | 15.6G | 1% | 0.7 | 1 | 81s | 8.0G | 1 | ok
get_hgncfamily | 0.2G | 7.8G | 2% | 0.0 | - | 1s | 8.0G | 1 | ok
get_omim_labels | 0.2G | 1.0G | 19% | 0.0 | - | 0s | 8.0G | 1 | ok
generate_content_report_for_compendium_ChemicalEntity | 0.2G | 15.6G | 1% | 0.0 | 1 | 3s | 8.0G | 1 | ok
generate_content_report_for_compendium_MolecularMixture | 0.2G | 15.6G | 1% | 0.8 | 1 | 123s | 8.0G | 1 | ok
get_SMPDB_labels | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_cell | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_hgnc | 0.2G | 7.8G | 2% | 0.1 | - | 1s | 8.0G | 1 | ok
disease_mp_taxa | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
process_reactome_ids | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_cell_line_completeness | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_umls_gene_protein_mappings | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_wikidata_cell_relationships | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_chemical_pubchem_cas_concord | 0.2G | - | - | 0.7 | - | 104s | 8.0G | 1 | no-request-data
gene_mods_ids | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
chemical_gtopdb_ids | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Drug | 0.2G | 15.6G | 1% | 0.0 | 1 | 2s | 8.0G | 1 | ok
disease_manual_concord | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_doid_labels_and_synonyms | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_PhenotypicFeature | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_genefamily | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
disease_hp_taxa | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
macromolecular_complex | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
disease_omim_ids | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_drug | 0.2G | 15.6G | 1% | 0.0 | 1 | 1s | 8.0G | 1 | ok
generate_content_report_for_compendium_ChemicalMixture | 0.2G | 15.6G | 1% | 0.0 | 1 | 0s | 8.0G | 1 | ok
get_clo | 0.2G | 7.8G | 2% | 0.1 | - | 1s | 8.0G | 1 | ok
download_rxnorm | 0.2G | 7.8G | 2% | 0.4 | - | 47s | 8.0G | 1 | ok
chemical_unii_ids | 0.2G | - | - | 0.0 | - | 2s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_MacromolecularComplex | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_reactome_labels | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
taxon_ncbi_ids | 0.0G | - | - | 0.3 | - | 2s | 8.0G | 1 | no-request-data
gene_ncbi_ids | 0.0G | - | - | 0.6 | - | 23s | 8.0G | 1 | no-request-data
protein_uniprotkb_ids | 0.0G | - | - | 0.7 | - | 59s | 8.0G | 1 | no-request-data
disease_doid_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
disease_orphanet_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
genefamily_pantherfamily_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
process_rhea_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
process_smpdb_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
genefamily_hgncfamily_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
process_panther_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
