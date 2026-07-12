<!--
Captured example of babel-slurm-resources output, regenerate with:
  uv run babel-slurm-resources data/babel-1.17
See docs/tools/Resources.md for how to read it. This is the analysis behind the resource
tuning in slurm/config.yaml and the per-rule overrides in src/snakefiles/.
-->

> _Example output of `babel-slurm-resources` on the full babel-1.17 run — the analysis behind
> the SLURM defaults in `slurm/config.yaml` and the per-rule overrides. Regenerate with_
> `uv run babel-slurm-resources data/babel-1.17`. _See [Resources.md](../Resources.md) to read it._

# SLURM resource analysis

Rules with benchmarks: 345  |  over-provisioned: 166  |  at-risk: 3  |  no request data: 129
Wasted reservation (requested minus used): 18394 GB across rules with a known request.

Proposed new default: mem=16G, cpus=1. Detected run default: mem=62.5G.
7 of 44 exceeding rule(s) ran on the default and need a *new* block; 13 already carry one; 24 have no request data (check manually).

## Rules exceeding the proposed default

`ran on default` = **yes** → needs a new `resources:` block; **no** → already has one; **?** → unknown.

rule | actual RSS | rec mem | rec cpus | ran on default
---- | ---------- | ------- | -------- | --------------
drugchemical_conflation | 56.9G | 96.0G | 1 | yes
geneprotein_conflation | 47.5G | 96.0G | 1 | yes
get_uniprotkb_labels | 40.0G | 64.0G | 1 | yes
check_protein_completeness | 21.1G | 32.0G | 1 | yes
get_chemical_unichem_relationships | 20.9G | 32.0G | 1 | yes
taxon_compendia | 14.0G | 24.0G | 1 | yes
check_chemical_completeness | 13.8G | 24.0G | 1 | yes
export_synonyms_to_duckdb_GeneProteinConflated | 144.0G | 256.0G | 3 | ?
export_synonyms_to_duckdb_Protein | 129.0G | 256.0G | 2 | ?
chembl_labels_and_smiles | 85.0G | 128.0G | 1 | ?
export_synonyms_to_duckdb_DrugChemicalConflated | 84.1G | 128.0G | 3 | ?
export_compendia_to_duckdb_SmallMolecule | 38.8G | 64.0G | 2 | ?
export_compendia_to_duckdb_Protein | 32.2G | 64.0G | 2 | ?
hmdb_labels_and_synonyms | 29.6G | 48.0G | 1 | ?
export_synonyms_to_duckdb_Gene | 28.3G | 48.0G | 3 | ?
export_compendia_to_duckdb_Gene | 24.9G | 48.0G | 3 | ?
export_compendia_to_duckdb_Publication | 19.0G | 32.0G | 3 | ?
export_compendia_to_duckdb_MolecularMixture | 7.6G | 16.0G | 2 | ?
export_synonyms_to_duckdb_OrganismTaxon | 1.3G | 8.0G | 3 | ?
export_synonyms_to_duckdb_umls | 0.9G | 8.0G | 2 | ?
export_conflation_to_duckdb_GeneProtein | 0.9G | 8.0G | 2 | ?
export_synonyms_to_duckdb_Disease | 0.7G | 8.0G | 2 | ?
export_synonyms_to_duckdb_AnatomicalEntity | 0.6G | 8.0G | 2 | ?
export_compendia_to_duckdb_Drug | 0.5G | 8.0G | 2 | ?
export_compendia_to_duckdb_MolecularActivity | 0.5G | 8.0G | 2 | ?
export_compendia_to_duckdb_AnatomicalEntity | 0.5G | 8.0G | 2 | ?
export_compendia_to_duckdb_Disease | 0.5G | 8.0G | 2 | ?
export_compendia_to_duckdb_ChemicalEntity | 0.4G | 8.0G | 2 | ?
export_compendia_to_duckdb_BiologicalProcess | 0.3G | 8.0G | 2 | ?
export_compendia_to_duckdb_Pathway | 0.3G | 8.0G | 2 | ?
export_compendia_to_duckdb_GeneFamily | 0.3G | 8.0G | 2 | ?
protein_compendia | 337.5G | 512.0G | 1 | no
chemical_compendia | 334.5G | 512.0G | 1 | no
gene_compendia | 175.4G | 384.0G | 1 | no
untyped_chemical_compendia | 132.0G | 256.0G | 1 | no
generate_pubmed_compendia | 122.3G | 192.0G | 1 | no
geneprotein_conflated_synonyms | 112.0G | 192.0G | 2 | no
chemical_unichem_concordia | 111.6G | 192.0G | 1 | no
check_for_duplicate_curies | 103.9G | 192.0G | 1 | no
generate_clique_leader_report | 98.7G | 192.0G | 1 | no
generate_curie_report | 94.8G | 192.0G | 1 | no
check_for_identically_labeled_cliques | 63.6G | 96.0G | 1 | no
check_for_duplicate_clique_leaders | 50.8G | 96.0G | 2 | no
generate_pubmed_concords | 32.1G | 64.0G | 1 | no

