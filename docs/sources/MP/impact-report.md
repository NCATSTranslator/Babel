# Source impact report: MP

- Generated: 2026-07-02 05:51:31 UTC
- Babel commit: 909e421fa6518e6de219d4e23dd3fceb84811255
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

- disease / PhenotypicFeature.txt: 14,750 MP identifiers

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

- 14,735 new cliques composed only of MP identifiers (a 3.46% increase over the 426,271 pre-existing
  cliques)
- 15 existing cliques contain MP identifiers in the after state (0.00% of the 426,271 pre-existing
  cliques). Of these, 0 cliques gain at least one structurally new identifier from MP, and 15
  already contained the MP CURIE via an xref from another source — MP's ids file now also lists
  those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new MP cross-references
- 0 structurally-new MP identifiers are added to existing cliques (0 via expansion, 0 via merges).
  This is distinct from the 0 existing cliques that change, since one clique can gain several
  identifiers.
- Total cliques in this pipeline go from 426,271 to 440,992
- Full list of new cliques: [`impact-report/new-cliques.csv`](impact-report/new-cliques.csv)
- Full list of modified cliques (one row per added/preexisting MP identifier):
  [`impact-report/modified-cliques.csv`](impact-report/modified-cliques.csv)
- Full list of new / activated cross-references:
  [`impact-report/new-xrefs.tsv`](impact-report/new-xrefs.tsv)

#### Sample pure-new cliques (up to 3)

- [`MP:0011253`](http://purl.obolibrary.org/obo/MP_0011253) "situs inversus with levocardia"
  **(preferred)**
  - `Fyler:0102`
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
  - `Fyler:102`
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
  - [`MPATH:714`](http://purl.obolibrary.org/obo/MPATH_714)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
- [`MP:0010913`](http://purl.obolibrary.org/obo/MP_0010913) "abnormal neuroendocrine cell
  morphology" **(preferred)**
  - [`CL:0000165`](http://purl.obolibrary.org/obo/CL_0000165)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
  - [`FMA:83810`](http://purl.obolibrary.org/obo/FMA_83810)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
- [`MP:0009942`](http://purl.obolibrary.org/obo/MP_0009942) "abnormal olfactory bulb granule cell
  morphology" **(preferred)**
  - [`CL:0000626`](http://purl.obolibrary.org/obo/CL_0000626)
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**
  - `NLX:nifext_123`
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:PhenotypicFeature`)**

#### Sample expanded cliques (up to 3)

Of the 15 cliques that contain MP identifiers in the after state, 0 would also see their preferred
identifier change as a result of adding MP. The sample below leads with preferred-id-change cliques
(if any), then structurally grown cliques, then cliques where MP only adds CURIEs that were already
present via xref. Within each clique, identifiers are listed in the same order they would appear in
the compendium (biolink prefix priority, then lexicographic within prefix).

- Clique with 2 identifiers — typed as `biolink:PhenotypicFeature` — MP CURIE already present via
  xref:
  - [`EFO:0005414`](http://www.ebi.ac.uk/efo/EFO_0005414) "airway hyperresponsiveness"
    **(preferred)**
  - [`MP:0001952`](http://purl.obolibrary.org/obo/MP_0001952) "increased airway responsiveness"
    **(existing identifier, also added by MP)**
- Clique with 12 identifiers — typed as `biolink:PhenotypicFeature` — MP CURIE already present via
  xref:
  - [`EFO:0009472`](http://www.ebi.ac.uk/efo/EFO_0009472) "tympanic membrane perforation"
    **(preferred)**
  - [`UMLS:C0206504`](http://identifiers.org/umls/C0206504) "Tympanic Membrane Perforation"
  - [`MEDDRA:10014006`](http://identifiers.org/meddra/10014006)
  - [`MEDDRA:10034391`](http://identifiers.org/meddra/10034391)
  - [`MEDDRA:10034424`](http://identifiers.org/meddra/10034424)
  - [`MEDDRA:10034425`](http://identifiers.org/meddra/10034425)
  - [`MEDDRA:10045210`](http://identifiers.org/meddra/10045210)
  - [`MP:0030414`](http://purl.obolibrary.org/obo/MP_0030414) "tympanic membrane perforation"
    **(existing identifier, also added by MP)**
  - [`SNOMEDCT:271743003`](http://snomed.info/id/271743003)
  - [`SNOMEDCT:60442001`](http://snomed.info/id/60442001)
  - [`MESH:D018058`](http://id.nlm.nih.gov/mesh/D018058) "Tympanic Membrane Perforation"
  - [`ICD10:H72`](https://icd.codes/icd9cm/H72)
- Clique with 5 identifiers — typed as `biolink:PhenotypicFeature` — MP CURIE already present via
  xref:
  - [`EFO:0009471`](http://www.ebi.ac.uk/efo/EFO_0009471) "small kidney" **(preferred)**
  - [`MEDDRA:10041135`](http://identifiers.org/meddra/10041135)
  - [`MEDDRA:10041137`](http://identifiers.org/meddra/10041137)
  - [`MP:0002989`](http://purl.obolibrary.org/obo/MP_0002989) "small kidney"
    **(existing identifier, also added by MP)**
  - [`ICD10:N27`](https://icd.codes/icd9cm/N27)
