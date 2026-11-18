# What happens to obsolete NCBITaxon IDs in the taxon concords

Inputs: UMLS 2026AA MRCONSO; MeSH 2026 (desc2026/supp2026 XML: preferred-concept txid registry
numbers, standing in for the mesh.nt registry query); NCBI Taxonomy taxdump of 2026-11-17. The UMLS
and MeSH label and synonym files were produced in the pipeline's format from the same releases.

Counts of rows per decision; see `update_obsolete_ncbitaxon_ids()` and
`resolve_obsolete_ncbitaxon_ids()` in `src/createcompendia/taxon.py` for what each one means.

| decision | NCBI_MESH | UMLS |
|---|---|---|
| remapped_merged | 46 | 993 |
| dropped_merged_already_linked | 608 | 0 |
| dropped_merged_into_broader_taxon | 14 | 40 |
| dropped_merged_superseded_by_direct | 641 | 976 |
| dropped_merged_ambiguous | 0 | 23 |
| dropped_deleted | 3 | 115 |

## dropped_merged_into_broader_taxon

8 of 54, spread evenly over them in order of current taxon (all of them are in `obsolete-id-
decisions.csv`):

| identifier | obsolete | current |
|---|---|---|
| MESH:C000638712 Staphylococcus aureus subsp. aureus | NCBITaxon:46170 | NCBITaxon:1280 Staphylococcus aureus |
| UMLS:C4460777 Caesalpinia clade | NCBITaxon:1963084 | NCBITaxon:163090 Caesalpinieae |
| MESH:D018109 Avulavirus | NCBITaxon:260963 | NCBITaxon:2560069 Avulavirinae |
| UMLS:C5810217 Miconia sect. Echinata | NCBITaxon:3026378 | NCBITaxon:263288 Miconia |
| MESH:D017899 Caudovirales | NCBITaxon:28883 | NCBITaxon:2731619 Caudoviricetes |
| UMLS:C4444065 Stillabothrium cambelli | NCBITaxon:1930085 | NCBITaxon:3323339 Stillabothrium campbelli |
| UMLS:C0998215 Superorder Eucarida | NCBITaxon:6682 | NCBITaxon:3701045 Stomatocarida |
| UMLS:C5263768 Poa subgen. Stenopoa | NCBITaxon:2703953 | NCBITaxon:4544 Poa |

## dropped_merged_ambiguous

8 of 23, spread evenly over them in order of current taxon (all of them are in `obsolete-id-
decisions.csv`):

| identifier | obsolete | current |
|---|---|---|
| UMLS:C1008062 Dalyellioida | NCBITaxon:39220 | NCBITaxon:3092782 Dalytyphloplanida |
| UMLS:C5949938 Stenopsocus brevicapitus | NCBITaxon:3074938 | NCBITaxon:3457878 Neostenopsocus maculosus |
| UMLS:C5251354 Tanytarsus churamarinus | NCBITaxon:2562930 | NCBITaxon:3569709 Yaetanytarsus iriomeneus |
| UMLS:C4776447 Yaetanytarsus iriomotensis | NCBITaxon:2050747 | NCBITaxon:3569711 Yaetanytarsus magnihamatus |
| UMLS:C1076325 Ernoporus caucasicus | NCBITaxon:159918 | NCBITaxon:3716124 Eidophelus caucasicus |
| UMLS:C2993230 Austrolebias luzardoi | NCBITaxon:653298 | NCBITaxon:3738836 Matilebias periodicus |
| UMLS:C1190016 Austrolebias cinereus | NCBITaxon:135332 | NCBITaxon:3740832 Cypholebias cinereus |
| UMLS:C1190018 Austrolebias vazferreirai | NCBITaxon:2496534 | NCBITaxon:3740832 Cypholebias cinereus |
