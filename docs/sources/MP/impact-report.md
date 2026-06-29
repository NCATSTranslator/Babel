# Source impact report: MP

- Generated: 2026-06-29 22:32:34 UTC
- Babel commit: c3eb2d697be69e9954de4d5a4871a7678a717a41
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

- disease / Disease.txt: 93 MP identifiers
- disease / PhenotypicFeature.txt: 14,657 MP identifiers

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

- 14,441 new cliques composed only of MP identifiers (a 3.39% increase over the 426,254 pre-existing
  cliques)
- 214 existing cliques contain MP identifiers in the after state (0.05% of the 426,254 pre-existing
  cliques). Of these, 185 cliques gain at least one structurally new identifier from MP, and 29
  already contained the MP CURIE via an xref from another source — MP's ids file now also lists
  those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new MP cross-references
- 194 structurally-new MP identifiers are added to existing cliques (194 via expansion, 0 via
  merges). This is distinct from the 185 existing cliques that change, since one clique can gain
  several identifiers.
- Total cliques in this pipeline go from 426,254 to 440,695
- Full list of new cliques: [`impact-report/new-cliques.csv`](impact-report/new-cliques.csv)
- Full list of modified cliques (one row per added/preexisting MP identifier):
  [`impact-report/modified-cliques.csv`](impact-report/modified-cliques.csv)
- Full list of new / activated cross-references:
  [`impact-report/new-xrefs.tsv`](impact-report/new-xrefs.tsv)

#### Sample pure-new cliques (up to 3)

