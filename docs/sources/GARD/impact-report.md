# Source impact report: GARD

- Generated: 2026-08-19 05:53:57 UTC
- Babel commit: 183907c558bae95a9bbfcb6f2f14f4e1e8eabb96
- Source pipelines: disease
- Source prefixes: GARD
- Comparison mode: synthetic

## 1. Identifiers added

Totals: 16,214 identifiers across 1 prefix(es) in 1 pipeline(s).

### By prefix

- GARD: 16,214

### By pipeline

- disease: 16,214

## 2. Biolink types

### Overall declared type breakdown

- biolink:Disease: 16,214

### Source-declared (from each ids file)

- disease / GARD
  - biolink:Disease: 16,214

### Final compendium-assigned (after glom)

- disease / Disease.txt: 16,214 GARD identifiers

## 3. Cross-references added

Totals: 0 cross-reference rows across 0 concord file(s).

### By pipeline

- disease / GARD: 0

### Partner prefix breakdown (per pipeline)

- disease
  - (no concord rows)

### Join pathways (every asserted cross-reference, not only this source's own)

`status` is `added` when GARD's own concord file asserts the pathway and `from_other_source` when
another source's does — the latter may predate this addition. The prefix pair is sorted, so
`asserted_by` is what tells you which side declared it.

| pipeline | predicate | prefix pair | asserted by | status | xrefs |
|---|---|---|---|---|---|
| disease | `xref` | GARD ↔ MONDO | `MONDO_GARD` | from_other_source | 16,212 |
| disease | `xref` | DOID ↔ GARD | `DOID` | from_other_source | 1,902 |

## 4. Clique impact

**Worst-case view.** This report is computed from the intermediate identifier and concord files and
cannot see downstream filtering that happens later in the build — most notably the Biolink Model's
per-class prefix restrictions, which drop identifiers whose prefix is not permitted for a clique's
biolink type. The counts and detail files below are therefore an *upper bound*: they show every
change the source could introduce before that filtering is applied.

### disease

- 277 new cliques composed only of GARD identifiers (a 0.06% increase over the 440,628 pre-existing
  cliques)
- 15,643 existing cliques contain GARD identifiers in the after state (3.55% of the 440,628
  pre-existing cliques). Of these, 0 cliques gain at least one structurally new identifier from
  GARD, and 15,643 already contained the GARD CURIE via an xref from another source — GARD's ids
  file now also lists those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new GARD cross-references
- 0 structurally-new GARD identifiers are added to existing cliques (0 via expansion, 0 via merges).
  This is distinct from the 0 existing cliques that change, since one clique can gain several
  identifiers.
- Total cliques in this pipeline go from 440,628 to 440,905
- Sample of new cliques (top 100, unsurvivable and largest first):
  [`impact-report/new-cliques-top-100.csv`](impact-report/new-cliques-top-100.csv)
- Full list of modified cliques (one row per added/preexisting GARD identifier):
  [`impact-report/modified-cliques.csv`](impact-report/modified-cliques.csv)
- Cross-reference summary (join pathways with counts and example rows):
  [`impact-report/new-xrefs-summary.csv`](impact-report/new-xrefs-summary.csv)

#### Sample pure-new cliques (up to 3)

- `GARD:15005` "Pacak-Zhung syndrome"
  **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
- `GARD:15006` "STAT5 Haploinsufficiency"
  **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
- `GARD:15009` "Monocytosis/myelocytosis, Autoimmunity, Gain of function, Immunodeficiency, Short
  stature" **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**

#### Sample expanded cliques (up to 3)

Of the 15,643 cliques that contain GARD identifiers in the after state, 0 would also see their
preferred identifier change as a result of adding GARD. The sample below leads with
preferred-id-change cliques (if any), then structurally grown cliques, then cliques where GARD only
adds CURIEs that were already present via xref. Within each clique, identifiers are listed in the
same order they would appear in the compendium (biolink prefix priority, then lexicographic within
prefix).

