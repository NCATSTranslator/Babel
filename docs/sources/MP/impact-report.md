# Source impact report: MP

- Generated: 2026-06-30 05:20:58 UTC
- Babel commit: 765aa0a6b91551c4487edaefa821397bf71d6933
- Source pipelines: disease
- Source prefixes: MP
- Comparison mode: synthetic

## 1. Identifiers added

Totals: 14,750 identifiers across 1 prefix(es) in 1 pipeline(s).

### By prefix

- MP: 14,750

### By pipeline

- disease: 14,750

## 2. Biolink types

### Overall declared type breakdown

- biolink:PhenotypicFeature: 14,750

### Source-declared (from each ids file)

- disease / MP
  - biolink:PhenotypicFeature: 14,750

### Final compendium-assigned (after glom)

- disease / Disease.txt: 94 MP identifiers
- disease / PhenotypicFeature.txt: 14,656 MP identifiers

## 3. Cross-references added

Totals: 663 cross-reference rows across 1 concord file(s).

### By pipeline

- disease / MP: 663

### Partner prefix breakdown (per pipeline)

- disease
  - Fyler: 257
  - CL: 112
  - MA: 85
  - GO: 76
  - MGI: 70
  - FMA: 30
  - https: 11
  - http: 7
  - MPATH: 4
  - NLX: 4
  - HP: 2
  - PMID: 2
  - UMLS: 2
  - NBO: 1

## 4. Clique impact

**Worst-case view.** This report is computed from the intermediate identifier and concord files and
cannot see downstream filtering that happens later in the build — most notably the Biolink Model's
per-class prefix restrictions, which drop identifiers whose prefix is not permitted for a clique's
biolink type. The counts and detail files below are therefore an *upper bound*: they show every
change the source could introduce before that filtering is applied.

### disease

- 14,441 new cliques composed only of MP identifiers (a 3.39% increase over the 426,256 pre-existing
  cliques)
- 214 existing cliques contain MP identifiers in the after state (0.05% of the 426,256 pre-existing
  cliques). Of these, 185 cliques gain at least one structurally new identifier from MP, and 29
  already contained the MP CURIE via an xref from another source — MP's ids file now also lists
  those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new MP cross-references
- 194 structurally-new MP identifiers are added to existing cliques (194 via expansion, 0 via
  merges). This is distinct from the 185 existing cliques that change, since one clique can gain
  several identifiers.
- Total cliques in this pipeline go from 426,256 to 440,697
- Full list of new cliques: [`impact-report/new-cliques.csv`](impact-report/new-cliques.csv)
- Full list of modified cliques (one row per added/preexisting MP identifier):
  [`impact-report/modified-cliques.csv`](impact-report/modified-cliques.csv)
- Full list of new / activated cross-references:
  [`impact-report/new-xrefs.tsv`](impact-report/new-xrefs.tsv)

#### Sample pure-new cliques (up to 3)

