# Source impact report: PO

- Generated: 2026-11-24 04:40:32 UTC
- Babel commit: b0d1af6372aeef0d56159c856a07e5561d8cdaf7
- Source pipelines: anatomy
- Source prefixes: PO
- Source concords: PO
- Comparison mode: synthetic

## 1. Identifiers added

Totals: 1,312 identifiers across 1 prefix(es) in 1 pipeline(s).

### By prefix

- PO: 1,312

### By pipeline

- anatomy: 1,312

## 2. Biolink types

### Overall declared type breakdown

- biolink:Cell: 206
- biolink:GrossAnatomicalStructure: 1,106

### Source-declared (from each ids file)

- anatomy / PO
  - biolink:Cell: 206
  - biolink:GrossAnatomicalStructure: 1,106

### Final compendium-assigned (after glom)

- anatomy / Cell.txt: 206 PO identifiers
- anatomy / GrossAnatomicalStructure.txt: 1,106 PO identifiers

## 3. Cross-references added

Totals: 75 cross-reference rows across 1 concord file(s).

### By pipeline

- anatomy / PO: 75

### Partner prefix breakdown (per pipeline)

- anatomy
  - NCIT: 44
  - MESH: 31

### Join pathways (every asserted cross-reference, not only this source's own)

`status` is `added` when one of PO's own concord files asserts the pathway and `from_other_source`
when another source's does — the latter may predate this addition. The prefix pair is sorted, so
`asserted_by` is what tells you which side declared it.

| pipeline | predicate | prefix pair | asserted by | status | xrefs |
|---|---|---|---|---|---|
| anatomy | `label_match` | NCIT ↔ PO | `PO` | added | 44 |
| anatomy | `label_match` | MESH ↔ PO | `PO` | added | 31 |

## 4. Clique impact

**Worst-case view.** This report is computed from the intermediate identifier and concord files and
cannot see downstream filtering that happens later in the build — most notably the Biolink Model's
per-class prefix restrictions, which drop identifiers whose prefix is not permitted for a clique's
biolink type. The counts and detail files below are therefore an _upper bound_: they show every
change the source could introduce before that filtering is applied.

### anatomy

- 1,250 new cliques composed only of PO identifiers (a 0.70% increase over the 177,508 pre-existing
  cliques)
- 60 existing cliques contain PO identifiers in the after state (0.03% of the 177,508 pre-existing
  cliques). Of these, 60 cliques gain at least one structurally new identifier from PO, and 0
  already contained the PO CURIE via an xref from another source — PO's ids file now also lists
  those existing CURIEs as first-class typed identifiers.
- 2 existing cliques will be merged because of new PO cross-references
- 62 structurally-new PO identifiers are added to existing cliques (60 via expansion, 2 via merges).
  This is distinct from the 62 existing cliques that change, since one clique can gain several
  identifiers.
- Total cliques in this pipeline go from 177,508 to 178,756
- Sample of new cliques (top 100, unsurvivable and largest first):
  [`impact-report/new-cliques-top-100.csv`](impact-report/new-cliques-top-100.csv)
- Full list of modified cliques (one row per added/preexisting PO identifier):
  `impact-report/modified-cliques.csv` -- not committed (see `.gitignore`); regenerate it with
  `uv run source-impact-report`
- Cross-reference summary (join pathways with counts and example rows):
  [`impact-report/new-xrefs-summary.csv`](impact-report/new-xrefs-summary.csv)

#### Sample merges (up to 3)

- PO:0004518 bridges MESH:D024301, NCIT:C79615
- PO:0003023 bridges MESH:D053204, NCIT:C79693

#### Sample pure-new cliques (up to 3)

- [`PO:0000001`](http://purl.obolibrary.org/obo/PO_0000001) "plant embryo proper"
- [`PO:0000002`](http://purl.obolibrary.org/obo/PO_0000002) "anther wall"
- [`PO:0000004`](http://purl.obolibrary.org/obo/PO_0000004) "in vitro plant structure"

#### Sample expanded cliques (up to 3)

Of the 60 cliques that contain PO identifiers in the after state, 2 would also see their preferred
identifier change as a result of adding PO. The sample below leads with preferred-id-change cliques
(if any), then structurally grown cliques, then cliques where PO only adds CURIEs that were already
present via xref. Within each clique, identifiers are listed in the same order they would appear in
the compendium (biolink prefix priority, then lexicographic within prefix).

- Clique with 3 identifiers — typed as `biolink:Cell` — preferred identifier changes; gains 1 new
  member(s) from PO:
  - [`PO:0004006`](http://purl.obolibrary.org/obo/PO_0004006) "mesophyll cell" **(new from PO)**
    **(preferred)**
  - [`UMLS:C2936408`](http://identifiers.org/umls/C2936408) _(was preferred before)_
  - [`MESH:D058503`](http://id.nlm.nih.gov/mesh/D058503) "Mesophyll Cells"
- Clique with 2 identifiers — typed as `biolink:Cell` — preferred identifier changes; gains 1 new
  member(s) from PO:
  - [`PO:0025407`](http://purl.obolibrary.org/obo/PO_0025407) "plant fiber cell" **(new from PO)**
    **(preferred)**
  - [`NCIT:C1502`](http://purl.obolibrary.org/obo/NCIT_C1502) "Fiber" _(was preferred before)_
- Clique with 6 identifiers — typed as `biolink:GrossAnatomicalStructure` — gains 1 new member(s)
  from PO:
  - [`UMLS:C0036563`](http://identifiers.org/umls/C0036563) **(preferred)**
  - [`MESH:D012639`](http://id.nlm.nih.gov/mesh/D012639) "Seeds"
  - [`NCIT:C73913`](http://purl.obolibrary.org/obo/NCIT_C73913) "Seed"
  - [`PO:0009010`](http://purl.obolibrary.org/obo/PO_0009010) "seed" **(new from PO)**
  - [`SNOMEDCT:1660001`](http://snomed.info/id/1660001)
  - [`SNOMEDCT:264337003`](http://snomed.info/id/264337003)