- Clique with 83 identifiers — typed as `biolink:Disease` — GARD CURIE already present via xref:
  - [`MONDO:0005055`](http://purl.obolibrary.org/obo/MONDO_0005055) "Kaposi's sarcoma"
    **(preferred)**
  - [`DOID:8632`](http://purl.obolibrary.org/obo/DOID_8632) "Kaposi's sarcoma"
  - [`orphanet:33276`](http://www.orpha.net/ORDO/Orphanet_33276)
  - [`EFO:0000558`](http://www.ebi.ac.uk/efo/EFO_0000558) "obsolete_Kaposi's sarcoma"
  - [`UMLS:C0036220`](http://identifiers.org/umls/C0036220) "Kaposi Sarcoma"
  - [`UMLS:C0153560`](http://identifiers.org/umls/C0153560) "Kaposi's sarcoma of skin"
  - [`UMLS:C0153561`](http://identifiers.org/umls/C0153561) "Kaposi's sarcoma of soft tissue"
  - [`UMLS:C0153562`](http://identifiers.org/umls/C0153562) "Kaposi's sarcoma of palate"
  - [`UMLS:C0153563`](http://identifiers.org/umls/C0153563) "Kaposi's sarcoma, gastrointestinal
    sites"
  - [`UMLS:C0153564`](http://identifiers.org/umls/C0153564) "Kaposi's sarcoma of lung"
  - [`UMLS:C0153565`](http://identifiers.org/umls/C0153565) "Kaposi's sarcoma of lymph nodes"
  - [`UMLS:C0346935`](http://identifiers.org/umls/C0346935) "Kaposi's sarcoma of conjunctiva"
  - [`UMLS:C0346936`](http://identifiers.org/umls/C0346936) "Kaposi's sarcoma of cornea"
  - [`UMLS:C1332265`](http://identifiers.org/umls/C1332265) "Anal Kaposi Sarcoma"
  - [`UMLS:C1332847`](http://identifiers.org/umls/C1332847) "Cardiac Kaposi's Sarcoma"
  - [`UMLS:C1333453`](http://identifiers.org/umls/C1333453) "Kaposi's sarcoma of esophagus"
  - [`UMLS:C1333744`](http://identifiers.org/umls/C1333744) "Gallbladder Kaposi's Sarcoma"
  - [`UMLS:C1333776`](http://identifiers.org/umls/C1333776) "Gastric Kaposi's Sarcoma"
  - [`UMLS:C1334318`](http://identifiers.org/umls/C1334318) "Central Nervous System Kaposi Sarcoma"
  - [`UMLS:C1334457`](http://identifiers.org/umls/C1334457) "Lymphadenopathic Kaposi Sarcoma"
  - [`UMLS:C1335372`](http://identifiers.org/umls/C1335372) "Kaposi's sarcoma of penis"
  - [`UMLS:C1335509`](http://identifiers.org/umls/C1335509) "Prostate Kaposi Sarcoma"
  - [`MESH:D012514`](http://id.nlm.nih.gov/mesh/D012514) "Sarcoma, Kaposi"
  - [`MEDDRA:10023284`](http://identifiers.org/meddra/10023284)
  - [`MEDDRA:10023285`](http://identifiers.org/meddra/10023285)
  - [`MEDDRA:10023290`](http://identifiers.org/meddra/10023290)
  - [`MEDDRA:10023291`](http://identifiers.org/meddra/10023291)
  - [`MEDDRA:10023292`](http://identifiers.org/meddra/10023292)
  - [`MEDDRA:10023293`](http://identifiers.org/meddra/10023293)
  - [`MEDDRA:10023295`](http://identifiers.org/meddra/10023295)
  - [`MEDDRA:10023296`](http://identifiers.org/meddra/10023296)
  - [`MEDDRA:10023297`](http://identifiers.org/meddra/10023297)
  - [`MEDDRA:10023298`](http://identifiers.org/meddra/10023298)
  - [`MEDDRA:10028220`](http://identifiers.org/meddra/10028220)
  - [`MEDDRA:10028221`](http://identifiers.org/meddra/10028221)
  - [`MEDDRA:10028222`](http://identifiers.org/meddra/10028222)
  - [`MEDDRA:10055863`](http://identifiers.org/meddra/10055863)
  - [`NCIT:C194225`](http://purl.obolibrary.org/obo/NCIT_C194225) "Kaposi's Sarcoma of Soft Tissue"
  - [`NCIT:C27500`](http://purl.obolibrary.org/obo/NCIT_C27500) "Lymphadenopathic Kaposi Sarcoma"
  - [`NCIT:C3550`](http://purl.obolibrary.org/obo/NCIT_C3550) "Skin Kaposi Sarcoma"
  - [`NCIT:C3551`](http://purl.obolibrary.org/obo/NCIT_C3551) "Lung Kaposi Sarcoma"
  - [`NCIT:C4578`](http://purl.obolibrary.org/obo/NCIT_C4578) "Conjunctival Kaposi Sarcoma"
  - [`NCIT:C4579`](http://purl.obolibrary.org/obo/NCIT_C4579) "Corneal Kaposi Sarcoma"
  - [`NCIT:C5363`](http://purl.obolibrary.org/obo/NCIT_C5363) "Cardiac Kaposi Sarcoma"
  - [`NCIT:C5523`](http://purl.obolibrary.org/obo/NCIT_C5523) "Prostate Kaposi Sarcoma"
  - [`NCIT:C5529`](http://purl.obolibrary.org/obo/NCIT_C5529) "Gastric Kaposi Sarcoma"
  - [`NCIT:C5602`](http://purl.obolibrary.org/obo/NCIT_C5602) "Anal Kaposi Sarcoma"
  - [`NCIT:C5706`](http://purl.obolibrary.org/obo/NCIT_C5706) "Esophageal Kaposi Sarcoma"
  - [`NCIT:C5842`](http://purl.obolibrary.org/obo/NCIT_C5842) "Gallbladder Kaposi Sarcoma"
  - [`NCIT:C6377`](http://purl.obolibrary.org/obo/NCIT_C6377) "Penile Kaposi Sarcoma"
  - [`NCIT:C6749`](http://purl.obolibrary.org/obo/NCIT_C6749) "Palate Kaposi Sarcoma"
  - [`NCIT:C7006`](http://purl.obolibrary.org/obo/NCIT_C7006) "Central Nervous System Kaposi
    Sarcoma"
  - [`NCIT:C9087`](http://purl.obolibrary.org/obo/NCIT_C9087) "Kaposi Sarcoma"
  - [`SNOMEDCT:109385007`](http://snomed.info/id/109385007)
  - [`SNOMEDCT:109386008`](http://snomed.info/id/109386008)
  - [`SNOMEDCT:109388009`](http://snomed.info/id/109388009)
  - [`SNOMEDCT:109390005`](http://snomed.info/id/109390005)
  - [`SNOMEDCT:109391009`](http://snomed.info/id/109391009)
  - [`SNOMEDCT:1179374007`](http://snomed.info/id/1179374007)
  - [`SNOMEDCT:188029000`](http://snomed.info/id/188029000)
  - [`SNOMEDCT:188144002`](http://snomed.info/id/188144002)
  - [`SNOMEDCT:188775002`](http://snomed.info/id/188775002)
  - [`SNOMEDCT:255114007`](http://snomed.info/id/255114007)
  - [`SNOMEDCT:255115008`](http://snomed.info/id/255115008)
  - [`SNOMEDCT:49937004`](http://snomed.info/id/49937004)
  - `MEDGEN:11321`
  - [`ICD10:C46`](https://icd.codes/icd9cm/C46)
  - [`ICD10:C46.0`](https://icd.codes/icd9cm/C46.0)
  - [`ICD10:C46.1`](https://icd.codes/icd9cm/C46.1)
  - [`ICD10:C46.2`](https://icd.codes/icd9cm/C46.2)
  - [`ICD10:C46.3`](https://icd.codes/icd9cm/C46.3)
  - [`ICD10:C46.4`](https://icd.codes/icd9cm/C46.4)
  - [`ICD10:C46.5`](https://icd.codes/icd9cm/C46.5)
  - [`ICD9:176`](http://translator.ncats.nih.gov/ICD9_176)
  - [`ICD9:176.0`](http://translator.ncats.nih.gov/ICD9_176.0)
  - [`ICD9:176.1`](http://translator.ncats.nih.gov/ICD9_176.1)
  - [`ICD9:176.2`](http://translator.ncats.nih.gov/ICD9_176.2)
  - [`ICD9:176.3`](http://translator.ncats.nih.gov/ICD9_176.3)
  - [`ICD9:176.4`](http://translator.ncats.nih.gov/ICD9_176.4)
  - [`ICD9:176.5`](http://translator.ncats.nih.gov/ICD9_176.5)
  - [`HP:0100726`](http://purl.obolibrary.org/obo/HP_0100726) "Kaposi's sarcoma"
  - `GARD:6814` "Kaposi sarcoma" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `ICD10CM:C46`
- Clique with 99 identifiers — typed as `biolink:Disease` — GARD CURIE already present via xref:
  - [`MONDO:0001275`](http://purl.obolibrary.org/obo/MONDO_0001275) "spinal meningioma"
    **(preferred)**
  - [`DOID:0080842`](http://purl.obolibrary.org/obo/DOID_0080842) "intracranial meningioma"
  - [`DOID:0080843`](http://purl.obolibrary.org/obo/DOID_0080843) "supratentorial meningioma"
  - [`DOID:1138`](http://purl.obolibrary.org/obo/DOID_1138) "spinal meningioma"
  - [`DOID:12689`](http://purl.obolibrary.org/obo/DOID_12689) "acoustic neuroma"
  - [`DOID:3565`](http://purl.obolibrary.org/obo/DOID_3565) "meningioma"
  - [`DOID:3772`](http://purl.obolibrary.org/obo/DOID_3772) "intraventricular meningioma"
  - [`DOID:4141`](http://purl.obolibrary.org/obo/DOID_4141) "intraorbital meningioma"
  - [`DOID:4210`](http://purl.obolibrary.org/obo/DOID_4210) "clear cell meningioma"
  - [`DOID:4211`](http://purl.obolibrary.org/obo/DOID_4211) "posterior fossa meningioma"
  - [`DOID:4587`](http://purl.obolibrary.org/obo/DOID_4587) "benign meningioma"
  - [`DOID:4588`](http://purl.obolibrary.org/obo/DOID_4588) "secretory meningioma"
  - [`DOID:4594`](http://purl.obolibrary.org/obo/DOID_4594) "microcystic meningioma"
  - [`DOID:6114`](http://purl.obolibrary.org/obo/DOID_6114) "cerebral convexity meningioma"
  - [`DOID:6548`](http://purl.obolibrary.org/obo/DOID_6548) "angiomatous meningioma"
  - [`DOID:6869`](http://purl.obolibrary.org/obo/DOID_6869) "parasagittal meningioma"
  - [`DOID:7210`](http://purl.obolibrary.org/obo/DOID_7210) "psammomatous meningioma"
  - [`DOID:7211`](http://purl.obolibrary.org/obo/DOID_7211) "fibrous meningioma"
  - [`DOID:7212`](http://purl.obolibrary.org/obo/DOID_7212) "meningothelial meningioma"
  - [`DOID:7213`](http://purl.obolibrary.org/obo/DOID_7213) "transitional meningioma"
  - [`DOID:8057`](http://purl.obolibrary.org/obo/DOID_8057) "olfactory groove meningioma"
  - [`UMLS:C0025286`](http://identifiers.org/umls/C0025286) "Meningioma"
  - [`UMLS:C0027859`](http://identifiers.org/umls/C0027859) "Acoustic Neuroma"
  - [`UMLS:C0281784`](http://identifiers.org/umls/C0281784) "Benign Meningioma"
  - [`UMLS:C0334605`](http://identifiers.org/umls/C0334605) "Meningothelial meningioma"
  - [`UMLS:C0334606`](http://identifiers.org/umls/C0334606) "Fibrous Meningioma"
  - [`UMLS:C0334607`](http://identifiers.org/umls/C0334607) "Psammomatous Meningioma"
  - [`UMLS:C0334608`](http://identifiers.org/umls/C0334608) "Angiomatous Meningioma"
  - [`UMLS:C0334611`](http://identifiers.org/umls/C0334611) "Transitional Meningioma"
  - [`UMLS:C0347515`](http://identifiers.org/umls/C0347515) "Spinal Cord Meningioma"
  - [`UMLS:C0349604`](http://identifiers.org/umls/C0349604) "Intracranial Meningioma"
  - [`UMLS:C0431121`](http://identifiers.org/umls/C0431121) "Clear Cell Meningioma"
  - [`UMLS:C0751303`](http://identifiers.org/umls/C0751303) "Cerebral Convexity Meningioma"
  - [`UMLS:C0751304`](http://identifiers.org/umls/C0751304) "Parasagittal Meningioma"
  - [`UMLS:C1334261`](http://identifiers.org/umls/C1334261) "Intraorbital Meningioma"
  - [`UMLS:C1334271`](http://identifiers.org/umls/C1334271) "Intraventricular Meningioma"
  - [`UMLS:C1334698`](http://identifiers.org/umls/C1334698) "Meningothelial Cell Neoplasm"
  - [`UMLS:C1335107`](http://identifiers.org/umls/C1335107) "Olfactory Groove Meningioma"
  - [`UMLS:C1384406`](http://identifiers.org/umls/C1384406) "Secretory meningioma"
  - [`UMLS:C1384408`](http://identifiers.org/umls/C1384408) "Microcystic meningioma"
  - [`UMLS:C1565950`](http://identifiers.org/umls/C1565950) "Posterior Fossa Meningioma"
  - [`MESH:D008579`](http://id.nlm.nih.gov/mesh/D008579) "Meningioma"
  - [`MESH:D009464`](http://id.nlm.nih.gov/mesh/D009464) "Neuroma, Acoustic"
  - [`MEDDRA:10000522`](http://identifiers.org/meddra/10000522)
  - [`MEDDRA:10000523`](http://identifiers.org/meddra/10000523)
  - [`MEDDRA:10004290`](http://identifiers.org/meddra/10004290)
  - [`MEDDRA:10027191`](http://identifiers.org/meddra/10027191)
  - [`MEDDRA:10027192`](http://identifiers.org/meddra/10027192)
  - [`MEDDRA:10027195`](http://identifiers.org/meddra/10027195)
  - [`MEDDRA:10048925`](http://identifiers.org/meddra/10048925)
  - [`MEDDRA:10067793`](http://identifiers.org/meddra/10067793)
  - [`MEDDRA:10083886`](http://identifiers.org/meddra/10083886)
  - [`MEDDRA:10089129`](http://identifiers.org/meddra/10089129)
  - [`MEDDRA:10090334`](http://identifiers.org/meddra/10090334)
  - [`NCIT:C3230`](http://purl.obolibrary.org/obo/NCIT_C3230) "Meningioma"
  - [`NCIT:C3276`](http://purl.obolibrary.org/obo/NCIT_C3276) "Vestibular Schwannoma"
  - [`NCIT:C4329`](http://purl.obolibrary.org/obo/NCIT_C4329) "Meningothelial Meningioma"
  - [`NCIT:C4330`](http://purl.obolibrary.org/obo/NCIT_C4330) "Fibrous Meningioma"
  - [`NCIT:C4331`](http://purl.obolibrary.org/obo/NCIT_C4331) "Psammomatous Meningioma"
  - [`NCIT:C4332`](http://purl.obolibrary.org/obo/NCIT_C4332) "Angiomatous Meningioma"
  - [`NCIT:C4333`](http://purl.obolibrary.org/obo/NCIT_C4333) "Transitional Meningioma"
  - [`NCIT:C4656`](http://purl.obolibrary.org/obo/NCIT_C4656) "Intracranial Meningioma"
  - [`NCIT:C4718`](http://purl.obolibrary.org/obo/NCIT_C4718) "Secretory Meningioma"
  - [`NCIT:C4721`](http://purl.obolibrary.org/obo/NCIT_C4721) "Microcystic Meningioma"
  - [`NCIT:C4722`](http://purl.obolibrary.org/obo/NCIT_C4722) "Clear Cell Meningioma"
  - [`NCIT:C4959`](http://purl.obolibrary.org/obo/NCIT_C4959) "Cerebral Convexity Meningioma"
  - [`NCIT:C4960`](http://purl.obolibrary.org/obo/NCIT_C4960) "Parasagittal Meningioma"
  - [`NCIT:C5273`](http://purl.obolibrary.org/obo/NCIT_C5273) "Intraventricular Meningioma"
  - [`NCIT:C6771`](http://purl.obolibrary.org/obo/NCIT_C6771) "Olfactory Groove Meningioma"
  - [`NCIT:C6775`](http://purl.obolibrary.org/obo/NCIT_C6775) "Posterior Fossa Meningioma"
  - [`NCIT:C6778`](http://purl.obolibrary.org/obo/NCIT_C6778) "Orbital Meningioma"
  - [`NCIT:C6935`](http://purl.obolibrary.org/obo/NCIT_C6935) "Spinal Cord Meningioma"
  - [`NCIT:C6971`](http://purl.obolibrary.org/obo/NCIT_C6971) "Meningothelial Cell Neoplasm"
  - [`SNOMEDCT:1157019008`](http://snomed.info/id/1157019008)
  - [`SNOMEDCT:134213009`](http://snomed.info/id/134213009)
  - [`SNOMEDCT:1373614004`](http://snomed.info/id/1373614004)
  - [`SNOMEDCT:189167009`](http://snomed.info/id/189167009)
  - [`SNOMEDCT:253081009`](http://snomed.info/id/253081009)
  - [`SNOMEDCT:253084001`](http://snomed.info/id/253084001)
  - [`SNOMEDCT:269643009`](http://snomed.info/id/269643009)
  - [`SNOMEDCT:302820008`](http://snomed.info/id/302820008)
  - [`SNOMEDCT:38431002`](http://snomed.info/id/38431002)
  - [`SNOMEDCT:393566004`](http://snomed.info/id/393566004)
  - [`SNOMEDCT:511008`](http://snomed.info/id/511008)
  - [`SNOMEDCT:64967004`](http://snomed.info/id/64967004)
  - [`SNOMEDCT:68944005`](http://snomed.info/id/68944005)
  - [`SNOMEDCT:73918009`](http://snomed.info/id/73918009)
  - `MEDGEN:87576`
  - [`ICD10:D32.9`](https://icd.codes/icd9cm/D32.9)
  - [`HP:0002858`](http://purl.obolibrary.org/obo/HP_0002858) "Meningioma"
  - `GARD:10264` "Spinal meningioma" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:223` "Acoustic neuroma" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:7015` "Meningioma" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `ICD0:9530/0`
  - `ICD0:9531/0`
  - `ICD0:9532/0`
  - `ICD0:9533/0`
  - `ICD0:9534/0`
  - `ICD0:9537/0`
- Clique with 68 identifiers — typed as `biolink:Disease` — GARD CURIE already present via xref:
  - [`MONDO:0004604`](http://purl.obolibrary.org/obo/MONDO_0004604) "Hodgkin's lymphoma,
    lymphocytic-histiocytic predominance" **(preferred)**
  - [`DOID:8543`](http://purl.obolibrary.org/obo/DOID_8543) "Hodgkin's lymphoma,
    lymphocytic-histiocytic predominance"
  - [`DOID:8567`](http://purl.obolibrary.org/obo/DOID_8567) "Hodgkin's lymphoma"
  - [`DOID:8628`](http://purl.obolibrary.org/obo/DOID_8628) "Hodgkin's lymphoma, lymphocytic
    depletion"
  - [`DOID:8642`](http://purl.obolibrary.org/obo/DOID_8642) "Hodgkin's paragranuloma"
  - [`DOID:8654`](http://purl.obolibrary.org/obo/DOID_8654) "Hodgkin's lymphoma, mixed cellularity"
  - [`OMIM:236000`](http://purl.obolibrary.org/obo/OMIM_236000)
  - [`OMIM:300221`](http://purl.obolibrary.org/obo/OMIM_300221)
  - [`OMIM:400021`](http://purl.obolibrary.org/obo/OMIM_400021)
  - [`orphanet:98293`](http://www.orpha.net/ORDO/Orphanet_98293)
  - [`orphanet:98845`](http://www.orpha.net/ORDO/Orphanet_98845)
  - [`EFO:0000183`](http://www.ebi.ac.uk/efo/EFO_0000183) "obsolete_Hodgkins lymphoma"
  - [`UMLS:C0019829`](http://identifiers.org/umls/C0019829) "Hodgkin Disease"
  - [`UMLS:C0152266`](http://identifiers.org/umls/C0152266) "Mixed Cellularity Hodgkin Lymphoma"
  - [`UMLS:C0152267`](http://identifiers.org/umls/C0152267) "Hodgkin lymphoma, lymphocyte depletion"
  - [`UMLS:C1266194`](http://identifiers.org/umls/C1266194) "Lymphocyte Rich Classical Hodgkin
    Lymphoma"
  - [`UMLS:C5235037`](http://identifiers.org/umls/C5235037) "Hodgkin sarcoma"
  - [`MESH:D006689`](http://id.nlm.nih.gov/mesh/D006689) "Hodgkin Disease"
  - [`MEDDRA:10020206`](http://identifiers.org/meddra/10020206)
  - [`MEDDRA:10020219`](http://identifiers.org/meddra/10020219)
  - [`MEDDRA:10020231`](http://identifiers.org/meddra/10020231)
  - [`MEDDRA:10020232`](http://identifiers.org/meddra/10020232)
  - [`MEDDRA:10020242`](http://identifiers.org/meddra/10020242)
  - [`MEDDRA:10020255`](http://identifiers.org/meddra/10020255)
  - [`MEDDRA:10020272`](http://identifiers.org/meddra/10020272)
  - [`MEDDRA:10020281`](http://identifiers.org/meddra/10020281)
  - [`MEDDRA:10020290`](http://identifiers.org/meddra/10020290)
  - [`MEDDRA:10020309`](http://identifiers.org/meddra/10020309)
  - [`MEDDRA:10020318`](http://identifiers.org/meddra/10020318)
  - [`MEDDRA:10020328`](http://identifiers.org/meddra/10020328)
  - [`MEDDRA:10020329`](http://identifiers.org/meddra/10020329)
  - [`MEDDRA:10020339`](http://identifiers.org/meddra/10020339)
  - [`MEDDRA:10025319`](http://identifiers.org/meddra/10025319)
  - [`MEDDRA:10063666`](http://identifiers.org/meddra/10063666)
  - [`NCIT:C164145`](http://purl.obolibrary.org/obo/NCIT_C164145) "Hodgkin's Sarcoma"
  - [`NCIT:C26956`](http://purl.obolibrary.org/obo/NCIT_C26956) "Hodgkin's Paragranuloma"
  - [`NCIT:C3517`](http://purl.obolibrary.org/obo/NCIT_C3517) "Mixed Cellularity Classic Hodgkin
    Lymphoma"
  - [`NCIT:C6913`](http://purl.obolibrary.org/obo/NCIT_C6913) "Lymphocyte-Rich Classic Hodgkin
    Lymphoma"
  - [`NCIT:C6914`](http://purl.obolibrary.org/obo/NCIT_C6914) "Hodgkin's Granuloma"
  - [`NCIT:C9283`](http://purl.obolibrary.org/obo/NCIT_C9283) "Lymphocyte-Depleted Classic Hodgkin
    Lymphoma"
  - [`NCIT:C9357`](http://purl.obolibrary.org/obo/NCIT_C9357) "Hodgkin Lymphoma"
  - [`SNOMEDCT:112687003`](http://snomed.info/id/112687003)
  - [`SNOMEDCT:1163005009`](http://snomed.info/id/1163005009)
  - [`SNOMEDCT:118599009`](http://snomed.info/id/118599009)
  - [`SNOMEDCT:118602004`](http://snomed.info/id/118602004)
  - [`SNOMEDCT:118605002`](http://snomed.info/id/118605002)
  - [`SNOMEDCT:118606001`](http://snomed.info/id/118606001)
  - [`SNOMEDCT:118607005`](http://snomed.info/id/118607005)
  - [`SNOMEDCT:118609008`](http://snomed.info/id/118609008)
  - [`SNOMEDCT:128799007`](http://snomed.info/id/128799007)
  - [`SNOMEDCT:14537002`](http://snomed.info/id/14537002)
  - [`SNOMEDCT:41529000`](http://snomed.info/id/41529000)
  - [`SNOMEDCT:46923007`](http://snomed.info/id/46923007)
  - [`SNOMEDCT:70600005`](http://snomed.info/id/70600005)
  - [`SNOMEDCT:74189002`](http://snomed.info/id/74189002)
  - [`SNOMEDCT:836276000`](http://snomed.info/id/836276000)
  - [`SNOMEDCT:836277009`](http://snomed.info/id/836277009)
  - `MEDGEN:224769`
  - [`ICD10:C81.2`](https://icd.codes/icd9cm/C81.2)
  - [`ICD10:C81.3`](https://icd.codes/icd9cm/C81.3)
  - [`ICD10:C81.4`](https://icd.codes/icd9cm/C81.4)
  - [`ICD9:201.4`](http://translator.ncats.nih.gov/ICD9_201.4)
  - [`ICD9:201.6`](http://translator.ncats.nih.gov/ICD9_201.6)
  - [`ICD9:201.7`](http://translator.ncats.nih.gov/ICD9_201.7)
  - [`HP:0012189`](http://purl.obolibrary.org/obo/HP_0012189) "Hodgkin lymphoma"
  - `GARD:19593` "Classic Hodgkin lymphoma, lymphocyte-rich type"
    **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:2714` "Hodgkins lymphoma" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `http://id.who.int/icd/entity/352299041`
