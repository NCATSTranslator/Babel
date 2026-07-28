# Source impact report: GARD

- Generated: 2026-07-28 21:53:18 UTC
- Babel commit: 093b64e937c08ee1d740537b228ac202d5753c4a
- Source pipelines: disease
- Source prefixes: GARD
- Comparison mode: synthetic

## 1. Identifiers added

Totals: 6,265 identifiers across 1 prefix(es) in 1 pipeline(s).

### By prefix

- GARD: 6,265

### By pipeline

- disease: 6,265

## 2. Biolink types

### Overall declared type breakdown

- biolink:Disease: 6,265

### Source-declared (from each ids file)

- disease / GARD
  - biolink:Disease: 6,265

### Final compendium-assigned (after glom)

- (no source identifiers found in any compendium)

## 3. Cross-references added

Totals: 0 cross-reference rows across 0 concord file(s).

### By pipeline

- disease / GARD: 0

### Partner prefix breakdown (per pipeline)

- disease
  - (no concord rows)

## 4. Clique impact

**Worst-case view.** This report is computed from the intermediate identifier and concord files and
cannot see downstream filtering that happens later in the build — most notably the Biolink Model's
per-class prefix restrictions, which drop identifiers whose prefix is not permitted for a clique's
biolink type. The counts and detail files below are therefore an *upper bound*: they show every
change the source could introduce before that filtering is applied.

### disease

- 6,265 new cliques composed only of GARD identifiers (a 2.60% increase over the 241,269
  pre-existing cliques)
- 0 existing cliques contain GARD identifiers in the after state (0.00% of the 241,269 pre-existing
  cliques). Of these, 0 cliques gain at least one structurally new identifier from GARD, and 0
  already contained the GARD CURIE via an xref from another source — GARD's ids file now also lists
  those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new GARD cross-references
- 0 structurally-new GARD identifiers are added to existing cliques (0 via expansion, 0 via merges).
  This is distinct from the 0 existing cliques that change, since one clique can gain several
  identifiers.
- Total cliques in this pipeline go from 241,269 to 247,534
- Full list of new cliques: [`impact-report/new-cliques.csv`](impact-report/new-cliques.csv)
- Full list of modified cliques (one row per added/preexisting GARD identifier):
  [`impact-report/modified-cliques.csv`](impact-report/modified-cliques.csv)
- Full list of new / activated cross-references:
  [`impact-report/new-xrefs.tsv`](impact-report/new-xrefs.tsv)

#### Sample pure-new cliques (up to 3)

- `GARD:0000001` "GRACILE syndrome"
  **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
- `GARD:0000003` "Ablepharon macrostomia syndrome"
  **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
- `GARD:0000005` "Abetalipoproteinaemia"
  **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
