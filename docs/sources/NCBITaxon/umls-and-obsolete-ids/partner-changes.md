# NCBITaxon partner changes

- Before: main (bb882867)
- After: this branch (37e01618)

| prefix | what happened to its NCBITaxon partner | identifiers |
|---|---|---|
| MESH | gained an NCBITaxon | 49 |
| MESH | obsolete partner removed | 1,367 |
| MESH | obsolete partner replaced by current | 579 |
| MESH | same partner | 68,604 |
| UMLS | current partner lost (regression) | 59 |
| UMLS | current partner replaced (regression) | 27 |
| UMLS | gained an NCBITaxon | 712,486 |
| UMLS | obsolete partner removed | 667 |
| UMLS | obsolete partner replaced by current | 625 |
| UMLS | same partner | 100,875 |

A random sample of 10 of the 86 regressions (all of them are in `partner-changes-regressions.csv`):

| identifier | before partner | after partner | before partner is now with |
|---|---|---|---|
| UMLS:C5434099 Bambusicola irregulispora | NCBITaxon:1238263 Bambusicola irregularispora |   | NCBITaxon:1238263; MESH:C000663319; UMLS:C3595841 |
| UMLS:C5434150 Calonectria hevicola | NCBITaxon:2182562 Calonectria heveicola |   | NCBITaxon:2182562; MESH:C000664735; UMLS:C5246841 |
| UMLS:C0319623 Geotrichum galactomycetum | NCBITaxon:1173061 Geotrichum candidum | NCBITaxon:27317 Geotrichum galactomycetum | NCBITaxon:1173061; MESH:C000682231; UMLS:C4049071 |
| UMLS:C3053958 Xanthoparmelia hottentota | NCBITaxon:859859 Xanthoparmelia hottentotta |   | NCBITaxon:859859; MESH:C000704777; UMLS:C1467519 |
| UMLS:C5434571 Inocybe dulcamaroides | NCBITaxon:707238 Pseudosperma dulcamaroides |   | NCBITaxon:707238; MESH:C000683025; UMLS:C2812180 |
| UMLS:C5434549 Seimatosporium cornii | NCBITaxon:1699687 Seimatosporium corni |   | NCBITaxon:1699687; MESH:C000688479; UMLS:C4096966 |
| UMLS:C5434142 Ceramothyrium ficus | NCBITaxon:1743213 Ceramothyrium fici |   | NCBITaxon:1743213; MESH:C000665876; UMLS:C4092737 |
| UMLS:C5227205 Staphylococcus saprophyticus subsp. bovis | NCBITaxon:29385 Staphylococcus saprophyticus |   | NCBITaxon:29385; MESH:C000638665; UMLS:C0318112 |
| UMLS:C5434535 Diaporthe podocarpi-macrophyll | NCBITaxon:1968850 Diaporthe podocarpi-macrophylli |   | NCBITaxon:1968850; MESH:C000690687; UMLS:C4570684 |
| UMLS:C5433606 Cercaria, flatworms | NCBITaxon:280692 Cercaria |   | NCBITaxon:280692; MESH:C000709674; UMLS:C1947992 |