- [`CL:0000623`](http://purl.obolibrary.org/obo/CL_0000623) **(preferred)**
  - [`FMA:63147`](http://purl.obolibrary.org/obo/FMA_63147)
  - [`FMA:83601`](http://purl.obolibrary.org/obo/FMA_83601)
  - [`MP:0005068`](http://purl.obolibrary.org/obo/MP_0005068)
  - [`MP:0008043`](http://purl.obolibrary.org/obo/MP_0008043)
  - [`MP:0008044`](http://purl.obolibrary.org/obo/MP_0008044)
  - [`MP:0008045`](http://purl.obolibrary.org/obo/MP_0008045)
  - [`MP:0008046`](http://purl.obolibrary.org/obo/MP_0008046)
  - [`MP:0010766`](http://purl.obolibrary.org/obo/MP_0010766)
- [`CL:0002038`](http://purl.obolibrary.org/obo/CL_0002038) **(preferred)**
  - [`MP:0010184`](http://purl.obolibrary.org/obo/MP_0010184)
  - [`MP:0010185`](http://purl.obolibrary.org/obo/MP_0010185)
  - [`MP:0010186`](http://purl.obolibrary.org/obo/MP_0010186)
  - [`MP:0010187`](http://purl.obolibrary.org/obo/MP_0010187)
  - [`MP:0010188`](http://purl.obolibrary.org/obo/MP_0010188)
  - [`MP:0010189`](http://purl.obolibrary.org/obo/MP_0010189)
- [`CL:0002357`](http://purl.obolibrary.org/obo/CL_0002357) **(preferred)**
  - [`MP:0011240`](http://purl.obolibrary.org/obo/MP_0011240)
  - [`MP:0011241`](http://purl.obolibrary.org/obo/MP_0011241)
  - [`MP:0011242`](http://purl.obolibrary.org/obo/MP_0011242)
  - [`MP:0011243`](http://purl.obolibrary.org/obo/MP_0011243)
  - [`MP:0011244`](http://purl.obolibrary.org/obo/MP_0011244)
  - [`MP:0011245`](http://purl.obolibrary.org/obo/MP_0011245)

#### Sample expanded cliques (up to 3)

Of the 214 cliques that contain MP identifiers in the after state, 0 would also see their preferred
identifier change as a result of adding MP. The sample below leads with preferred-id-change cliques
(if any), then structurally grown cliques, then cliques where MP only adds CURIEs that were already
present via xref. Within each clique, identifiers are listed in the same order they would appear in
the compendium (biolink prefix priority, then lexicographic within prefix).

- Clique with 98 identifiers — gains 1 new member(s) from MP:
  - [`DOID:0110423`](http://purl.obolibrary.org/obo/DOID_0110423) **(preferred)**
  - [`DOID:0110424`](http://purl.obolibrary.org/obo/DOID_0110424)
  - [`DOID:0110426`](http://purl.obolibrary.org/obo/DOID_0110426)
  - [`DOID:0110427`](http://purl.obolibrary.org/obo/DOID_0110427)
  - [`DOID:0110428`](http://purl.obolibrary.org/obo/DOID_0110428)
  - [`DOID:0110429`](http://purl.obolibrary.org/obo/DOID_0110429)
  - [`DOID:0110430`](http://purl.obolibrary.org/obo/DOID_0110430)
  - [`DOID:0110431`](http://purl.obolibrary.org/obo/DOID_0110431)
  - [`DOID:0110432`](http://purl.obolibrary.org/obo/DOID_0110432)
  - [`DOID:0110433`](http://purl.obolibrary.org/obo/DOID_0110433)
  - [`DOID:0110434`](http://purl.obolibrary.org/obo/DOID_0110434)
  - [`DOID:0110435`](http://purl.obolibrary.org/obo/DOID_0110435)
  - [`DOID:0110436`](http://purl.obolibrary.org/obo/DOID_0110436)
  - [`DOID:0110437`](http://purl.obolibrary.org/obo/DOID_0110437)
  - [`DOID:0110438`](http://purl.obolibrary.org/obo/DOID_0110438)
  - [`DOID:0110439`](http://purl.obolibrary.org/obo/DOID_0110439)
  - [`DOID:0110441`](http://purl.obolibrary.org/obo/DOID_0110441)
  - [`DOID:0110442`](http://purl.obolibrary.org/obo/DOID_0110442)
  - [`DOID:0110443`](http://purl.obolibrary.org/obo/DOID_0110443)
  - [`DOID:0110444`](http://purl.obolibrary.org/obo/DOID_0110444)
  - [`DOID:0110445`](http://purl.obolibrary.org/obo/DOID_0110445)
  - [`DOID:0110446`](http://purl.obolibrary.org/obo/DOID_0110446)
  - [`DOID:0110447`](http://purl.obolibrary.org/obo/DOID_0110447)
  - [`DOID:0110448`](http://purl.obolibrary.org/obo/DOID_0110448)
  - [`DOID:0110449`](http://purl.obolibrary.org/obo/DOID_0110449)
  - [`DOID:0110450`](http://purl.obolibrary.org/obo/DOID_0110450)
  - [`DOID:0110451`](http://purl.obolibrary.org/obo/DOID_0110451)
  - [`DOID:0110452`](http://purl.obolibrary.org/obo/DOID_0110452)
  - [`DOID:0110453`](http://purl.obolibrary.org/obo/DOID_0110453)
  - [`DOID:0110454`](http://purl.obolibrary.org/obo/DOID_0110454)
  - [`DOID:0110455`](http://purl.obolibrary.org/obo/DOID_0110455)
  - [`DOID:0110456`](http://purl.obolibrary.org/obo/DOID_0110456)
  - [`DOID:0110457`](http://purl.obolibrary.org/obo/DOID_0110457)
  - [`DOID:0110458`](http://purl.obolibrary.org/obo/DOID_0110458)
  - [`DOID:0110459`](http://purl.obolibrary.org/obo/DOID_0110459)
  - [`DOID:0110460`](http://purl.obolibrary.org/obo/DOID_0110460)
  - [`DOID:0110461`](http://purl.obolibrary.org/obo/DOID_0110461)
  - [`DOID:12930`](http://purl.obolibrary.org/obo/DOID_12930)
  - [`EFO:0000407`](http://www.ebi.ac.uk/efo/EFO_0000407)
  - `Fyler:1843`
  - `GARD:221`
  - [`HP:0001644`](http://purl.obolibrary.org/obo/HP_0001644)
  - [`ICD10:I42.0`](https://icd.codes/icd9cm/I42.0)
  - `ICD10CM:I42.0`
  - [`KEGG.DISEASE:05414`](http://identifiers.org/kegg.disease/05414)
  - [`MEDDRA:10010681`](http://identifiers.org/meddra/10010681)
  - [`MEDDRA:10056370`](http://identifiers.org/meddra/10056370)
  - [`MEDDRA:10056419`](http://identifiers.org/meddra/10056419)
  - `MEDGEN:2880`
  - [`MESH:C580047`](http://id.nlm.nih.gov/mesh/C580047)
  - [`MESH:D002311`](http://id.nlm.nih.gov/mesh/D002311)
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
  - [`MONDO:0005021`](http://purl.obolibrary.org/obo/MONDO_0005021)
  - [`MP:0002795`](http://purl.obolibrary.org/obo/MP_0002795) **(new from MP)**
  - [`NCIT:C84673`](http://purl.obolibrary.org/obo/NCIT_C84673)
  - `ORDO:217604`
  - [`SNOMEDCT:195021004`](http://snomed.info/id/195021004)
  - [`SNOMEDCT:399020009`](http://snomed.info/id/399020009)
  - `SNOMEDCT_US_2025_09_01:74368002`
  - [`UMLS:C0007193`](http://identifiers.org/umls/C0007193)
  - `http://id.who.int/icd/entity/1916294688`
  - [`orphanet:217604`](http://www.orpha.net/ORDO/Orphanet_217604)
- Clique with 56 identifiers — gains 2 new member(s) from MP:
  - [`DOID:3627`](http://purl.obolibrary.org/obo/DOID_3627) **(preferred)**
  - [`EFO:0001666`](http://www.ebi.ac.uk/efo/EFO_0001666)
  - `Fyler:2301`
  - `Fyler:2708`
  - [`HP:0004942`](http://purl.obolibrary.org/obo/HP_0004942)
  - [`ICD10:I71.1`](https://icd.codes/icd9cm/I71.1)
  - [`ICD10:I71.3`](https://icd.codes/icd9cm/I71.3)
  - [`ICD10:I71.5`](https://icd.codes/icd9cm/I71.5)
  - [`ICD10:I71.8`](https://icd.codes/icd9cm/I71.8)
  - [`ICD10:I71.9`](https://icd.codes/icd9cm/I71.9)
  - [`ICD9:441.1`](http://translator.ncats.nih.gov/ICD9_441.1)
  - [`ICD9:441.3`](http://translator.ncats.nih.gov/ICD9_441.3)
  - [`ICD9:441.5`](http://translator.ncats.nih.gov/ICD9_441.5)
  - [`ICD9:441.6`](http://translator.ncats.nih.gov/ICD9_441.6)
  - [`MEDDRA:10000053`](http://identifiers.org/meddra/10000053)
  - [`MEDDRA:10002330`](http://identifiers.org/meddra/10002330)
  - [`MEDDRA:10002339`](http://identifiers.org/meddra/10002339)
  - [`MEDDRA:10002882`](http://identifiers.org/meddra/10002882)
  - [`MEDDRA:10002884`](http://identifiers.org/meddra/10002884)
  - [`MEDDRA:10002886`](http://identifiers.org/meddra/10002886)
  - [`MEDDRA:10043464`](http://identifiers.org/meddra/10043464)
  - [`MEDDRA:10043481`](http://identifiers.org/meddra/10043481)
  - [`MEDDRA:10051355`](http://identifiers.org/meddra/10051355)
  - [`MEDDRA:10057453`](http://identifiers.org/meddra/10057453)
  - [`MEDDRA:10058293`](http://identifiers.org/meddra/10058293)
  - [`MEDDRA:10060874`](http://identifiers.org/meddra/10060874)
  - `MEDGEN:362`
  - [`MESH:D001014`](http://id.nlm.nih.gov/mesh/D001014)
  - [`MESH:D001019`](http://id.nlm.nih.gov/mesh/D001019)
  - [`MONDO:0005160`](http://purl.obolibrary.org/obo/MONDO_0005160)
  - [`MP:0006278`](http://purl.obolibrary.org/obo/MP_0006278) **(new from MP)**
  - [`MP:0010574`](http://purl.obolibrary.org/obo/MP_0010574) **(new from MP)**
  - [`NCIT:C187666`](http://purl.obolibrary.org/obo/NCIT_C187666)
  - [`NCIT:C196716`](http://purl.obolibrary.org/obo/NCIT_C196716)
  - [`NCIT:C26697`](http://purl.obolibrary.org/obo/NCIT_C26697)
  - [`NCIT:C27046`](http://purl.obolibrary.org/obo/NCIT_C27046)
  - [`NCIT:C27198`](http://purl.obolibrary.org/obo/NCIT_C27198)
  - [`NCIT:C27299`](http://purl.obolibrary.org/obo/NCIT_C27299)
  - [`SNOMEDCT:14336007`](http://snomed.info/id/14336007)
  - [`SNOMEDCT:195258006`](http://snomed.info/id/195258006)
  - [`SNOMEDCT:195265003`](http://snomed.info/id/195265003)
  - [`SNOMEDCT:26660001`](http://snomed.info/id/26660001)
  - [`SNOMEDCT:67362008`](http://snomed.info/id/67362008)
  - [`SNOMEDCT:73067008`](http://snomed.info/id/73067008)
  - `SNOMEDCT_US_2025_09_01:14336007`
  - `SNOMEDCT_US_2025_09_01:155419006`
  - `SNOMEDCT_US_2025_09_01:195265003`
  - `SNOMEDCT_US_2025_09_01:34365005`
  - `SNOMEDCT_US_2025_09_01:73067008`
  - [`UMLS:C0003486`](http://identifiers.org/umls/C0003486)
  - [`UMLS:C0003496`](http://identifiers.org/umls/C0003496)
  - [`UMLS:C0265004`](http://identifiers.org/umls/C0265004)
  - [`UMLS:C0265010`](http://identifiers.org/umls/C0265010)
  - [`UMLS:C0265012`](http://identifiers.org/umls/C0265012)
  - [`UMLS:C0741160`](http://identifiers.org/umls/C0741160)
  - [`UMLS:C1305122`](http://identifiers.org/umls/C1305122)
- Clique with 49 identifiers — gains 1 new member(s) from MP:
  - [`DOID:11502`](http://purl.obolibrary.org/obo/DOID_11502) **(preferred)**
  - [`DOID:57`](http://purl.obolibrary.org/obo/DOID_57)
  - `Fyler:1151`
  - [`HP:0001653`](http://purl.obolibrary.org/obo/HP_0001653)
  - [`ICD10:I06.1`](https://icd.codes/icd9cm/I06.1)
  - [`ICD10:Q23.3`](https://icd.codes/icd9cm/Q23.3)
  - `ICD10CM:Q23.3`
  - [`ICD9:395.1`](http://translator.ncats.nih.gov/ICD9_395.1)
  - [`ICD9:396.3`](http://translator.ncats.nih.gov/ICD9_396.3)
  - [`ICD9:746.6`](http://translator.ncats.nih.gov/ICD9_746.6)
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
  - `MEDGEN:510600`
  - [`MESH:D001022`](http://id.nlm.nih.gov/mesh/D001022)
  - [`MESH:D008944`](http://id.nlm.nih.gov/mesh/D008944)
  - [`MONDO:0001298`](http://purl.obolibrary.org/obo/MONDO_0001298)
  - [`MP:0006045`](http://purl.obolibrary.org/obo/MP_0006045) **(new from MP)**
  - [`NCIT:C197881`](http://purl.obolibrary.org/obo/NCIT_C197881)
  - [`NCIT:C197951`](http://purl.obolibrary.org/obo/NCIT_C197951)
  - [`NCIT:C50852`](http://purl.obolibrary.org/obo/NCIT_C50852)
  - [`NCIT:C50861`](http://purl.obolibrary.org/obo/NCIT_C50861)
  - [`NCIT:C50888`](http://purl.obolibrary.org/obo/NCIT_C50888)
  - [`NCIT:C51223`](http://purl.obolibrary.org/obo/NCIT_C51223)
  - [`SNOMEDCT:194736003`](http://snomed.info/id/194736003)
  - [`SNOMEDCT:29928006`](http://snomed.info/id/29928006)
  - [`SNOMEDCT:48724000`](http://snomed.info/id/48724000)
  - `SNOMEDCT_US_2025_09_01:155283004`
  - `SNOMEDCT_US_2025_09_01:194736003`
  - `SNOMEDCT_US_2025_09_01:194977007`
  - `SNOMEDCT_US_2025_09_01:29928006`
  - `SNOMEDCT_US_2025_09_01:60234000`
  - [`UMLS:C0003504`](http://identifiers.org/umls/C0003504)
  - [`UMLS:C0026266`](http://identifiers.org/umls/C0026266)
  - [`UMLS:C0155568`](http://identifiers.org/umls/C0155568)
  - [`UMLS:C0158619`](http://identifiers.org/umls/C0158619)
  - [`UMLS:C0264774`](http://identifiers.org/umls/C0264774)
  - [`UMLS:C3551535`](http://identifiers.org/umls/C3551535)
  - `http://id.who.int/icd/entity/403917903`
