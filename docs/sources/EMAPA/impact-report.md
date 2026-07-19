# Source impact report: EMAPA

- Generated: 2026-07-19 19:27:15 UTC
- Babel commit: a05580fa9c4f0974f5cfd96fff64a94ba01656fd
- Source pipelines: anatomy
- Source prefixes: EMAPA
- Comparison mode: synthetic

## 1. Identifiers added

Totals: 8,078 identifiers across 1 prefix(es) in 1 pipeline(s).

### By prefix

- EMAPA: 8,078

### By pipeline

- anatomy: 8,078

## 2. Biolink types

### Overall declared type breakdown

- biolink:AnatomicalEntity: 4,090
- biolink:GrossAnatomicalStructure: 3,988

### Source-declared (from each ids file)

- anatomy / EMAPA
  - biolink:AnatomicalEntity: 4,090
  - biolink:GrossAnatomicalStructure: 3,988

### Final compendium-assigned (after glom)

- anatomy / AnatomicalEntity.txt: 2,820 EMAPA identifiers
- anatomy / GrossAnatomicalStructure.txt: 5,256 EMAPA identifiers

## 3. Cross-references added

Totals: 0 cross-reference rows across 1 concord file(s).

### By pipeline

- anatomy / EMAPA: 0

### Partner prefix breakdown (per pipeline)

- anatomy
  - (no concord rows)

## 4. Clique impact

**Worst-case view.** This report is computed from the intermediate identifier and concord files and
cannot see downstream filtering that happens later in the build — most notably the Biolink Model's
per-class prefix restrictions, which drop identifiers whose prefix is not permitted for a clique's
biolink type. The counts and detail files below are therefore an *upper bound*: they show every
change the source could introduce before that filtering is applied.

### anatomy

- 3,890 new cliques composed only of EMAPA identifiers (a 2.22% increase over the 175,115
  pre-existing cliques)
- 4,188 existing cliques contain EMAPA identifiers in the after state (2.39% of the 175,115
  pre-existing cliques). Of these, 0 cliques gain at least one structurally new identifier from
  EMAPA, and 4,188 already contained the EMAPA CURIE via an xref from another source — EMAPA's ids
  file now also lists those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new EMAPA cross-references
- 0 structurally-new EMAPA identifiers are added to existing cliques (0 via expansion, 0 via
  merges). This is distinct from the 0 existing cliques that change, since one clique can gain
  several identifiers.
- Total cliques in this pipeline go from 175,115 to 179,005
- Full list of new cliques: [`impact-report/new-cliques.csv`](impact-report/new-cliques.csv)
- Full list of modified cliques (one row per added/preexisting EMAPA identifier):
  [`impact-report/modified-cliques.csv`](impact-report/modified-cliques.csv)
- Full list of new / activated cross-references:
  [`impact-report/new-xrefs.tsv`](impact-report/new-xrefs.tsv)

#### Sample pure-new cliques (up to 3)

