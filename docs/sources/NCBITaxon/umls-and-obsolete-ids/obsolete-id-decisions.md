# What happens to obsolete NCBITaxon IDs in the taxon concords

Inputs: the taxon build of 37e01618 (this branch merged with main bb882867): UMLS 2026AA, and MeSH
mesh.nt and the NCBI Taxonomy taxdump both downloaded 2026-11-17.

Counts of rows per decision; see `update_obsolete_ncbitaxon_ids()` and
`resolve_obsolete_ncbitaxon_ids()` in `src/createcompendia/taxon.py` for what each one means.

| decision | NCBI_MESH | UMLS |
|---|---|---|
| remapped_merged | 54 | 992 |
| dropped_merged_already_linked | 609 | 0 |
| dropped_merged_into_broader_taxon | 14 | 40 |
| dropped_merged_superseded_by_direct | 1,231 | 976 |
| dropped_merged_ambiguous | 2 | 24 |
| dropped_deleted | 36 | 115 |

## dropped_merged_into_broader_taxon

8 of 54, spread evenly over them in order of current taxon (all of them are in
`obsolete-id-decisions.csv`):

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

8 of 26, spread evenly over them in order of current taxon (all of them are in
`obsolete-id-decisions.csv`):

| identifier | obsolete | current |
|---|---|---|
| UMLS:C1008062 Dalyellioida | NCBITaxon:39220 | NCBITaxon:3092782 Dalytyphloplanida |
| UMLS:C5949940 Stenopsocus dactylinus | NCBITaxon:3074940 | NCBITaxon:3457878 Neostenopsocus maculosus |
| UMLS:C4776447 Yaetanytarsus iriomotensis | NCBITaxon:2050747 | NCBITaxon:3569711 Yaetanytarsus magnihamatus |
| UMLS:C4571274 Ernoporicus caucasicus | NCBITaxon:1971807 | NCBITaxon:3716124 Eidophelus caucasicus |
| UMLS:C1076794 Exidiopsis grisea | NCBITaxon:160905 | NCBITaxon:3735854 Ulocolla grisea |
| UMLS:C1190016 Austrolebias cinereus | NCBITaxon:135332 | NCBITaxon:3740832 Cypholebias cinereus |
| UMLS:C2627771 Thomomys fulvus | NCBITaxon:496468 | NCBITaxon:3774382 Megascapheus fulvus |
| UMLS:C3766676 Thomomys nigricans | NCBITaxon:1387314 | NCBITaxon:3774384 Megascapheus nigricans |
