# Source impact report: EMAPA

- Generated: 2026-07-21 23:27:05 UTC
- Babel commit: cdca1d255a17d0c7f1b1bbd99efbd90d5f51a17e
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

- anatomy / AnatomicalEntity.txt: 2,787 EMAPA identifiers
- anatomy / GrossAnatomicalStructure.txt: 5,291 EMAPA identifiers

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

- 3,753 new cliques composed only of EMAPA identifiers (a 2.14% increase over the 175,117
  pre-existing cliques)
- 4,191 existing cliques contain EMAPA identifiers in the after state (2.39% of the 175,117
  pre-existing cliques). Of these, 0 cliques gain at least one structurally new identifier from
  EMAPA, and 4,191 already contained the EMAPA CURIE via an xref from another source — EMAPA's ids
  file now also lists those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new EMAPA cross-references
- 0 structurally-new EMAPA identifiers are added to existing cliques (0 via expansion, 0 via
  merges). This is distinct from the 0 existing cliques that change, since one clique can gain
  several identifiers.
- Total cliques in this pipeline go from 175,117 to 178,870
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

Of the 4,191 cliques that contain EMAPA identifiers in the after state, 0 would also see their
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
- Clique with 18 identifiers — typed as `biolink:AnatomicalEntity` — EMAPA CURIE already present via
  xref:
  - [`UBERON:0002256`](http://purl.obolibrary.org/obo/UBERON_0002256) "dorsal horn of spinal cord"
    **(preferred)**
  - [`UMLS:C0228564`](http://identifiers.org/umls/C0228564) "Spinal cord posterior horn"
  - [`UMLS:C0228575`](http://identifiers.org/umls/C0228575) "Structure of posterior gray horn of
    spinal cord"
  - [`MESH:D066148`](http://id.nlm.nih.gov/mesh/D066148)
  - [`NCIT:C32473`](http://purl.obolibrary.org/obo/NCIT_C32473) "Dorsal Horn of the Spinal Cord"
  - [`EMAPA:18574`](http://purl.obolibrary.org/obo/EMAPA_18574) "dorsal grey horn"
    **(existing identifier, also added by EMAPA)**
  - [`EMAPA:35790`](http://purl.obolibrary.org/obo/EMAPA_35790) "spinal cord dorsal horn"
    **(existing identifier, also added by EMAPA)**
  - [`ZFA:0000649`](http://purl.obolibrary.org/obo/ZFA_0000649)
  - [`FMA:256530`](http://purl.obolibrary.org/obo/FMA_256530)
  - `BIRNLEX:2667`
  - `BM:SpC-DH`
  - [`MA:0001119`](http://purl.obolibrary.org/obo/MA_0001119)
  - `SCTID:180961004`
  - [`SNOMEDCT:44985000`](http://snomed.info/id/44985000)
  - `TAO:0000649`
  - `VHOG:0001287`
  - `Wikipedia:Posterior_horn_of_spinal_cord`
  - `neuronames:1686`
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
