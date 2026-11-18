# UMLS CUIs whose direct and MeSH paths to NCBITaxon disagree

47 of the 66,236 UMLS CUIs that reach NCBITaxon both directly and through MeSH reach a different
NCBITaxon each way (all of them are in `path-disagreements.csv`). A random sample of 10:

| CUI | direct NCBITaxon | MeSH | NCBITaxon via MeSH |
|---|---|---|---|
| UMLS:C0751990 Epsilonproteobacteria | NCBITaxon:3031852 Epsilonproteobacteria | MESH:D020565 Epsilonproteobacteria | NCBITaxon:29547 Campylobacterota (e-proteobacteria) |
| UMLS:C0997376 Williopsis | NCBITaxon:3713381 Petasospora | MESH:D055320 Williopsis | NCBITaxon:4962 Williopsis |
| UMLS:C0013268 Ducks | NCBITaxon:8835 Anas (ducks) | MESH:D004372 Ducks | NCBITaxon:2068716 Anatinae |
| UMLS:C0319623 Geotrichum galactomycetum | NCBITaxon:27317 Geotrichum galactomycetum | MESH:C000682231 Geotrichum candidum | NCBITaxon:1173061 Geotrichum candidum |
| UMLS:C1070335 Goose circovirus | NCBITaxon:3047842 Circovirus goose | MESH:C000623807 Goose circovirus | NCBITaxon:146032 Goose circovirus |
| UMLS:C1060600 Russula cremoricolor | NCBITaxon:2860945 Russula cremoricolor | MESH:C000701688 Russula cremoricolor | NCBITaxon:125791 Russula cremicolor |
| UMLS:C0993566 Daboia | NCBITaxon:42188 Daboia | MESH:D017840 Daboia | NCBITaxon:8707 Daboia russelii (Russell's viper) |
| UMLS:C0330209 Magnoliopsida | NCBITaxon:2986937 Oncothecales | MESH:D019684 Magnoliopsida | NCBITaxon:3398 Magnoliopsida (flowering plants) |
| UMLS:C1031468 Wasabia | NCBITaxon:75806 Eutrema japonicum (wasabe) | MESH:D031228 Wasabia | NCBITaxon:98005 Eutrema |
| UMLS:C0376574 GB virus C | NCBITaxon:3052608 Pegivirus hominis | MESH:D029407 GB virus C | NCBITaxon:54290 GB virus C |
