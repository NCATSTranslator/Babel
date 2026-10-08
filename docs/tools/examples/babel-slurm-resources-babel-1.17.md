<!--
Captured example of babel-slurm-resources output, regenerate with:
  uv run babel-slurm-resources data/babel-1.17/babel_outputs
See docs/tools/Resources.md for how to read it. This is the analysis behind the resource
tuning in slurm/config.yaml and the per-rule overrides in src/snakefiles/.
The declared side (runtime limits, `mem` blocks) is whatever the checkout that regenerated this
was carrying, so a re-capture after a sizing pass scores the run against limits it never had --
see "Two ways the declared side can be wrong" in Resources.md.
-->

> _Example output of `babel-slurm-resources` on the full babel-1.17 run — the analysis behind
> the SLURM defaults in `slurm/config.yaml` and the per-rule overrides. Regenerate with_
> `uv run babel-slurm-resources data/babel-1.17/babel_outputs`. _See
> [Resources.md](../Resources.md) to read it._

# SLURM resource analysis

Rules with benchmarks: 263  |  over-provisioned: 172  |  at-risk: 3  |  no request data: 39
Wasted reservation (requested minus used): 19755 GB across rules with a known request.

Proposed new default: mem=16G, cpus=1. Detected run default: mem=64.0G.
8 of 25 exceeding rule(s) ran on the default and need a *new* block; 17 already carry one.

## Rules exceeding the proposed default

`ran on default` = **yes** → needs a new `resources:` block; **no** → already has one; **?** → unknown.

rule | actual RSS | rec mem | rec cpus | ran on default
---- | ---------- | ------- | -------- | --------------
drugchemical_conflation | 61.1G | 96.0G | 1 | yes
geneprotein_conflation | 51.0G | 96.0G | 1 | yes
get_uniprotkb_labels | 43.0G | 96.0G | 1 | yes
check_protein_completeness | 22.6G | 48.0G | 1 | yes
get_chemical_unichem_relationships | 22.5G | 48.0G | 1 | yes
taxon_compendia | 15.0G | 24.0G | 1 | yes
check_chemical_completeness | 14.8G | 24.0G | 1 | yes
export_conflation_to_duckdb (×2) | 1.0G | 8.0G | 2 | yes
protein_compendia | 362.4G | 768.0G | 1 | no
chemical_compendia | 359.1G | 768.0G | 1 | no
gene_compendia | 188.4G | 384.0G | 1 | no
export_synonyms_to_duckdb (×18) | 154.6G | 256.0G | 3 | no
untyped_chemical_compendia | 141.8G | 256.0G | 1 | no
generate_pubmed_compendia | 131.3G | 256.0G | 1 | no
geneprotein_conflated_synonyms | 120.3G | 192.0G | 2 | no
chemical_unichem_concordia | 119.8G | 192.0G | 1 | no
check_for_duplicate_curies | 111.6G | 192.0G | 1 | no
generate_clique_leader_report | 106.0G | 192.0G | 1 | no
generate_curie_report | 101.8G | 192.0G | 1 | no
chembl_labels_and_smiles | 91.2G | 192.0G | 1 | no
check_for_identically_labeled_cliques | 68.3G | 128.0G | 1 | no
check_for_duplicate_clique_leaders | 54.6G | 96.0G | 2 | no
export_compendia_to_duckdb (×24) | 41.7G | 64.0G | 3 | no
generate_pubmed_concords | 34.5G | 64.0G | 1 | no
hmdb_labels_and_synonyms | 31.8G | 48.0G | 1 | no

## Runtime fit