- [`EMAPA:16032`](http://purl.obolibrary.org/obo/EMAPA_16032) "first polar body"
- [`EMAPA:16033`](http://purl.obolibrary.org/obo/EMAPA_16033) "1-cell stage embryo"
- [`EMAPA:16034`](http://purl.obolibrary.org/obo/EMAPA_16034) "second polar body"

#### Sample expanded cliques (up to 3)

Of the 4,188 cliques that contain EMAPA identifiers in the after state, 0 would also see their
preferred identifier change as a result of adding EMAPA. The sample below leads with
preferred-id-change cliques (if any), then structurally grown cliques, then cliques where EMAPA only
adds CURIEs that were already present via xref. Within each clique, identifiers are listed in the
same order they would appear in the compendium (biolink prefix priority, then lexicographic within
prefix).

- Clique with 16 identifiers — typed as `biolink:GrossAnatomicalStructure` — EMAPA CURIE already
  present via xref:
  - [`UBERON:0001237`](http://purl.obolibrary.org/obo/UBERON_0001237) "paraaortic body"
    **(preferred)**
  - [`UMLS:C0030378`](http://identifiers.org/umls/C0030378) "Corpora paraaortica"
  - [`UMLS:C0442134`](http://identifiers.org/umls/C0442134) "Para-aortic"
  - [`UMLS:C0456269`](http://identifiers.org/umls/C0456269) "Para-aortic region"
  - [`MESH:D010220`](http://id.nlm.nih.gov/mesh/D010220)
  - [`NCIT:C207628`](http://purl.obolibrary.org/obo/NCIT_C207628) "Para-aortic Body"
  - [`NCIT:C25316`](http://purl.obolibrary.org/obo/NCIT_C25316) "Paraaortic Region"
  - [`EMAPA:18223`](http://purl.obolibrary.org/obo/EMAPA_18223) "paraganglion of Zuckerkandl"
    **(existing identifier, also added by EMAPA)**
  - [`MA:0001137`](http://purl.obolibrary.org/obo/MA_0001137)
  - [`FMA:15647`](http://purl.obolibrary.org/obo/FMA_15647)
  - [`FMA:76539`](http://purl.obolibrary.org/obo/FMA_76539)
  - `GAID:444`
  - `SCTID:276159005`
  - [`SNOMEDCT:276910005`](http://snomed.info/id/276910005)
  - [`SNOMEDCT:90769006`](http://snomed.info/id/90769006)
  - `Wikipedia:Organ_of_Zuckerkandl`
- Clique with 18 identifiers — typed as `biolink:GrossAnatomicalStructure` — EMAPA CURIE already
  present via xref:
  - [`UBERON:0001694`](http://purl.obolibrary.org/obo/UBERON_0001694) "petrous part of temporal
    bone" **(preferred)**
  - [`UMLS:C0031266`](http://identifiers.org/umls/C0031266) "Structure of petrous part of temporal
    bone"
  - [`UMLS:C1261761`](http://identifiers.org/umls/C1261761) "Structure of ciliary processes"
  - [`MESH:D010579`](http://id.nlm.nih.gov/mesh/D010579)
  - [`NCIT:C32316`](http://purl.obolibrary.org/obo/NCIT_C32316) "Ciliary Process"
  - [`NCIT:C62643`](http://purl.obolibrary.org/obo/NCIT_C62643) "Petrous Apex"
  - [`EMAPA:17683`](http://purl.obolibrary.org/obo/EMAPA_17683) "temporal bone petrous part"
    **(existing identifier, also added by EMAPA)**
  - [`MA:0001477`](http://purl.obolibrary.org/obo/MA_0001477)
  - `EHDAA2:0001452`
  - [`FMA:52871`](http://purl.obolibrary.org/obo/FMA_52871)
  - [`FMA:58486`](http://purl.obolibrary.org/obo/FMA_58486)
  - [`FMA:76551`](http://purl.obolibrary.org/obo/FMA_76551)
  - `GAID:234`
  - `SCTID:361733004`
  - [`SNOMEDCT:25516004`](http://snomed.info/id/25516004)
  - [`SNOMEDCT:7345001`](http://snomed.info/id/7345001)
  - `VHOG:0001553`
  - `Wikipedia:Petrous_part_of_the_temporal_bone`
- Clique with 14 identifiers — typed as `biolink:GrossAnatomicalStructure` — EMAPA CURIE already
  present via xref:
  - [`UBERON:0000396`](http://purl.obolibrary.org/obo/UBERON_0000396) "vallate papilla"
    **(preferred)**
  - [`UMLS:C0226965`](http://identifiers.org/umls/C0226965) "Structure of vallate papillae of
    tongue"
  - [`UMLS:C1182961`](http://identifiers.org/umls/C1182961) "Set of vallate papillae"
  - [`UMLS:C1267555`](http://identifiers.org/umls/C1267555) "Entire vallate papillae of tongue"
  - [`NCIT:C32322`](http://purl.obolibrary.org/obo/NCIT_C32322) "Circumvallate Papilla"
  - [`EMAPA:18271`](http://purl.obolibrary.org/obo/EMAPA_18271) "circumvallate papillae"
    **(existing identifier, also added by EMAPA)**
  - [`MA:0001594`](http://purl.obolibrary.org/obo/MA_0001594)
  - `BIRNLEX:4106_2`
  - [`FMA:54822`](http://purl.obolibrary.org/obo/FMA_54822)
  - [`FMA:71449`](http://purl.obolibrary.org/obo/FMA_71449)
  - `SCTID:69517000`
  - [`SNOMEDCT:368729003`](http://snomed.info/id/368729003)
  - [`SNOMEDCT:69517000`](http://snomed.info/id/69517000)
  - `Wikipedia:Vallate_papilla`
