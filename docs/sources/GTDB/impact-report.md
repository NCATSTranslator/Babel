# Source impact report: GTDB

- Generated: 2026-07-29 04:33:32 UTC
- Babel commit: 3ca3000ee77dfec1d8e31f724ef3e5e093abf841
- Source pipelines: taxon
- Source prefixes: GTDB
- Comparison mode: synthetic

## 1. Identifiers added

Totals: 247,368 identifiers across 1 prefix(es) in 1 pipeline(s).

### By prefix

- GTDB: 247,368

### By pipeline

- taxon: 247,368

## 2. Biolink types

### Overall declared type breakdown

- biolink:OrganismTaxon: 247,368

### Source-declared (from each ids file)

- taxon / GTDB
  - biolink:OrganismTaxon: 247,368

### Final compendium-assigned (after glom)

- (no source identifiers found in any compendium)

## 3. Cross-references added

Totals: 297,327 cross-reference rows across 1 concord file(s).

### By pipeline

- taxon / GTDB: 297,327

### Partner prefix breakdown (per pipeline)

- taxon
  - NCBITaxon: 297,327

## 4. Clique impact

**Worst-case view.** This report is computed from the intermediate identifier and concord files and
cannot see downstream filtering that happens later in the build — most notably the Biolink Model's
per-class prefix restrictions, which drop identifiers whose prefix is not permitted for a clique's
biolink type. The counts and detail files below are therefore an *upper bound*: they show every
change the source could introduce before that filtering is applied.

### taxon

- 198,259 new cliques composed only of GTDB identifiers (a 5.81% increase over the 3,410,629
  pre-existing cliques)
- 49,109 existing cliques contain GTDB identifiers in the after state (1.44% of the 3,410,629
  pre-existing cliques). Of these, 49,109 cliques gain at least one structurally new identifier from
  GTDB, and 0 already contained the GTDB CURIE via an xref from another source — GTDB's ids file now
  also lists those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new GTDB cross-references
- 49,109 structurally-new GTDB identifiers are added to existing cliques (49,109 via expansion, 0
  via merges). This is distinct from the 49,109 existing cliques that change, since one clique can
  gain several identifiers.
- Total cliques in this pipeline go from 3,410,629 to 3,608,888
- Full list of new cliques: [`impact-report/new-cliques.csv`](impact-report/new-cliques.csv)
- Full list of modified cliques (one row per added/preexisting GTDB identifier):
  [`impact-report/modified-cliques.csv`](impact-report/modified-cliques.csv)
- Full list of new / activated cross-references:
  [`impact-report/new-xrefs.tsv`](impact-report/new-xrefs.tsv)

#### Sample pure-new cliques (up to 3)

- [`NCBITaxon:3074081`](http://purl.obolibrary.org/obo/NCBITaxon_3074081) **(preferred)**
  - `GTDB:s__Agromyces_sp031432265` "Agromyces sp031432265"
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:OrganismTaxon`)**
- [`NCBITaxon:2054916`](http://purl.obolibrary.org/obo/NCBITaxon_2054916) **(preferred)**
  - `GTDB:s__Aquipseudomonas_sp000955815` "Aquipseudomonas sp000955815"
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:OrganismTaxon`)**
- [`NCBITaxon:1588753`](http://purl.obolibrary.org/obo/NCBITaxon_1588753) **(preferred)**
  - `GTDB:s__Berryella_vaginalis` "Berryella vaginalis"
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:OrganismTaxon`)**

#### Sample expanded cliques (up to 3)

Of the 49,109 cliques that contain GTDB identifiers in the after state, 0 would also see their
preferred identifier change as a result of adding GTDB. The sample below leads with
preferred-id-change cliques (if any), then structurally grown cliques, then cliques where GTDB only
adds CURIEs that were already present via xref. Within each clique, identifiers are listed in the
same order they would appear in the compendium (biolink prefix priority, then lexicographic within
prefix).

- Clique with 4 identifiers — typed as `biolink:OrganismTaxon` — gains 1 new member(s) from GTDB:
  - [`NCBITaxon:519`](http://purl.obolibrary.org/obo/NCBITaxon_519) **(preferred)**
  - [`MESH:D042483`](http://id.nlm.nih.gov/mesh/D042483)
  - [`UMLS:C0300959`](http://identifiers.org/umls/C0300959)
  - `GTDB:s__2-02-FULL-62-17_sp945897475` "2-02-FULL-62-17 sp945897475" **(new from GTDB)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:OrganismTaxon`)**
- Clique with 4 identifiers — typed as `biolink:OrganismTaxon` — gains 1 new member(s) from GTDB:
  - [`NCBITaxon:191495`](http://purl.obolibrary.org/obo/NCBITaxon_191495) **(preferred)**
  - [`MESH:C000648565`](http://id.nlm.nih.gov/mesh/C000648565)
  - [`UMLS:C1214231`](http://identifiers.org/umls/C1214231)
  - `GTDB:s__67-14_sp040391885` "67-14 sp040391885" **(new from GTDB)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:OrganismTaxon`)**
- Clique with 4 identifiers — typed as `biolink:OrganismTaxon` — gains 1 new member(s) from GTDB:
  - [`NCBITaxon:1960156`](http://purl.obolibrary.org/obo/NCBITaxon_1960156) **(preferred)**
  - [`MESH:C000648116`](http://id.nlm.nih.gov/mesh/C000648116)
  - [`UMLS:C4569451`](http://identifiers.org/umls/C4569451)
  - `GTDB:s__Abditibacterium_utsteinense` "Abditibacterium utsteinense" **(new from GTDB)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:OrganismTaxon`)**