Wall time against the declared `runtime` limit (from the rule's log, else its snakefile, else the cluster default). **at-risk** rules are close to being killed; **over** rules have a limit at least twice what they need, which makes Snakemake's remaining-time estimate useless and hides a job that has become pathologically slow.

Rules at risk of timing out: 3  |  declaring more time than they need: 7
243 rules ran on the default runtime; the slowest was `get_unichem` at 1.8h, so the 2.0h default is too tight and should rise to 3.0h — at that value none of them is at risk.

rule | wall | limit | wall% | rec runtime | class
---- | ---- | ----- | ----- | ----------- | -----
download_pubmed | 3.1h | 2.0h | 154% | 6.0h | at-risk
get_unichem | 1.8h | 2.0h | 92% | 3.0h | at-risk
geneprotein_conflated_synonyms | 5.2h | 6.0h | 86% | 8.0h | at-risk
export_synonyms_to_duckdb (×18) | 16m | 60m | 27% | 30m | over
download_unichem_structure | 33m | 4.0h | 14% | 60m | over
download_unichem_reference | 6m | 60m | 11% | 30m | over
get_uniprotkb_trembl | 32m | 6.0h | 9% | 60m | over
get_uniprotkb_idmapping | 17m | 6.0h | 5% | 30m | over
download_umls | 15m | 6.0h | 4% | 30m | over
get_ensembl | 3m | 6.0h | 1% | 30m | over

## All rules (by actual peak RSS)

rule | actual RSS | req mem | mem% | cores | req cpus | wall | rec mem | rec cpus | class
---- | ---------- | ------- | ---- | ----- | -------- | ---- | ------- | -------- | -----
protein_compendia | 362.4G | 512.0G | 71% | 1.0 | 4 | 27384s | 768.0G | 1 | ok
chemical_compendia | 359.1G | 512.0G | 70% | 1.0 | 4 | 18236s | 768.0G | 1 | ok
gene_compendia | 188.4G | 256.0G | 74% | 1.0 | 4 | 14806s | 384.0G | 1 | ok
export_synonyms_to_duckdb (×18) | 154.6G | 512.0G | 30% | 2.6 | 4 | 978s | 256.0G | 3 | over
untyped_chemical_compendia | 141.8G | 512.0G | 28% | 0.9 | 4 | 3603s | 256.0G | 1 | over
generate_pubmed_compendia | 131.3G | 128.0G | 103% | 1.0 | 4 | 6384s | 256.0G | 1 | at-risk
geneprotein_conflated_synonyms | 120.3G | 512.0G | 23% | 1.0 | 4 | 18609s | 192.0G | 2 | over
chemical_unichem_concordia | 119.8G | 128.0G | 94% | 0.9 | 4 | 2660s | 192.0G | 1 | at-risk
check_for_duplicate_curies | 111.6G | 1500.0G | 7% | 0.5 | 4 | 694s | 192.0G | 1 | over
generate_clique_leader_report | 106.0G | 1500.0G | 7% | 0.8 | 4 | 309s | 192.0G | 1 | over
generate_curie_report | 101.8G | 1500.0G | 7% | 0.7 | 4 | 434s | 192.0G | 1 | over
chembl_labels_and_smiles | 91.2G | 128.0G | 71% | 0.8 | - | 1727s | 192.0G | 1 | ok
check_for_identically_labeled_cliques | 68.3G | 1500.0G | 5% | 0.5 | 4 | 1237s | 128.0G | 1 | over
drugchemical_conflation | 61.1G | 64.0G | 96% | 0.9 | 4 | 1318s | 96.0G | 1 | at-risk
check_for_duplicate_clique_leaders | 54.6G | 1500.0G | 4% | 1.4 | 4 | 166s | 96.0G | 2 | over
geneprotein_conflation | 51.0G | 64.0G | 80% | 1.0 | 4 | 2633s | 96.0G | 1 | ok
get_uniprotkb_labels | 43.0G | 64.0G | 67% | 0.7 | 4 | 829s | 96.0G | 1 | ok
export_compendia_to_duckdb (×24) | 41.7G | 512.0G | 8% | 2.1 | 4 | 11186s | 64.0G | 3 | over
generate_pubmed_concords | 34.5G | 128.0G | 27% | 1.0 | 4 | 63052s | 64.0G | 1 | over
hmdb_labels_and_synonyms | 31.8G | 48.0G | 66% | 0.9 | - | 628s | 48.0G | 1 | ok
check_protein_completeness | 22.6G | 64.0G | 35% | 1.0 | 4 | 1222s | 48.0G | 1 | ok
get_chemical_unichem_relationships | 22.5G | 64.0G | 35% | 1.0 | 4 | 955s | 48.0G | 1 | ok
taxon_compendia | 15.0G | 64.0G | 23% | 0.9 | 4 | 435s | 24.0G | 1 | over
check_chemical_completeness | 14.8G | 64.0G | 23% | 1.0 | 4 | 867s | 24.0G | 1 | over
umls_relationships | 9.9G | 64.0G | 16% | 0.9 | 4 | 192s | 16.0G | 1 | over
leftover_umls | 9.8G | 64.0G | 15% | 1.0 | 4 | 2292s | 16.0G | 1 | over
disease_compendia | 8.9G | - | - | 0.9 | - | 225s | 16.0G | 1 | no-request-data
get_gene_ncbigene_ensembl_relationships | 8.4G | 64.0G | 13% | 0.8 | 4 | 151s | 16.0G | 1 | over
anatomy_compendia | 8.4G | - | - | 1.0 | - | 323s | 16.0G | 1 | no-request-data
geneprotein_uniprot_relationships | 8.1G | 64.0G | 13% | 0.9 | 4 | 1155s | 16.0G | 1 | over
check_gene_completeness | 7.3G | 64.0G | 11% | 1.0 | 4 | 402s | 16.0G | 1 | over
get_mesh_labels | 6.9G | 64.0G | 11% | 0.8 | 4 | 134s | 16.0G | 1 | over
get_chemical_mesh_relationships | 6.8G | 64.0G | 11% | 0.7 | 4 | 106s | 16.0G | 1 | over
taxon_mesh_ids | 6.8G | 64.0G | 11% | 0.7 | 4 | 105s | 16.0G | 1 | over
get_gene_ncbigene_relationships | 6.8G | 64.0G | 11% | 0.8 | 4 | 253s | 16.0G | 1 | over
chemical_mesh_ids | 6.8G | 64.0G | 11% | 0.8 | 4 | 128s | 16.0G | 1 | over
anatomy_mesh_ids | 6.7G | 64.0G | 10% | 0.7 | 4 | 109s | 16.0G | 1 | over
get_taxon_relationships | 6.5G | 64.0G | 10% | 0.7 | 4 | 114s | 16.0G | 1 | over
disease_mesh_ids | 6.5G | 64.0G | 10% | 0.7 | 4 | 113s | 16.0G | 1 | over
process_compendia | 6.1G | - | - | 0.9 | - | 221s | 16.0G | 1 | no-request-data
check_publications_completeness | 5.0G | 64.0G | 8% | 0.9 | 4 | 272s | 8.0G | 1 | over
get_umls_labels_and_synonyms | 4.0G | 64.0G | 6% | 0.8 | 4 | 63s | 8.0G | 1 | over
get_anatomy_obo_relationships | 3.4G | 64.0G | 5% | 0.6 | 4 | 90s | 8.0G | 1 | over
get_mods | 3.3G | 8.0G | 42% | 0.7 | 1 | 18s | 8.0G | 1 | ok
cell_line_compendia | 3.1G | 64.0G | 5% | 1.0 | 4 | 49s | 8.0G | 1 | over
genefamily_compendia | 3.1G | - | - | 0.9 | - | 48s | 8.0G | 1 | no-request-data
anatomy_uberon_ids | 3.0G | 64.0G | 5% | 0.3 | 4 | 129s | 8.0G | 1 | over
get_mods_labels | 2.4G | 64.0G | 4% | 0.6 | 4 | 22s | 8.0G | 1 | over
macromolecular_complex_compendia | 2.3G | 64.0G | 4% | 0.8 | 4 | 50s | 8.0G | 1 | over
get_chebi_concord | 2.2G | 64.0G | 3% | 0.1 | 4 | 23s | 8.0G | 1 | over
get_obo_synonyms | 2.1G | 8.0G | 26% | 0.1 | 1 | 748s | 8.0G | 1 | ok
get_disease_efo_relationships | 1.9G | 64.0G | 3% | 0.7 | 4 | 23s | 8.0G | 1 | over
disease_efo_ids | 1.9G | 64.0G | 3% | 0.7 | 4 | 22s | 8.0G | 1 | over
get_EFO_labels | 1.8G | 64.0G | 3% | 0.7 | 4 | 24s | 8.0G | 1 | over
ncbitaxon_labels_and_synonyms | 1.8G | 64.0G | 3% | 1.0 | 4 | 47s | 8.0G | 1 | over
get_obo_labels | 1.7G | 8.0G | 21% | 0.1 | 1 | 675s | 8.0G | 1 | ok
taxon_umls_ids | 1.7G | 64.0G | 3% | 0.9 | 4 | 12s | 8.0G | 1 | over
chemical_umls_ids | 1.7G | 64.0G | 3% | 0.9 | 4 | 13s | 8.0G | 1 | over
disease_umls_ids | 1.7G | 64.0G | 3% | 0.9 | 4 | 12s | 8.0G | 1 | over
anatomy_umls_ids | 1.6G | 64.0G | 2% | 0.9 | 4 | 11s | 8.0G | 1 | over
process_umls_ids | 1.5G | 64.0G | 2% | 0.7 | 4 | 11s | 8.0G | 1 | over
protein_umls_ids | 1.4G | 64.0G | 2% | 0.8 | 4 | 29s | 8.0G | 1 | over
get_process_rhea_relationships | 1.2G | 64.0G | 2% | 0.9 | 4 | 11s | 8.0G | 1 | over
get_rhea_labels | 1.2G | 64.0G | 2% | 0.8 | 4 | 12s | 8.0G | 1 | over
rxnorm_relationships | 1.0G | 64.0G | 2% | 0.9 | 4 | 17s | 8.0G | 1 | over
export_conflation_to_duckdb (×2) | 1.0G | 64.0G | 2% | 1.8 | 4 | 30s | 8.0G | 2 | over
chemical_chembl_ids | 0.9G | - | - | 0.9 | - | 6s | 8.0G | 1 | no-request-data
get_ncbitaxon | 0.8G | 8.0G | 9% | 0.2 | 1 | 19s | 8.0G | 1 | ok
drugchemical_conflated_synonyms | 0.7G | 64.0G | 1% | 1.0 | 4 | 9937s | 8.0G | 1 | over
get_obo_descriptions | 0.7G | 8.0G | 9% | 0.0 | 1 | 342s | 8.0G | 1 | ok
generate_kgx (×24) | 0.7G | 64.0G | 1% | 1.0 | 4 | 9699s | 8.0G | 1 | over
check_taxon_completeness | 0.6G | 64.0G | 1% | 0.8 | 4 | 18s | 8.0G | 1 | over
get_CLO_labels | 0.5G | 64.0G | 1% | 0.6 | 4 | 3s | 8.0G | 1 | over
get_clo_ids | 0.5G | 64.0G | 1% | 0.6 | 4 | 3s | 8.0G | 1 | over
get_icrdf | 0.5G | 64.0G | 1% | 0.2 | 4 | 251s | 8.0G | 1 | over
verify_pubmed | 0.4G | - | - | 0.3 | - | 586s | 8.0G | 1 | no-request-data
get_chemical_pubchem_mesh_concord | 0.4G | 64.0G | 1% | 0.4 | 4 | 2s | 8.0G | 1 | over
get_chemical_umls_relationships | 0.4G | 64.0G | 1% | 0.8 | 4 | 35s | 8.0G | 1 | over
get_hgnc_labels_and_synonyms | 0.3G | 64.0G | 1% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_chebi | 0.3G | 8.0G | 4% | 0.0 | 1 | 219s | 8.0G | 1 | ok
get_disease_obo_relationships | 0.3G | 64.0G | 1% | 0.2 | 4 | 14s | 8.0G | 1 | over
get_disease_umls_relationships | 0.3G | 64.0G | 1% | 0.7 | 4 | 36s | 8.0G | 1 | over
get_protein_pr_uniprotkb_relationships | 0.3G | 64.0G | 1% | 0.0 | 4 | 22s | 8.0G | 1 | over
get_taxon_umls_relationships | 0.3G | 64.0G | 1% | 0.8 | 4 | 35s | 8.0G | 1 | over
get_ensembl | 0.3G | 8.0G | 4% | 0.0 | 1 | 198s | 8.0G | 1 | ok
get_EC_labels | 0.3G | 64.0G | 0% | 0.4 | 4 | 1s | 8.0G | 1 | over
get_anatomy_umls_relationships | 0.3G | 64.0G | 0% | 0.8 | 4 | 34s | 8.0G | 1 | over
process_ec_ids | 0.3G | 64.0G | 0% | 0.3 | 4 | 1s | 8.0G | 1 | over
get_protein_umls_relationships | 0.3G | 64.0G | 0% | 1.0 | 4 | 33s | 8.0G | 1 | over
protein_pr_ids | 0.3G | 64.0G | 0% | 0.3 | 4 | 6s | 8.0G | 1 | over
get_reactome | 0.3G | 8.0G | 3% | 0.0 | 1 | 22s | 8.0G | 1 | ok
check_disease_completeness | 0.3G | - | - | 0.5 | - | 3s | 8.0G | 1 | no-request-data
chemical_chebi_ids | 0.3G | 64.0G | 0% | 0.0 | 4 | 22s | 8.0G | 1 | over
generate_sapbert_training_data (×18) | 0.3G | 64.0G | 0% | 1.0 | 4 | 8207s | 8.0G | 1 | over
get_process_umls_relationships | 0.3G | 64.0G | 0% | 1.0 | 4 | 33s | 8.0G | 1 | over
get_mesh | 0.3G | 8.0G | 3% | 0.0 | 1 | 42s | 8.0G | 1 | ok
check_process_completeness | 0.3G | - | - | 0.4 | - | 2s | 8.0G | 1 | no-request-data
get_gene_umls_relationships | 0.2G | 64.0G | 0% | 0.9 | 4 | 32s | 8.0G | 1 | over
process_go_ids | 0.2G | 64.0G | 0% | 0.2 | 4 | 1s | 8.0G | 1 | over
get_protein_ncit_umls_relationships | 0.2G | 64.0G | 0% | 0.8 | 4 | 34s | 8.0G | 1 | over
pubchem_rxnorm_annotations | 0.2G | 64.0G | 0% | 0.1 | 4 | 14s | 8.0G | 1 | over
disease_ncit_ids | 0.2G | 64.0G | 0% | 0.1 | 4 | 13s | 8.0G | 1 | over
unii_labels_and_synonyms | 0.2G | 64.0G | 0% | 0.4 | 4 | 2s | 8.0G | 1 | over
gene_hgnc_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_complexportal_labels_and_synonyms | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
anatomy_ncit_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_uniprotkb_sprot | 0.2G | 8.0G | 3% | 0.6 | 1 | 5s | 8.0G | 1 | ok
get_pubchem_structures | 0.2G | 8.0G | 3% | 0.1 | 1 | 113s | 8.0G | 1 | ok
gene_umls_ids | 0.2G | 64.0G | 0% | 1.0 | 4 | 27s | 8.0G | 1 | over
get_complexportal | 0.2G | 8.0G | 3% | 0.0 | 1 | 25s | 8.0G | 1 | ok
get_unichem | 0.2G | 8.0G | 3% | 0.1 | 1 | 6646s | 8.0G | 1 | ok
get_uniprotkb_trembl | 0.2G | 8.0G | 3% | 0.7 | 1 | 1902s | 8.0G | 1 | ok
protein_ensembl_ids | 0.2G | - | - | 1.0 | - | 21s | 8.0G | 1 | no-request-data
get_pubchem | 0.2G | 8.0G | 3% | 0.2 | 1 | 25s | 8.0G | 1 | ok
get_chemical_rxnorm_relationships | 0.2G | 64.0G | 0% | 0.0 | 4 | 2s | 8.0G | 1 | over
get_uniprotkb_idmapping | 0.2G | 8.0G | 3% | 0.7 | 1 | 1042s | 8.0G | 1 | ok
disease_hp_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 7s | 8.0G | 1 | over
download_unichem_structure | 0.2G | 8.0G | 3% | 0.2 | 1 | 1996s | 8.0G | 1 | ok
get_process_go_relationships | 0.2G | 64.0G | 0% | 0.1 | 4 | 5s | 8.0G | 1 | over
gene | 0.2G | 64.0G | 0% | 1.0 | 4 | 3252s | 8.0G | 1 | over
gene_ensembl_ids | 0.2G | - | - | 1.0 | - | 21s | 8.0G | 1 | no-request-data
anatomy_go_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
protein | 0.2G | 64.0G | 0% | 1.0 | 6 | 7693s | 8.0G | 1 | over
get_drugcentral | 0.2G | 8.0G | 3% | 0.0 | 1 | 1s | 8.0G | 1 | ok
check_disease | 0.2G | - | - | 0.4 | - | 3s | 8.0G | 1 | no-request-data
chemical | 0.2G | 64.0G | 0% | 1.0 | 4 | 6664s | 8.0G | 1 | over
filter_unichem | 0.2G | 64.0G | 0% | 0.9 | 4 | 192s | 8.0G | 1 | over
get_protein_uniprotkb_ensembl_relationships | 0.2G | 64.0G | 0% | 1.0 | 4 | 1092s | 8.0G | 1 | over
generate_content_report_for_compendium_SmallMolecule | 0.2G | 64.0G | 0% | 1.0 | 4 | 1086s | 8.0G | 1 | over
check_small_molecule | 0.2G | 64.0G | 0% | 1.0 | 4 | 883s | 8.0G | 1 | over
get_ncbigene_labels_synonyms_and_taxa | 0.2G | 64.0G | 0% | 1.0 | 4 | 604s | 8.0G | 1 | over
generate_content_report_for_compendium_MolecularActivity | 0.2G | - | - | 0.0 | - | 2s | 8.0G | 1 | no-request-data
keggcompound_labels | 0.2G | 64.0G | 0% | 0.0 | 4 | 420s | 8.0G | 1 | over
process | 0.2G | - | - | 0.9 | - | 12s | 8.0G | 1 | no-request-data
get_chemical_pubchem_cas_concord | 0.2G | 64.0G | 0% | 0.9 | 4 | 92s | 8.0G | 1 | over
check_activity | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
download_pubmed | 0.2G | 8.0G | 3% | 0.0 | 1 | 11059s | 8.0G | 1 | ok
anatomy_cl_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
chemical_rxnorm_ids | 0.2G | 64.0G | 0% | 0.3 | 4 | 2s | 8.0G | 1 | over
chemical_pubchem_ids | 0.2G | 64.0G | 0% | 1.0 | 4 | 324s | 8.0G | 1 | over
anatomy | 0.2G | - | - | 0.9 | - | 8s | 8.0G | 1 | no-request-data
check_gene | 0.2G | 64.0G | 0% | 0.9 | 4 | 505s | 8.0G | 1 | over
genefamily | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
pubchem_labels | 0.2G | 64.0G | 0% | 1.0 | 4 | 259s | 8.0G | 1 | over
chemical_unii_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
pubchem_synonyms | 0.2G | 64.0G | 0% | 0.8 | 4 | 162s | 8.0G | 1 | over
get_chemical_wikipedia_relationships | 0.2G | 64.0G | 0% | 0.0 | 4 | 2s | 8.0G | 1 | over
check_publications | 0.2G | 64.0G | 0% | 0.9 | 4 | 337s | 8.0G | 1 | over
cell_line | 0.2G | 64.0G | 0% | 0.4 | 4 | 1s | 8.0G | 1 | over
compress_umls | 0.2G | 64.0G | 0% | 0.3 | 4 | 44s | 8.0G | 1 | over
taxon | 0.2G | 64.0G | 0% | 1.0 | 4 | 137s | 8.0G | 1 | over
disease | 0.2G | - | - | 0.7 | - | 21s | 8.0G | 1 | no-request-data
check_chemical_entity | 0.2G | 64.0G | 0% | 0.6 | 4 | 2s | 8.0G | 1 | over
generate_content_report_for_compendium_MolecularMixture | 0.2G | 64.0G | 0% | 0.8 | 4 | 119s | 8.0G | 1 | over
check_molecular_mixture | 0.2G | 64.0G | 0% | 0.9 | 4 | 96s | 8.0G | 1 | over
get_SMPDB_labels | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
check_protein | 0.2G | 64.0G | 0% | 1.0 | 4 | 1337s | 8.0G | 1 | over
generate_prefix_table | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_content_report_for_compendium_Publication | 0.2G | 64.0G | 0% | 1.0 | 4 | 414s | 8.0G | 1 | over
generate_content_report_for_compendium_Protein | 0.2G | 64.0G | 0% | 1.0 | 4 | 1692s | 8.0G | 1 | over
chemical_drugbank_ids | 0.2G | 64.0G | 0% | 0.6 | 4 | 46s | 8.0G | 1 | over
macromolecular_complex (×2) | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
check_anatomical_entity | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
extract_taxon_ids_from_uniprotkb | 0.2G | 64.0G | 0% | 1.0 | 4 | 1072s | 8.0G | 1 | over
generate_content_report_for_compendium_Disease | 0.2G | - | - | 0.4 | - | 4s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_ChemicalEntity | 0.2G | 64.0G | 0% | 0.4 | 4 | 3s | 8.0G | 1 | over
download_unichem_reference | 0.2G | 8.0G | 3% | 0.1 | 1 | 382s | 8.0G | 1 | ok
generate_content_report_for_compendium_Drug | 0.2G | 64.0G | 0% | 0.0 | 4 | 2s | 8.0G | 1 | over
generate_content_report_for_compendium_umls | 0.2G | 64.0G | 0% | 0.4 | 4 | 10s | 8.0G | 1 | over
check_drug | 0.2G | 64.0G | 0% | 0.0 | 4 | 2s | 8.0G | 1 | over
get_wikidata_cell_relationships | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
generate_content_report_for_compendium_OrganismTaxon | 0.2G | 64.0G | 0% | 0.9 | 4 | 29s | 8.0G | 1 | over
check_taxon | 0.2G | 64.0G | 0% | 1.0 | 4 | 22s | 8.0G | 1 | over
generate_content_report_for_compendium_Gene | 0.2G | 64.0G | 0% | 1.0 | 4 | 625s | 8.0G | 1 | over
check_polypeptide | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_mapping_sources_table | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_unii | 0.2G | 8.0G | 3% | 0.2 | 1 | 9s | 8.0G | 1 | ok
gene_mods_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_omim | 0.2G | 8.0G | 3% | 0.0 | 1 | 0s | 8.0G | 1 | ok
generate_content_report_for_compendium_GrossAnatomicalStructure | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Pathway | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_conflation_files | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_gtopdb_inchikey_concord | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_rhea | 0.2G | 8.0G | 3% | 0.5 | 1 | 4s | 8.0G | 1 | ok
check_genefamily_completeness | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_chembl | 0.2G | 8.0G | 3% | 0.1 | 1 | 981s | 8.0G | 1 | ok
get_orphanet | 0.2G | 8.0G | 3% | 0.0 | 1 | 9s | 8.0G | 1 | ok
get_EFO | 0.2G | 8.0G | 3% | 0.2 | 1 | 5s | 8.0G | 1 | ok
generate_content_report_for_compendium_BiologicalProcess | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_SMPDB | 0.2G | 8.0G | 3% | 0.3 | 1 | 2s | 8.0G | 1 | ok
check_cellular_component | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_doid | 0.2G | 8.0G | 3% | 0.0 | 1 | 3s | 8.0G | 1 | ok
generate_content_report_for_compendium_GeneFamily | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_AnatomicalEntity | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
check_pathway | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_process | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_chemical_drugcentral_relationships | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_cliques_table | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_macromolecular_complex | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_doid_labels_and_synonyms | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_cell_line_completeness | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
pubchem_rxnorm_relationships | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_gross_anatomical_structure | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
download_rxnorm | 0.2G | 8.0G | 3% | 0.1 | 1 | 40s | 8.0G | 1 | ok
generate_content_report_for_compendium_Cell | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_cell_line | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
disease_manual_concord | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
process_reactome_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
disease_mondo_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
check_synonyms_gzipped_files | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_compendia_files | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_hgncfamily_labels | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_genefamily | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_orphanet_labels_and_synonyms | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
check_macromolecular_complex_completeness | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_anatomy_completeness | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
chemical_gtopdb_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_omim_labels | 0.2G | 1.0G | 21% | 0.0 | 1 | 0s | 8.0G | 1 | ok
get_umls_gene_protein_mappings | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_ncbigene | 0.2G | 8.0G | 3% | 0.1 | 1 | 42s | 8.0G | 1 | ok
get_clo | 0.2G | 8.0G | 3% | 0.0 | 1 | 1s | 8.0G | 1 | ok
get_pantherfamily_labels | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_Polypeptide | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_phenotypic_feature | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
generate_content_report_for_compendium_MacromolecularComplex | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_panther_pathway_labels | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_protein_ncit_uniprotkb_relationships | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
chemical_hmdb_ids | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
check_chemical_mixture | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_content_report_for_compendium_CellularComponent | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
gtopdb_labels_and_synonyms | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
generate_content_report_for_compendium_CellLine | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_hgncfamily | 0.2G | 8.0G | 3% | 0.0 | 1 | 1s | 8.0G | 1 | ok
generate_summary_content_report_for_compendia | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_content_report_for_compendium_ComplexMolecularMixture | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
download_umls | 0.2G | 8.0G | 3% | 0.5 | 1 | 906s | 8.0G | 1 | ok
generate_content_report_for_compendium_ChemicalMixture | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
chemical_drugcentral_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
gene_omim_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
generate_content_report_for_compendium_PhenotypicFeature | 0.2G | - | - | 0.0 | - | 1s | 8.0G | 1 | no-request-data
get_hgnc | 0.2G | 8.0G | 3% | 0.0 | 1 | 1s | 8.0G | 1 | ok
get_gtopdb | 0.2G | 8.0G | 3% | 0.0 | 1 | 5s | 8.0G | 1 | ok
get_reactome_labels | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_EC | 0.2G | 8.0G | 3% | 0.0 | 1 | 1s | 8.0G | 1 | ok
get_disease_doid_relationships | 0.2G | 64.0G | 0% | 0.0 | 4 | 1s | 8.0G | 1 | over
get_gene_medgen_relationships | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
check_cell | 0.2G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
get_pantherfamily | 0.2G | 8.0G | 3% | 0.0 | 1 | 131s | 8.0G | 1 | ok
disease_omim_ids | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
get_panther_pathways | 0.2G | 8.0G | 3% | 0.1 | 1 | 7s | 8.0G | 1 | ok
get_ncit | 0.2G | 8.0G | 3% | 0.0 | 1 | 0s | 8.0G | 1 | ok
check_complex_mixture | 0.2G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
taxon_ncbi_ids | 0.0G | 64.0G | 0% | 0.3 | 4 | 2s | 8.0G | 1 | over
gene_ncbi_ids | 0.0G | 64.0G | 0% | 0.6 | 4 | 24s | 8.0G | 1 | over
protein_uniprotkb_ids | 0.0G | 64.0G | 0% | 0.9 | 4 | 81s | 8.0G | 1 | over
genefamily_pantherfamily_ids | 0.0G | - | - | 0.0 | - | 0s | 8.0G | 1 | no-request-data
chemical_kegg_ids | 0.0G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
disease_doid_ids | 0.0G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
disease_orphanet_ids | 0.0G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
genefamily_hgncfamily_ids | 0.0G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
process_rhea_ids | 0.0G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
process_smpdb_ids | 0.0G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
process_panther_ids | 0.0G | 64.0G | 0% | 0.0 | 4 | 0s | 8.0G | 1 | over