## All rules (by actual peak RSS)

rule | actual RSS | req mem | mem% | cores | req cpus | wall | rec mem | rec cpus | class
---- | ---------- | ------- | ---- | ----- | -------- | ---- | ------- | -------- | -----
protein_compendia | 337.5G | 500.0G | 67% | 1.0 | 4 | 27384s | 512.0G | 1 | ok
chemical_compendia | 334.5G | 500.0G | 67% | 1.0 | 4 | 18236s | 512.0G | 1 | ok
gene_compendia | 175.4G | 250.0G | 70% | 1.0 | 4 | 14806s | 384.0G | 1 | ok
export_synonyms_to_duckdb_GeneProteinConflated | 144.0G | - | - | 2.0 | - | 978s | 256.0G | 3 | no-request-data
untyped_chemical_compendia | 132.0G | 500.0G | 26% | 0.9 | 4 | 3603s | 256.0G | 1 | ok
export_synonyms_to_duckdb_Protein | 129.0G | - | - | 1.8 | - | 805s | 256.0G | 2 | no-request-data
generate_pubmed_compendia | 122.3G | 125.0G | 98% | 1.0 | 4 | 6384s | 192.0G | 1 | at-risk
geneprotein_conflated_synonyms | 112.0G | 500.0G | 22% | 1.0 | 4 | 18609s | 192.0G | 2 | over
chemical_unichem_concordia | 111.6G | 125.0G | 89% | 0.9 | 4 | 2660s | 192.0G | 1 | at-risk
check_for_duplicate_curies | 103.9G | 1464.8G | 7% | 0.5 | 4 | 694s | 192.0G | 1 | over
generate_clique_leader_report | 98.7G | 1464.8G | 7% | 0.8 | 4 | 309s | 192.0G | 1 | over
generate_curie_report | 94.8G | 1464.8G | 6% | 0.7 | 4 | 434s | 192.0G | 1 | over
chembl_labels_and_smiles | 85.0G | - | - | 0.8 | - | 1727s | 128.0G | 1 | no-request-data
export_synonyms_to_duckdb_DrugChemicalConflated | 84.1G | - | - | 2.5 | - | 541s | 128.0G | 3 | no-request-data
check_for_identically_labeled_cliques | 63.6G | 1464.8G | 4% | 0.5 | 4 | 1237s | 96.0G | 1 | over
drugchemical_conflation | 56.9G | 62.5G | 91% | 0.9 | 4 | 1318s | 96.0G | 1 | at-risk
check_for_duplicate_clique_leaders | 50.8G | 1464.8G | 3% | 1.4 | 4 | 166s | 96.0G | 2 | over
geneprotein_conflation | 47.5G | 62.5G | 76% | 1.0 | 4 | 2633s | 96.0G | 1 | ok
get_uniprotkb_labels | 40.0G | 62.5G | 64% | 0.7 | 4 | 829s | 64.0G | 1 | ok
export_compendia_to_duckdb_SmallMolecule | 38.8G | - | - | 1.2 | - | 6805s | 64.0G | 2 | no-request-data
export_compendia_to_duckdb_Protein | 32.2G | - | - | 1.2 | - | 11186s | 64.0G | 2 | no-request-data
generate_pubmed_concords | 32.1G | 125.0G | 26% | 1.0 | 4 | 63052s | 64.0G | 1 | ok
hmdb_labels_and_synonyms | 29.6G | - | - | 0.9 | - | 628s | 48.0G | 1 | no-request-data
export_synonyms_to_duckdb_Gene | 28.3G | - | - | 2.6 | - | 251s | 48.0G | 3 | no-request-data
export_compendia_to_duckdb_Gene | 24.9G | - | - | 2.0 | - | 3830s | 48.0G | 3 | no-request-data
check_protein_completeness | 21.1G | 62.5G | 34% | 1.0 | 4 | 1222s | 32.0G | 1 | ok
get_chemical_unichem_relationships | 20.9G | 62.5G | 33% | 1.0 | 4 | 955s | 32.0G | 1 | ok
export_compendia_to_duckdb_Publication | 19.0G | - | - | 2.1 | - | 2213s | 32.0G | 3 | no-request-data
taxon_compendia | 14.0G | 62.5G | 22% | 0.9 | 4 | 435s | 24.0G | 1 | over
check_chemical_completeness | 13.8G | 62.5G | 22% | 1.0 | 4 | 867s | 24.0G | 1 | over
leftover_umls | 9.8G | 62.5G | 16% | 1.0 | 4 | 2482s | 16.0G | 1 | over
umls_relationships | 9.3G | 62.5G | 15% | 0.9 | 4 | 192s | 16.0G | 1 | over
disease_compendia | 8.3G | - | - | 0.9 | - | 225s | 16.0G | 1 | no-request-data
get_gene_ncbigene_ensembl_relationships | 7.8G | 62.5G | 13% | 0.8 | 4 | 151s | 16.0G | 1 | over
anatomy_compendia | 7.8G | - | - | 1.0 | - | 323s | 16.0G | 1 | no-request-data
export_compendia_to_duckdb_MolecularMixture | 7.6G | - | - | 2.0 | - | 612s | 16.0G | 2 | no-request-data
geneprotein_uniprot_relationships | 7.6G | 62.5G | 12% | 0.9 | 4 | 1155s | 16.0G | 1 | over
check_gene_completeness | 6.8G | 62.5G | 11% | 1.0 | 4 | 402s | 16.0G | 1 | over
get_mesh_labels | 6.5G | 62.5G | 10% | 0.8 | 4 | 134s | 16.0G | 1 | over
get_chemical_mesh_relationships | 6.4G | 62.5G | 10% | 0.7 | 4 | 106s | 16.0G | 1 | over
taxon_mesh_ids | 6.3G | 62.5G | 10% | 0.7 | 4 | 105s | 16.0G | 1 | over
get_gene_ncbigene_relationships | 6.3G | 62.5G | 10% | 0.8 | 4 | 253s | 16.0G | 1 | over
chemical_mesh_ids | 6.3G | 62.5G | 10% | 0.8 | 4 | 128s | 16.0G | 1 | over
anatomy_mesh_ids | 6.2G | 62.5G | 10% | 0.7 | 4 | 109s | 16.0G | 1 | over
get_taxon_relationships | 6.1G | 62.5G | 10% | 0.7 | 4 | 114s | 16.0G | 1 | over
disease_mesh_ids | 6.0G | 62.5G | 10% | 0.7 | 4 | 113s | 16.0G | 1 | over
process_compendia | 5.7G | - | - | 0.9 | - | 221s | 16.0G | 1 | no-request-data
check_publications_completeness | 4.6G | 62.5G | 7% | 0.9 | 4 | 272s | 8.0G | 1 | over
get_umls_labels_and_synonyms | 3.7G | 62.5G | 6% | 0.8 | 4 | 63s | 8.0G | 1 | over
get_anatomy_obo_relationships | 3.2G | 62.5G | 5% | 0.6 | 4 | 90s | 8.0G | 1 | over
get_mods | 3.1G | 7.8G | 40% | 0.7 | 1 | 18s | 8.0G | 1 | ok
cell_line_compendia | 2.9G | 62.5G | 5% | 1.0 | 4 | 49s | 8.0G | 1 | over
genefamily_compendia | 2.9G | - | - | 0.9 | - | 48s | 8.0G | 1 | no-request-data
anatomy_uberon_ids | 2.8G | 62.5G | 5% | 0.3 | 4 | 129s | 8.0G | 1 | over
get_mods_labels | 2.2G | 62.5G | 4% | 0.6 | 4 | 22s | 8.0G | 1 | over
macromolecular_complex_compendia | 2.1G | 62.5G | 3% | 0.8 | 4 | 50s | 8.0G | 1 | over
get_chebi_concord | 2.0G | 62.5G | 3% | 0.1 | 4 | 23s | 8.0G | 1 | over
get_obo_synonyms | 2.0G | 7.8G | 25% | 0.1 | 1 | 748s | 8.0G | 1 | ok
get_disease_efo_relationships | 1.8G | 62.5G | 3% | 0.7 | 4 | 23s | 8.0G | 1 | over
disease_efo_ids | 1.7G | 62.5G | 3% | 0.7 | 4 | 22s | 8.0G | 1 | over
get_EFO_labels | 1.7G | 62.5G | 3% | 0.7 | 4 | 24s | 8.0G | 1 | over
ncbitaxon_labels_and_synonyms | 1.7G | 62.5G | 3% | 1.0 | 4 | 47s | 8.0G | 1 | over
get_obo_labels | 1.6G | 7.8G | 20% | 0.1 | 1 | 675s | 8.0G | 1 | ok
taxon_umls_ids | 1.6G | 62.5G | 3% | 0.9 | 4 | 12s | 8.0G | 1 | over
chemical_umls_ids | 1.6G | 62.5G | 3% | 0.9 | 4 | 13s | 8.0G | 1 | over
disease_umls_ids | 1.5G | 62.5G | 2% | 0.9 | 4 | 12s | 8.0G | 1 | over
anatomy_umls_ids | 1.5G | 62.5G | 2% | 0.9 | 4 | 11s | 8.0G | 1 | over
process_umls_ids | 1.4G | 62.5G | 2% | 0.7 | 4 | 11s | 8.0G | 1 | over
export_synonyms_to_duckdb_OrganismTaxon | 1.3G | - | - | 2.2 | - | 11s | 8.0G | 3 | no-request-data
protein_umls_ids | 1.3G | 62.5G | 2% | 0.8 | 4 | 29s | 8.0G | 1 | over
export_compendia_to_duckdb_OrganismTaxon | 1.2G | - | - | 0.9 | - | 155s | 8.0G | 1 | no-request-data
get_process_rhea_relationships | 1.1G | 62.5G | 2% | 0.9 | 4 | 11s | 8.0G | 1 | over
get_rhea_labels | 1.1G | 62.5G | 2% | 0.8 | 4 | 12s | 8.0G | 1 | over
export_synonyms_to_duckdb_umls | 0.9G | - | - | 1.7 | - | 8s | 8.0G | 2 | no-request-data
rxnorm_relationships | 0.9G | 62.5G | 1% | 0.9 | 4 | 17s | 8.0G | 1 | over
export_conflation_to_duckdb_GeneProtein | 0.9G | - | - | 1.8 | - | 30s | 8.0G | 2 | no-request-data
chemical_chembl_ids | 0.8G | - | - | 0.9 | - | 6s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_Disease | 0.7G | - | - | 1.3 | - | 6s | 8.0G | 2 | no-request-data
get_ncbitaxon | 0.7G | 7.8G | 9% | 0.2 | 1 | 19s | 8.0G | 1 | ok
export_compendia_to_duckdb_umls | 0.7G | - | - | 0.8 | - | 55s | 8.0G | 1 | no-request-data
drugchemical_conflated_synonyms | 0.7G | 62.5G | 1% | 1.0 | 4 | 9937s | 8.0G | 1 | over
get_obo_descriptions | 0.7G | 7.8G | 8% | 0.0 | 1 | 342s | 8.0G | 1 | ok
generate_kgx_Protein | 0.7G | - | - | 1.0 | - | 6874s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_AnatomicalEntity | 0.6G | - | - | 1.1 | - | 3s | 8.0G | 2 | no-request-data
check_taxon_completeness | 0.6G | 62.5G | 1% | 0.8 | 4 | 18s | 8.0G | 1 | over
export_synonyms_to_duckdb_MolecularActivity | 0.5G | - | - | 0.7 | - | 3s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_Drug | 0.5G | - | - | 1.9 | - | 12s | 8.0G | 2 | no-request-data
generate_kgx_MolecularMixture | 0.5G | - | - | 1.0 | - | 1100s | 8.0G | 1 | no-request-data
get_CLO_labels | 0.5G | 62.5G | 1% | 0.6 | 4 | 3s | 8.0G | 1 | over
get_clo_ids | 0.5G | 62.5G | 1% | 0.6 | 4 | 3s | 8.0G | 1 | over
generate_kgx_SmallMolecule | 0.5G | - | - | 1.0 | - | 9699s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_MolecularActivity | 0.5G | - | - | 1.1 | - | 10s | 8.0G | 2 | no-request-data
generate_kgx_Publication | 0.5G | - | - | 1.0 | - | 4169s | 8.0G | 1 | no-request-data
get_icrdf | 0.5G | 62.5G | 1% | 0.2 | 4 | 251s | 8.0G | 1 | over
export_compendia_to_duckdb_AnatomicalEntity | 0.5G | - | - | 1.8 | - | 8s | 8.0G | 2 | no-request-data
export_compendia_to_duckdb_Disease | 0.5G | - | - | 1.3 | - | 24s | 8.0G | 2 | no-request-data
generate_kgx_Disease | 0.5G | - | - | 0.5 | - | 40s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_ChemicalEntity | 0.4G | - | - | 1.1 | - | 23s | 8.0G | 2 | no-request-data
export_synonyms_to_duckdb_BiologicalProcess | 0.4G | - | - | 0.9 | - | 2s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_PhenotypicFeature | 0.4G | - | - | 0.7 | - | 2s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_PhenotypicFeature | 0.4G | - | - | 0.9 | - | 4s | 8.0G | 1 | no-request-data
verify_pubmed | 0.4G | - | - | 0.3 | - | 586s | 8.0G | 1 | no-request-data
get_chemical_pubchem_mesh_concord | 0.4G | 62.5G | 1% | 0.4 | 4 | 2s | 8.0G | 1 | over
generate_kgx_ChemicalEntity | 0.4G | - | - | 1.0 | - | 18s | 8.0G | 1 | no-request-data
get_chemical_umls_relationships | 0.4G | 62.5G | 1% | 0.8 | 4 | 35s | 8.0G | 1 | over
generate_kgx_AnatomicalEntity | 0.4G | - | - | 0.9 | - | 11s | 8.0G | 1 | no-request-data
export_conflation_to_duckdb_DrugChemical | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_MacromolecularComplex | 0.3G | - | - | 0.4 | - | 2s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_BiologicalProcess | 0.3G | - | - | 1.3 | - | 3s | 8.0G | 2 | no-request-data
export_compendia_to_duckdb_GrossAnatomicalStructure | 0.3G | - | - | 0.5 | - | 1s | 8.0G | 1 | no-request-data
generate_kgx_Gene | 0.3G | - | - | 1.0 | - | 2950s | 8.0G | 1 | no-request-data
get_hgnc_labels_and_synonyms | 0.3G | 62.5G | 1% | 0.0 | 4 | 1s | 8.0G | 1 | over
export_compendia_to_duckdb_Pathway | 0.3G | - | - | 1.4 | - | 3s | 8.0G | 2 | no-request-data
get_chebi | 0.3G | 7.8G | 4% | 0.0 | 1 | 219s | 8.0G | 1 | ok
get_disease_obo_relationships | 0.3G | 62.5G | 1% | 0.2 | 4 | 14s | 8.0G | 1 | over
generate_kgx_Drug | 0.3G | - | - | 1.0 | - | 13s | 8.0G | 1 | no-request-data
get_disease_umls_relationships | 0.3G | 62.5G | 1% | 0.7 | 4 | 36s | 8.0G | 1 | over
export_compendia_to_duckdb_GeneFamily | 0.3G | - | - | 1.1 | - | 2s | 8.0G | 2 | no-request-data
get_protein_pr_uniprotkb_relationships | 0.3G | 62.5G | 0% | 0.0 | 4 | 22s | 8.0G | 1 | over
generate_kgx_OrganismTaxon | 0.3G | - | - | 0.7 | - | 109s | 8.0G | 1 | no-request-data
get_taxon_umls_relationships | 0.3G | 62.5G | 0% | 0.8 | 4 | 35s | 8.0G | 1 | over
generate_kgx_MolecularActivity | 0.3G | - | - | 0.9 | - | 6s | 8.0G | 1 | no-request-data
get_ensembl | 0.3G | 7.8G | 4% | 0.0 | 1 | 198s | 8.0G | 1 | ok
generate_kgx_umls | 0.3G | - | - | 0.7 | - | 32s | 8.0G | 1 | no-request-data
generate_kgx_PhenotypicFeature | 0.3G | - | - | 0.9 | - | 4s | 8.0G | 1 | no-request-data
get_EC_labels | 0.3G | 62.5G | 0% | 0.4 | 4 | 1s | 8.0G | 1 | over
export_synonyms_to_duckdb_Pathway | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_anatomy_umls_relationships | 0.3G | 62.5G | 0% | 0.8 | 4 | 34s | 8.0G | 1 | over
export_synonyms_to_duckdb_GrossAnatomicalStructure | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
process_ec_ids | 0.3G | 62.5G | 0% | 0.3 | 4 | 1s | 8.0G | 1 | over
get_protein_umls_relationships | 0.3G | 62.5G | 0% | 1.0 | 4 | 33s | 8.0G | 1 | over
protein_pr_ids | 0.3G | 62.5G | 0% | 0.3 | 4 | 6s | 8.0G | 1 | over
export_synonyms_to_duckdb_CellularComponent | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_Cell | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_CellLine | 0.3G | - | - | 0.5 | - | 2s | 8.0G | 1 | no-request-data
generate_kgx_BiologicalProcess | 0.3G | - | - | 0.5 | - | 2s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_CellularComponent | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_GeneFamily | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
export_synonyms_to_duckdb_CellLine | 0.3G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_reactome | 0.3G | 7.8G | 3% | 0.0 | 1 | 22s | 8.0G | 1 | ok
export_compendia_to_duckdb_Cell | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_disease_completeness | 0.2G | - | - | 0.5 | - | 3s | 8.0G | 1 | no-request-data
generate_kgx_Pathway | 0.2G | - | - | 0.4 | - | 1s | 8.0G | 1 | no-request-data
chemical_chebi_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 22s | 8.0G | 1 | over
export_synonyms_to_duckdb_MacromolecularComplex | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_DrugChemicalConflated.txt | 0.2G | - | - | 1.0 | - | 5724s | 8.0G | 1 | no-request-data
get_process_umls_relationships | 0.2G | 62.5G | 0% | 1.0 | 4 | 33s | 8.0G | 1 | over
get_mesh | 0.2G | 7.8G | 3% | 0.0 | 1 | 42s | 8.0G | 1 | ok
check_process_completeness | 0.2G | - | - | 0.4 | - | 2s | 8.0G | 1 | no-request-data
generate_kgx_GrossAnatomicalStructure | 0.2G | - | - | 0.4 | - | 2s | 8.0G | 1 | no-request-data
get_gene_umls_relationships | 0.2G | 62.5G | 0% | 0.9 | 4 | 32s | 8.0G | 1 | over
generate_kgx_CellLine | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
process_go_ids | 0.2G | 62.5G | 0% | 0.2 | 4 | 1s | 8.0G | 1 | over
get_protein_ncit_umls_relationships | 0.2G | 62.5G | 0% | 0.8 | 4 | 34s | 8.0G | 1 | over
pubchem_rxnorm_annotations | 0.2G | 62.5G | 0% | 0.1 | 4 | 14s | 8.0G | 1 | over
disease_ncit_ids | 0.2G | 62.5G | 0% | 0.1 | 4 | 13s | 8.0G | 1 | over
generate_kgx_GeneFamily | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
unii_labels_and_synonyms | 0.2G | 62.5G | 0% | 0.4 | 4 | 2s | 8.0G | 1 | over
gene_hgnc_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
generate_kgx_Cell | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_complexportal_labels_and_synonyms | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
anatomy_ncit_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_uniprotkb_sprot | 0.2G | 7.8G | 3% | 0.6 | 1 | 5s | 8.0G | 1 | ok
get_pubchem_structures | 0.2G | 7.8G | 3% | 0.1 | 1 | 113s | 8.0G | 1 | ok
gene_umls_ids | 0.2G | 62.5G | 0% | 1.0 | 4 | 27s | 8.0G | 1 | over
get_complexportal | 0.2G | 7.8G | 3% | 0.0 | 1 | 25s | 8.0G | 1 | ok
generate_kgx_CellularComponent | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_unichem | 0.2G | 7.8G | 3% | 0.1 | 1 | 6646s | 8.0G | 1 | ok
get_uniprotkb_trembl | 0.2G | 7.8G | 3% | 0.7 | 1 | 1902s | 8.0G | 1 | ok
protein_ensembl_ids | 0.2G | - | - | 1.0 | - | 21s | 8.0G | 1 | no-request-data
get_pubchem | 0.2G | 7.8G | 3% | 0.2 | 1 | 25s | 8.0G | 1 | ok
get_chemical_rxnorm_relationships | 0.2G | 62.5G | 0% | 0.0 | 4 | 2s | 8.0G | 1 | over
get_uniprotkb_idmapping | 0.2G | 7.8G | 3% | 0.7 | 1 | 1042s | 8.0G | 1 | ok
disease_hp_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 7s | 8.0G | 1 | over
download_unichem_structure | 0.2G | - | - | 0.2 | - | 1996s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_GeneProteinConflated.txt | 0.2G | - | - | 1.0 | - | 8207s | 8.0G | 1 | no-request-data
get_process_go_relationships | 0.2G | 62.5G | 0% | 0.1 | 4 | 5s | 8.0G | 1 | over
gene | 0.2G | 62.5G | 0% | 1.0 | 4 | 3252s | 8.0G | 1 | over
gene_ensembl_ids | 0.2G | - | - | 1.0 | - | 21s | 8.0G | 1 | no-request-data
anatomy_go_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
protein | 0.2G | 62.5G | 0% | 1.0 | 6 | 7693s | 8.0G | 1 | over
get_drugcentral | 0.2G | 7.8G | 3% | 0.0 | 1 | 1s | 8.0G | 1 | ok
generate_sapbert_training_data_BiologicalProcess.txt | 0.2G | - | - | 0.8 | - | 4s | 8.0G | 1 | no-request-data
check_disease | 0.2G | - | - | 0.4 | - | 3s | 8.0G | 1 | no-request-data
chemical | 0.2G | 62.5G | 0% | 1.0 | 4 | 6664s | 8.0G | 1 | over
generate_sapbert_training_data_CellLine.txt | 0.2G | - | - | 0.4 | - | 1s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_GeneFamily.txt | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
filter_unichem | 0.2G | 62.5G | 0% | 0.9 | 4 | 192s | 8.0G | 1 | over
get_protein_uniprotkb_ensembl_relationships | 0.2G | 62.5G | 0% | 1.0 | 4 | 1092s | 8.0G | 1 | over
generate_sapbert_training_data_Protein.txt | 0.2G | - | - | 1.0 | - | 6285s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_SmallMolecule | 0.2G | 62.5G | 0% | 1.0 | 4 | 1086s | 8.0G | 1 | over
check_small_molecule | 0.2G | 62.5G | 0% | 1.0 | 4 | 883s | 8.0G | 1 | over
generate_sapbert_training_data_Gene.txt | 0.2G | - | - | 1.0 | - | 2186s | 8.0G | 1 | no-request-data
get_ncbigene_labels_synonyms_and_taxa | 0.2G | 62.5G | 0% | 1.0 | 4 | 604s | 8.0G | 1 | over
generate_content_report_for_compendium_MolecularActivity | 0.2G | - | - | 0.0 | - | 2s | 8.0G | 1 | no-request-data
keggcompound_labels | 0.2G | 62.5G | 0% | 0.0 | 4 | 420s | 8.0G | 1 | over
process | 0.2G | - | - | 0.9 | - | 12s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_Disease.txt | 0.2G | - | - | 0.7 | - | 23s | 8.0G | 1 | no-request-data
get_chemical_pubchem_cas_concord | 0.2G | 62.5G | 0% | 0.9 | 4 | 92s | 8.0G | 1 | over
check_activity | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
download_pubmed | 0.2G | 7.8G | 3% | 0.0 | 1 | 11059s | 8.0G | 1 | ok
generate_sapbert_training_data_Cell.txt | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
anatomy_cl_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
generate_sapbert_training_data_AnatomicalEntity.txt | 0.2G | - | - | 0.9 | - | 7s | 8.0G | 1 | no-request-data
chemical_rxnorm_ids | 0.2G | 62.5G | 0% | 0.3 | 4 | 2s | 8.0G | 1 | over
chemical_pubchem_ids | 0.2G | 62.5G | 0% | 1.0 | 4 | 324s | 8.0G | 1 | over
generate_sapbert_training_data_GrossAnatomicalStructure.txt | 0.2G | - | - | 0.4 | - | 1s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_MolecularActivity.txt | 0.2G | - | - | 0.9 | - | 8s | 8.0G | 1 | no-request-data
anatomy | 0.2G | - | - | 0.9 | - | 8s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_PhenotypicFeature.txt | 0.2G | - | - | 0.8 | - | 3s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_umls.txt | 0.2G | - | - | 0.8 | - | 60s | 8.0G | 1 | no-request-data
check_gene | 0.2G | 62.5G | 0% | 0.9 | 4 | 505s | 8.0G | 1 | over
genefamily | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_OrganismTaxon.txt | 0.2G | - | - | 0.8 | - | 94s | 8.0G | 1 | no-request-data
pubchem_labels | 0.2G | 62.5G | 0% | 1.0 | 4 | 259s | 8.0G | 1 | over
chemical_unii_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
pubchem_synonyms | 0.2G | 62.5G | 0% | 0.8 | 4 | 162s | 8.0G | 1 | over
get_chemical_wikipedia_relationships | 0.2G | 62.5G | 0% | 0.0 | 4 | 2s | 8.0G | 1 | over
check_publications | 0.2G | 62.5G | 0% | 0.9 | 4 | 337s | 8.0G | 1 | over
cell_line | 0.2G | 62.5G | 0% | 0.4 | 4 | 1s | 8.0G | 1 | over
compress_umls | 0.2G | 62.5G | 0% | 0.3 | 4 | 44s | 8.0G | 1 | over
taxon | 0.2G | 62.5G | 0% | 1.0 | 4 | 137s | 8.0G | 1 | over
disease | 0.2G | - | - | 0.7 | - | 21s | 8.0G | 1 | no-request-data
check_chemical_entity | 0.2G | 62.5G | 0% | 0.6 | 4 | 2s | 8.0G | 1 | over
generate_content_report_for_compendium_MolecularMixture | 0.2G | 62.5G | 0% | 0.8 | 4 | 119s | 8.0G | 1 | over
check_molecular_mixture | 0.2G | 62.5G | 0% | 0.9 | 4 | 96s | 8.0G | 1 | over
get_SMPDB_labels | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
check_protein | 0.2G | 62.5G | 0% | 1.0 | 4 | 1337s | 8.0G | 1 | over
generate_prefix_table | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_sapbert_training_data_Pathway.txt | 0.2G | - | - | 0.7 | - | 2s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Publication | 0.2G | 62.5G | 0% | 1.0 | 4 | 414s | 8.0G | 1 | over
generate_content_report_for_compendium_Protein | 0.2G | 62.5G | 0% | 1.0 | 4 | 1692s | 8.0G | 1 | over
generate_sapbert_training_data_MacromolecularComplex.txt | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
chemical_drugbank_ids | 0.2G | 62.5G | 0% | 0.6 | 4 | 46s | 8.0G | 1 | over
macromolecular_complex | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
check_anatomical_entity | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
extract_taxon_ids_from_uniprotkb | 0.2G | 62.5G | 0% | 1.0 | 4 | 1072s | 8.0G | 1 | over
generate_content_report_for_compendium_Disease | 0.2G | - | - | 0.4 | - | 4s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_ChemicalEntity | 0.2G | 62.5G | 0% | 0.4 | 4 | 3s | 8.0G | 1 | over
download_unichem_reference | 0.2G | - | - | 0.1 | - | 382s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Drug | 0.2G | 62.5G | 0% | 0.0 | 4 | 2s | 8.0G | 1 | over
generate_content_report_for_compendium_umls | 0.2G | 62.5G | 0% | 0.4 | 4 | 10s | 8.0G | 1 | over
check_drug | 0.2G | 62.5G | 0% | 0.0 | 4 | 2s | 8.0G | 1 | over
get_wikidata_cell_relationships | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
generate_content_report_for_compendium_OrganismTaxon | 0.2G | 62.5G | 0% | 0.9 | 4 | 29s | 8.0G | 1 | over
check_taxon | 0.2G | 62.5G | 0% | 1.0 | 4 | 22s | 8.0G | 1 | over
generate_content_report_for_compendium_Gene | 0.2G | 62.5G | 0% | 1.0 | 4 | 625s | 8.0G | 1 | over
check_polypeptide | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
export_compendia_to_duckdb_Polypeptide | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_mapping_sources_table | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
export_compendia_to_duckdb_ComplexMolecularMixture | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_unii | 0.2G | 7.8G | 3% | 0.2 | 1 | 9s | 8.0G | 1 | ok
gene_mods_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_omim | 0.2G | 7.8G | 3% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_content_report_for_compendium_GrossAnatomicalStructure | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Pathway | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_conflation_files | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_gtopdb_inchikey_concord | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_rhea | 0.2G | 7.8G | 2% | 0.5 | 1 | 4s | 8.0G | 1 | ok
check_genefamily_completeness | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_chembl | 0.2G | 7.8G | 2% | 0.1 | 1 | 981s | 8.0G | 1 | ok
generate_kgx_ComplexMolecularMixture | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_orphanet | 0.2G | 7.8G | 2% | 0.0 | 1 | 9s | 8.0G | 1 | ok
get_EFO | 0.2G | 7.8G | 2% | 0.2 | 1 | 5s | 8.0G | 1 | ok
generate_content_report_for_compendium_BiologicalProcess | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_SMPDB | 0.2G | 7.8G | 2% | 0.3 | 1 | 2s | 8.0G | 1 | ok
check_cellular_component | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_doid | 0.2G | 7.8G | 2% | 0.0 | 1 | 3s | 8.0G | 1 | ok
generate_content_report_for_compendium_GeneFamily | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_AnatomicalEntity | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_pathway | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
export_compendia_to_duckdb_ChemicalMixture | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_process | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_chemical_drugcentral_relationships | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_cliques_table | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_macromolecular_complex | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_doid_labels_and_synonyms | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_cell_line_completeness | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
pubchem_rxnorm_relationships | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_gross_anatomical_structure | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
download_rxnorm | 0.2G | 7.8G | 2% | 0.1 | 1 | 40s | 8.0G | 1 | ok
generate_content_report_for_compendium_Cell | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_cell_line | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
disease_manual_concord | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
process_reactome_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
disease_mondo_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
check_synonyms_gzipped_files | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_compendia_files | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_hgncfamily_labels | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_genefamily | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_orphanet_labels_and_synonyms | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
check_macromolecular_complex_completeness | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_anatomy_completeness | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
chemical_gtopdb_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_omim_labels | 0.2G | 1.0G | 20% | 0.0 | 1 | 0s | 8.0G | 1 | ok
get_umls_gene_protein_mappings | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_ncbigene | 0.2G | 7.8G | 2% | 0.1 | 1 | 42s | 8.0G | 1 | ok
get_clo | 0.2G | 7.8G | 2% | 0.0 | 1 | 1s | 8.0G | 1 | ok
get_pantherfamily_labels | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Polypeptide | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_phenotypic_feature | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_MacromolecularComplex | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_panther_pathway_labels | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_protein_ncit_uniprotkb_relationships | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_kgx_MacromolecularComplex | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
generate_sapbert_training_data_CellularComponent.txt | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
chemical_hmdb_ids | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_chemical_mixture | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_content_report_for_compendium_CellularComponent | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
gtopdb_labels_and_synonyms | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
generate_content_report_for_compendium_CellLine | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_hgncfamily | 0.2G | 7.8G | 2% | 0.0 | 1 | 1s | 8.0G | 1 | ok
generate_summary_content_report_for_compendia | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_content_report_for_compendium_ComplexMolecularMixture | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
download_umls | 0.2G | 7.8G | 2% | 0.5 | 1 | 906s | 8.0G | 1 | ok
generate_content_report_for_compendium_ChemicalMixture | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
chemical_drugcentral_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
gene_omim_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_content_report_for_compendium_PhenotypicFeature | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_hgnc | 0.2G | 7.8G | 2% | 0.0 | 1 | 1s | 8.0G | 1 | ok
get_gtopdb | 0.2G | 7.8G | 2% | 0.0 | 1 | 5s | 8.0G | 1 | ok
get_reactome_labels | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_EC | 0.2G | 7.8G | 2% | 0.0 | 1 | 1s | 8.0G | 1 | ok
get_disease_doid_relationships | 0.2G | 62.5G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_gene_medgen_relationships | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_kgx_Polypeptide | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_cell | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_pantherfamily | 0.2G | 7.8G | 2% | 0.0 | 1 | 131s | 8.0G | 1 | ok
disease_omim_ids | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_panther_pathways | 0.2G | 7.8G | 2% | 0.1 | 1 | 7s | 8.0G | 1 | ok
get_ncit | 0.2G | 7.8G | 2% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_kgx_ChemicalMixture | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_complex_mixture | 0.2G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
taxon_ncbi_ids | 0.0G | 62.5G | 0% | 0.3 | 4 | 2s | 8.0G | 1 | over
gene_ncbi_ids | 0.0G | 62.5G | 0% | 0.6 | 4 | 24s | 8.0G | 1 | over
protein_uniprotkb_ids | 0.0G | 62.5G | 0% | 0.9 | 4 | 81s | 8.0G | 1 | over
genefamily_pantherfamily_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
chemical_kegg_ids | 0.0G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
disease_doid_ids | 0.0G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
disease_orphanet_ids | 0.0G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
genefamily_hgncfamily_ids | 0.0G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
process_rhea_ids | 0.0G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
process_smpdb_ids | 0.0G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
macromolecular_complex_ids | 0.0G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
process_panther_ids | 0.0G | 62.5G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