- [`MP:0005068`](http://purl.obolibrary.org/obo/MP_0005068) "abnormal NK cell morphology"
  **(preferred)**
  - [`MP:0008043`](http://purl.obolibrary.org/obo/MP_0008043) "abnormal NK cell number"
  - [`MP:0008044`](http://purl.obolibrary.org/obo/MP_0008044) "increased NK cell number"
  - [`MP:0008045`](http://purl.obolibrary.org/obo/MP_0008045) "decreased NK cell number"
  - [`MP:0008046`](http://purl.obolibrary.org/obo/MP_0008046) "absent NK cells"
  - [`MP:0010766`](http://purl.obolibrary.org/obo/MP_0010766) "abnormal NK cell physiology"
  - [`CL:0000623`](http://purl.obolibrary.org/obo/CL_0000623)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
  - [`FMA:63147`](http://purl.obolibrary.org/obo/FMA_63147)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
  - [`FMA:83601`](http://purl.obolibrary.org/obo/FMA_83601)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
- [`MP:0010184`](http://purl.obolibrary.org/obo/MP_0010184) "abnormal T follicular helper cell
  morphology" **(preferred)**
  - [`MP:0010185`](http://purl.obolibrary.org/obo/MP_0010185) "abnormal T follicular helper cell
    number"
  - [`MP:0010186`](http://purl.obolibrary.org/obo/MP_0010186) "increased T follicular helper cell
    number"
  - [`MP:0010187`](http://purl.obolibrary.org/obo/MP_0010187) "decreased T follicular helper cell
    number"
  - [`MP:0010188`](http://purl.obolibrary.org/obo/MP_0010188) "abnormal T follicular helper cell
    differentiation"
  - [`MP:0010189`](http://purl.obolibrary.org/obo/MP_0010189) "abnormal T follicular helper cell
    physiology"
  - [`CL:0002038`](http://purl.obolibrary.org/obo/CL_0002038)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
- [`MP:0011240`](http://purl.obolibrary.org/obo/MP_0011240) "abnormal fetal derived definitive
  erythrocyte morphology" **(preferred)**
  - [`MP:0011241`](http://purl.obolibrary.org/obo/MP_0011241) "abnormal fetal derived definitive
    erythrocyte cell number"
  - [`MP:0011242`](http://purl.obolibrary.org/obo/MP_0011242) "increased fetal derived definitive
    erythrocyte cell number"
  - [`MP:0011243`](http://purl.obolibrary.org/obo/MP_0011243) "decreased fetal derived definitive
    erythrocyte cell number"
  - [`MP:0011244`](http://purl.obolibrary.org/obo/MP_0011244) "absent fetal derived definitive
    erythrocytes"
  - [`MP:0011245`](http://purl.obolibrary.org/obo/MP_0011245) "abnormal fetal derived definitive
    erythrocyte physiology"
  - [`CL:0002357`](http://purl.obolibrary.org/obo/CL_0002357)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**

#### Sample expanded cliques (up to 3)

Of the 214 cliques that contain MP identifiers in the after state, 0 would also see their preferred
identifier change as a result of adding MP. The sample below leads with preferred-id-change cliques
(if any), then structurally grown cliques, then cliques where MP only adds CURIEs that were already
present via xref. Within each clique, identifiers are listed in the same order they would appear in
the compendium (biolink prefix priority, then lexicographic within prefix).

- Clique with 98 identifiers — typed as `biolink:Disease` — gains 1 new member(s) from MP:
  - [`MONDO:0005021`](http://purl.obolibrary.org/obo/MONDO_0005021) "dilated cardiomyopathy"
    **(preferred)**
  - [`DOID:0110423`](http://purl.obolibrary.org/obo/DOID_0110423) "dilated cardiomyopathy 1C"
  - [`DOID:0110424`](http://purl.obolibrary.org/obo/DOID_0110424) "dilated cardiomyopathy 1CC"
  - [`DOID:0110426`](http://purl.obolibrary.org/obo/DOID_0110426) "dilated cardiomyopathy 1D"
  - [`DOID:0110427`](http://purl.obolibrary.org/obo/DOID_0110427) "dilated cardiomyopathy 1V"
  - [`DOID:0110428`](http://purl.obolibrary.org/obo/DOID_0110428) "dilated cardiomyopathy 1AA"
  - [`DOID:0110429`](http://purl.obolibrary.org/obo/DOID_0110429) "dilated cardiomyopathy 1H"
  - [`DOID:0110430`](http://purl.obolibrary.org/obo/DOID_0110430) "dilated cardiomyopathy 1G"
  - [`DOID:0110431`](http://purl.obolibrary.org/obo/DOID_0110431) "dilated cardiomyopathy 1I"
  - [`DOID:0110432`](http://purl.obolibrary.org/obo/DOID_0110432) "dilated cardiomyopathy 1NN"
  - [`DOID:0110433`](http://purl.obolibrary.org/obo/DOID_0110433) "dilated cardiomyopathy 1E"
  - [`DOID:0110434`](http://purl.obolibrary.org/obo/DOID_0110434) "dilated cardiomyopathy 1Z"
  - [`DOID:0110435`](http://purl.obolibrary.org/obo/DOID_0110435) "dilated cardiomyopathy 1GG"
  - [`DOID:0110436`](http://purl.obolibrary.org/obo/DOID_0110436) "dilated cardiomyopathy 1L"
  - [`DOID:0110437`](http://purl.obolibrary.org/obo/DOID_0110437) "dilated cardiomyopathy 1K"
  - [`DOID:0110438`](http://purl.obolibrary.org/obo/DOID_0110438) "dilated cardiomyopathy 1JJ"
  - [`DOID:0110439`](http://purl.obolibrary.org/obo/DOID_0110439) "dilated cardiomyopathy 1P"
  - [`DOID:0110441`](http://purl.obolibrary.org/obo/DOID_0110441) "dilated cardiomyopathy 2B"
  - [`DOID:0110442`](http://purl.obolibrary.org/obo/DOID_0110442) "dilated cardiomyopathy 1Q"
  - [`DOID:0110443`](http://purl.obolibrary.org/obo/DOID_0110443) "dilated cardiomyopathy 1B"
  - [`DOID:0110444`](http://purl.obolibrary.org/obo/DOID_0110444) "dilated cardiomyopathy 1X"
  - [`DOID:0110445`](http://purl.obolibrary.org/obo/DOID_0110445) "dilated cardiomyopathy 1KK"
  - [`DOID:0110446`](http://purl.obolibrary.org/obo/DOID_0110446) "dilated cardiomyopathy 1W"
  - [`DOID:0110447`](http://purl.obolibrary.org/obo/DOID_0110447) "dilated cardiomyopathy 1DD"
  - [`DOID:0110448`](http://purl.obolibrary.org/obo/DOID_0110448) "dilated cardiomyopathy 1HH"
  - [`DOID:0110449`](http://purl.obolibrary.org/obo/DOID_0110449) "dilated cardiomyopathy 1M"
  - [`DOID:0110450`](http://purl.obolibrary.org/obo/DOID_0110450) "dilated cardiomyopathy 1II"
  - [`DOID:0110451`](http://purl.obolibrary.org/obo/DOID_0110451) "dilated cardiomyopathy 1O"
  - [`DOID:0110452`](http://purl.obolibrary.org/obo/DOID_0110452) "dilated cardiomyopathy 1T"
  - [`DOID:0110453`](http://purl.obolibrary.org/obo/DOID_0110453) "dilated cardiomyopathy 1EE"
  - [`DOID:0110454`](http://purl.obolibrary.org/obo/DOID_0110454) "dilated cardiomyopathy 1S"
  - [`DOID:0110455`](http://purl.obolibrary.org/obo/DOID_0110455) "dilated cardiomyopathy 1U"
  - [`DOID:0110456`](http://purl.obolibrary.org/obo/DOID_0110456) "dilated cardiomyopathy 1R"
  - [`DOID:0110457`](http://purl.obolibrary.org/obo/DOID_0110457) "dilated cardiomyopathy 1Y"
  - [`DOID:0110458`](http://purl.obolibrary.org/obo/DOID_0110458) "dilated cardiomyopathy 1BB"
  - [`DOID:0110459`](http://purl.obolibrary.org/obo/DOID_0110459) "dilated cardiomyopathy 1FF"
  - [`DOID:0110460`](http://purl.obolibrary.org/obo/DOID_0110460) "dilated cardiomyopathy 2A"
  - [`DOID:0110461`](http://purl.obolibrary.org/obo/DOID_0110461) "dilated cardiomyopathy 3B"
  - [`DOID:12930`](http://purl.obolibrary.org/obo/DOID_12930) "dilated cardiomyopathy"
  - [`orphanet:217604`](http://www.orpha.net/ORDO/Orphanet_217604)
  - [`EFO:0000407`](http://www.ebi.ac.uk/efo/EFO_0000407) "obsolete_dilated cardiomyopathy"
  - [`UMLS:C0007193`](http://identifiers.org/umls/C0007193) "Cardiomyopathy, Dilated"
  - [`MESH:C580047`](http://id.nlm.nih.gov/mesh/C580047) "Dmd-Associated Dilated Cardiomyopathy"
  - [`MESH:D002311`](http://id.nlm.nih.gov/mesh/D002311) "Cardiomyopathy, Dilated"
  - [`MEDDRA:10010681`](http://identifiers.org/meddra/10010681)
  - [`MEDDRA:10056370`](http://identifiers.org/meddra/10056370)
  - [`MEDDRA:10056419`](http://identifiers.org/meddra/10056419)
  - [`NCIT:C84673`](http://purl.obolibrary.org/obo/NCIT_C84673) "Dilated Cardiomyopathy"
  - [`SNOMEDCT:195021004`](http://snomed.info/id/195021004)
  - [`SNOMEDCT:399020009`](http://snomed.info/id/399020009)
  - `MEDGEN:2880`
  - [`ICD10:I42.0`](https://icd.codes/icd9cm/I42.0)
  - [`KEGG.DISEASE:05414`](http://identifiers.org/kegg.disease/05414)
  - [`HP:0001644`](http://purl.obolibrary.org/obo/HP_0001644) "Dilated cardiomyopathy"
  - [`MP:0002795`](http://purl.obolibrary.org/obo/MP_0002795) "dilated cardiomyopathy"
    **(new from MP)**
  - `Fyler:1843`
  - `GARD:221`
  - `ICD10CM:I42.0`
  - `MIM:302045`
  - `MIM:600884`
  - `MIM:601154`
  - `MIM:601493`
  - `MIM:601494`
  - `MIM:604145`
  - `MIM:604288`
  - `MIM:604765`
  - `MIM:605582`
  - `MIM:606685`
  - `MIM:607482`
  - `MIM:608569`
  - `MIM:609909`
  - `MIM:609915`
  - `MIM:611407`
  - `MIM:611615`
  - `MIM:611878`
  - `MIM:611879`
  - `MIM:611880`
  - `MIM:612158`
  - `MIM:612877`
  - `MIM:613122`
  - `MIM:613172`
  - `MIM:613252`
  - `MIM:613286`
  - `MIM:613424`
  - `MIM:613426`
  - `MIM:613642`
  - `MIM:613694`
  - `MIM:613697`
  - `MIM:613881`
  - `MIM:614672`
  - `MIM:615184`
  - `MIM:615235`
  - `MIM:615248`
  - `MIM:615916`
  - `MIM:PS115200`
  - `ORDO:217604`
  - `SNOMEDCT_US_2025_09_01:74368002`
  - `http://id.who.int/icd/entity/1916294688`
- Clique with 45 identifiers — typed as `biolink:Disease` — gains 1 new member(s) from MP:
  - [`MONDO:0007172`](http://purl.obolibrary.org/obo/MONDO_0007172) "atrial septal defect 1"
    **(preferred)**
  - [`DOID:0110106`](http://purl.obolibrary.org/obo/DOID_0110106) "atrial heart septal defect 1"
  - [`DOID:0110107`](http://purl.obolibrary.org/obo/DOID_0110107) "atrial heart septal defect 2"
  - [`DOID:0110108`](http://purl.obolibrary.org/obo/DOID_0110108) "atrial heart septal defect 3"
  - [`DOID:0110109`](http://purl.obolibrary.org/obo/DOID_0110109) "atrial heart septal defect 4"
  - [`DOID:0110110`](http://purl.obolibrary.org/obo/DOID_0110110) "atrial heart septal defect 5"
  - [`DOID:0110111`](http://purl.obolibrary.org/obo/DOID_0110111) "atrial heart septal defect 6"
  - [`DOID:0110112`](http://purl.obolibrary.org/obo/DOID_0110112) "atrial heart septal defect 7"
  - [`DOID:0110113`](http://purl.obolibrary.org/obo/DOID_0110113) "atrial heart septal defect 8"
  - [`DOID:0110114`](http://purl.obolibrary.org/obo/DOID_0110114) "atrial heart septal defect 9"
  - [`DOID:1882`](http://purl.obolibrary.org/obo/DOID_1882) "atrial heart septal defect"
  - [`OMIM:108800`](http://purl.obolibrary.org/obo/OMIM_108800)
  - [`UMLS:C0018817`](http://identifiers.org/umls/C0018817) "Atrial Septal Defects"
  - [`UMLS:C1862389`](http://identifiers.org/umls/C1862389) "ATRIAL SEPTAL DEFECT 1"
  - [`UMLS:C1862392`](http://identifiers.org/umls/C1862392) "Atrial Septal Defect, Secundum Type"
  - [`MESH:C566239`](http://id.nlm.nih.gov/mesh/C566239) "Atrial Septal Defect 1"
  - [`MESH:C566241`](http://id.nlm.nih.gov/mesh/C566241) "Atrial Septal Defect, Secundum Type"
  - [`MESH:D006344`](http://id.nlm.nih.gov/mesh/D006344) "Heart Septal Defects, Atrial"
  - [`MEDDRA:10003664`](http://identifiers.org/meddra/10003664)
  - [`MEDDRA:10003666`](http://identifiers.org/meddra/10003666)
  - [`MEDDRA:10010377`](http://identifiers.org/meddra/10010377)
  - [`MEDDRA:10019308`](http://identifiers.org/meddra/10019308)
  - [`MEDDRA:10040055`](http://identifiers.org/meddra/10040055)
  - [`NCIT:C84473`](http://purl.obolibrary.org/obo/NCIT_C84473) "Atrial Septal Defect"
  - [`SNOMEDCT:253366007`](http://snomed.info/id/253366007)
  - [`SNOMEDCT:405752007`](http://snomed.info/id/405752007)
  - [`SNOMEDCT:70142008`](http://snomed.info/id/70142008)
  - `MEDGEN:349495`
  - [`ICD10:Q21.1`](https://icd.codes/icd9cm/Q21.1)
  - [`HP:0001631`](http://purl.obolibrary.org/obo/HP_0001631) "Atrial septal defect"
  - [`MP:0010403`](http://purl.obolibrary.org/obo/MP_0010403) "atrial septal defect"
    **(new from MP)**
  - `Fyler:2050`
  - `MIM:108800`
  - `MIM:108900`
  - `MIM:607941`
  - `MIM:611363`
  - `MIM:612794`
  - `MIM:613087`
  - `MIM:614089`
  - `MIM:614433`
  - `MIM:614475`
  - `MIM:PS108800`
  - `ORDO:1478`
  - `ORDO:1479`
  - `SNOMEDCT_US_2025_09_01:156915002`
- Clique with 49 identifiers — typed as `biolink:Disease` — gains 1 new member(s) from MP:
  - [`MONDO:0001298`](http://purl.obolibrary.org/obo/MONDO_0001298) "congenital mitral valve
    insufficiency" **(preferred)**
  - [`DOID:11502`](http://purl.obolibrary.org/obo/DOID_11502) "mitral valve insufficiency"
  - [`DOID:57`](http://purl.obolibrary.org/obo/DOID_57) "aortic valve insufficiency"
  - [`UMLS:C0003504`](http://identifiers.org/umls/C0003504) "Aortic Valve Insufficiency"
  - [`UMLS:C0026266`](http://identifiers.org/umls/C0026266) "Mitral Valve Insufficiency"
  - [`UMLS:C0155568`](http://identifiers.org/umls/C0155568) "Rheumatic aortic regurgitation"
  - [`UMLS:C0158619`](http://identifiers.org/umls/C0158619) "Congenital insufficiency of mitral
    valve"
  - [`UMLS:C0264774`](http://identifiers.org/umls/C0264774) "Mitral and aortic incompetence"
  - [`UMLS:C3551535`](http://identifiers.org/umls/C3551535) "Mitral regurgitation, mild"
  - [`MESH:D001022`](http://id.nlm.nih.gov/mesh/D001022) "Aortic Valve Insufficiency"
  - [`MESH:D008944`](http://id.nlm.nih.gov/mesh/D008944) "Mitral Valve Insufficiency"
  - [`MEDDRA:10002898`](http://identifiers.org/meddra/10002898)
  - [`MEDDRA:10002904`](http://identifiers.org/meddra/10002904)
  - [`MEDDRA:10002915`](http://identifiers.org/meddra/10002915)
  - [`MEDDRA:10010545`](http://identifiers.org/meddra/10010545)
  - [`MEDDRA:10010547`](http://identifiers.org/meddra/10010547)
  - [`MEDDRA:10027715`](http://identifiers.org/meddra/10027715)
  - [`MEDDRA:10027716`](http://identifiers.org/meddra/10027716)
  - [`MEDDRA:10027718`](http://identifiers.org/meddra/10027718)
  - [`MEDDRA:10027727`](http://identifiers.org/meddra/10027727)
  - [`MEDDRA:10039045`](http://identifiers.org/meddra/10039045)
  - [`MEDDRA:10039046`](http://identifiers.org/meddra/10039046)
  - [`MEDDRA:10052839`](http://identifiers.org/meddra/10052839)
  - [`MEDDRA:10074862`](http://identifiers.org/meddra/10074862)
  - [`NCIT:C197881`](http://purl.obolibrary.org/obo/NCIT_C197881) "Congenital Mitral Insufficiency"
  - [`NCIT:C197951`](http://purl.obolibrary.org/obo/NCIT_C197951) "Rheumatic Aortic Insufficiency"
  - [`NCIT:C50852`](http://purl.obolibrary.org/obo/NCIT_C50852) "Mitral Valve Regurgitation"
  - [`NCIT:C50861`](http://purl.obolibrary.org/obo/NCIT_C50861) "Aortic Valve Regurgitation"
  - [`NCIT:C50888`](http://purl.obolibrary.org/obo/NCIT_C50888) "Mitral Valve Insufficiency"
  - [`NCIT:C51223`](http://purl.obolibrary.org/obo/NCIT_C51223) "Aortic Valve Insufficiency"
  - [`SNOMEDCT:194736003`](http://snomed.info/id/194736003)
  - [`SNOMEDCT:29928006`](http://snomed.info/id/29928006)
  - [`SNOMEDCT:48724000`](http://snomed.info/id/48724000)
  - `MEDGEN:510600`
  - [`ICD10:I06.1`](https://icd.codes/icd9cm/I06.1)
  - [`ICD10:Q23.3`](https://icd.codes/icd9cm/Q23.3)
  - [`ICD9:395.1`](http://translator.ncats.nih.gov/ICD9_395.1)
  - [`ICD9:396.3`](http://translator.ncats.nih.gov/ICD9_396.3)
  - [`ICD9:746.6`](http://translator.ncats.nih.gov/ICD9_746.6)
  - [`HP:0001653`](http://purl.obolibrary.org/obo/HP_0001653) "Mitral regurgitation"
  - [`MP:0006045`](http://purl.obolibrary.org/obo/MP_0006045) "mitral valve regurgitation"
    **(new from MP)**
  - `Fyler:1151`
  - `ICD10CM:Q23.3`
  - `SNOMEDCT_US_2025_09_01:155283004`
  - `SNOMEDCT_US_2025_09_01:194736003`
  - `SNOMEDCT_US_2025_09_01:194977007`
  - `SNOMEDCT_US_2025_09_01:29928006`
  - `SNOMEDCT_US_2025_09_01:60234000`
  - `http://id.who.int/icd/entity/403917903`
