# Source impact report: GARD

- Generated: 2026-08-17 22:21:22 UTC
- Babel commit: 4805fcf2453e0e61126087aa28eef02fdfe45bd2
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

- 14,328 new cliques composed only of GARD identifiers (a 3.25% increase over the 440,990
  pre-existing cliques)
- 1,644 existing cliques contain GARD identifiers in the after state (0.37% of the 440,990
  pre-existing cliques). Of these, 0 cliques gain at least one structurally new identifier from
  GARD, and 1,644 already contained the GARD CURIE via an xref from another source — GARD's ids file
  now also lists those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new GARD cross-references
- 0 structurally-new GARD identifiers are added to existing cliques (0 via expansion, 0 via merges).
  This is distinct from the 0 existing cliques that change, since one clique can gain several
  identifiers.
- Total cliques in this pipeline go from 440,990 to 455,318
- Full list of new cliques: [`impact-report/new-cliques.csv`](impact-report/new-cliques.csv)
- Full list of modified cliques (one row per added/preexisting GARD identifier):
  [`impact-report/modified-cliques.csv`](impact-report/modified-cliques.csv)
- Full list of new / activated cross-references:
  [`impact-report/new-xrefs.tsv`](impact-report/new-xrefs.tsv)

#### Sample pure-new cliques (up to 3)

- `GARD:10001` "Congenital secretory diarrhea, chloride type"
  **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
- `GARD:10002` "Chromosome 8Q12.1-q21.2 deletion syndrome"
  **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
- `GARD:10004` "GRN-related frontotemporal lobar degeneration with Tdp43 inclusions"
  **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**

#### Sample expanded cliques (up to 3)

Of the 1,644 cliques that contain GARD identifiers in the after state, 0 would also see their
preferred identifier change as a result of adding GARD. The sample below leads with
preferred-id-change cliques (if any), then structurally grown cliques, then cliques where GARD only
adds CURIEs that were already present via xref. Within each clique, identifiers are listed in the
same order they would appear in the compendium (biolink prefix priority, then lexicographic within
prefix).

- Clique with 281 identifiers — typed as `biolink:Disease` — GARD CURIE already present via xref:
  - [`MONDO:0000912`](http://purl.obolibrary.org/obo/MONDO_0000912) "autosomal recessive
    nonsyndromic hearing loss 5" **(preferred)**
  - [`DOID:0050564`](http://purl.obolibrary.org/obo/DOID_0050564) "autosomal dominant nonsyndromic
    deafness"
  - [`DOID:0050565`](http://purl.obolibrary.org/obo/DOID_0050565) "autosomal recessive nonsyndromic
    deafness"
  - [`DOID:0050566`](http://purl.obolibrary.org/obo/DOID_0050566) "X-linked nonsyndromic deafness"
  - [`DOID:0060690`](http://purl.obolibrary.org/obo/DOID_0060690) "autosomal dominant auditory
    neuropathy 1"
  - [`DOID:0110462`](http://purl.obolibrary.org/obo/DOID_0110462) "autosomal recessive nonsyndromic
    deafness 101"
  - [`DOID:0110463`](http://purl.obolibrary.org/obo/DOID_0110463) "autosomal recessive nonsyndromic
    deafness 102"
  - [`DOID:0110464`](http://purl.obolibrary.org/obo/DOID_0110464) "autosomal recessive nonsyndromic
    deafness 103"
  - [`DOID:0110465`](http://purl.obolibrary.org/obo/DOID_0110465) "autosomal recessive nonsyndromic
    deafness 104"
  - [`DOID:0110467`](http://purl.obolibrary.org/obo/DOID_0110467) "autosomal recessive nonsyndromic
    deafness 12"
  - [`DOID:0110468`](http://purl.obolibrary.org/obo/DOID_0110468) "autosomal recessive nonsyndromic
    deafness 13"
  - [`DOID:0110469`](http://purl.obolibrary.org/obo/DOID_0110469) "autosomal recessive nonsyndromic
    deafness 14"
  - [`DOID:0110470`](http://purl.obolibrary.org/obo/DOID_0110470) "autosomal recessive nonsyndromic
    deafness 15"
  - [`DOID:0110471`](http://purl.obolibrary.org/obo/DOID_0110471) "autosomal recessive nonsyndromic
    deafness 16"
  - [`DOID:0110472`](http://purl.obolibrary.org/obo/DOID_0110472) "autosomal recessive nonsyndromic
    deafness 17"
  - [`DOID:0110473`](http://purl.obolibrary.org/obo/DOID_0110473) "autosomal recessive nonsyndromic
    deafness 18A"
  - [`DOID:0110474`](http://purl.obolibrary.org/obo/DOID_0110474) "autosomal recessive nonsyndromic
    deafness 18B"
  - [`DOID:0110475`](http://purl.obolibrary.org/obo/DOID_0110475) "autosomal recessive nonsyndromic
    deafness 1A"
  - [`DOID:0110476`](http://purl.obolibrary.org/obo/DOID_0110476) "autosomal recessive nonsyndromic
    deafness 1B"
  - [`DOID:0110477`](http://purl.obolibrary.org/obo/DOID_0110477) "autosomal recessive nonsyndromic
    deafness 2"
  - [`DOID:0110478`](http://purl.obolibrary.org/obo/DOID_0110478) "autosomal recessive nonsyndromic
    deafness 20"
  - [`DOID:0110479`](http://purl.obolibrary.org/obo/DOID_0110479) "autosomal recessive nonsyndromic
    deafness 21"
  - [`DOID:0110480`](http://purl.obolibrary.org/obo/DOID_0110480) "autosomal recessive nonsyndromic
    deafness 22"
  - [`DOID:0110481`](http://purl.obolibrary.org/obo/DOID_0110481) "autosomal recessive nonsyndromic
    deafness 23"
  - [`DOID:0110482`](http://purl.obolibrary.org/obo/DOID_0110482) "autosomal recessive nonsyndromic
    deafness 24"
  - [`DOID:0110483`](http://purl.obolibrary.org/obo/DOID_0110483) "autosomal recessive nonsyndromic
    deafness 25"
  - [`DOID:0110484`](http://purl.obolibrary.org/obo/DOID_0110484) "autosomal recessive nonsyndromic
    deafness 26"
  - [`DOID:0110485`](http://purl.obolibrary.org/obo/DOID_0110485) "autosomal recessive nonsyndromic
    deafness 27"
  - [`DOID:0110486`](http://purl.obolibrary.org/obo/DOID_0110486) "autosomal recessive nonsyndromic
    deafness 28"
  - [`DOID:0110487`](http://purl.obolibrary.org/obo/DOID_0110487) "autosomal recessive nonsyndromic
    deafness 29"
  - [`DOID:0110488`](http://purl.obolibrary.org/obo/DOID_0110488) "autosomal recessive nonsyndromic
    deafness 3"
  - [`DOID:0110489`](http://purl.obolibrary.org/obo/DOID_0110489) "autosomal recessive nonsyndromic
    deafness 30"
  - [`DOID:0110490`](http://purl.obolibrary.org/obo/DOID_0110490) "autosomal recessive nonsyndromic
    deafness 31"
  - [`DOID:0110491`](http://purl.obolibrary.org/obo/DOID_0110491) "autosomal recessive nonsyndromic
    deafness 32"
  - [`DOID:0110492`](http://purl.obolibrary.org/obo/DOID_0110492) "autosomal recessive nonsyndromic
    deafness 33"
  - [`DOID:0110493`](http://purl.obolibrary.org/obo/DOID_0110493) "autosomal recessive nonsyndromic
    deafness 35"
  - [`DOID:0110494`](http://purl.obolibrary.org/obo/DOID_0110494) "autosomal recessive nonsyndromic
    deafness 36"
  - [`DOID:0110495`](http://purl.obolibrary.org/obo/DOID_0110495) "autosomal recessive nonsyndromic
    deafness 37"
  - [`DOID:0110496`](http://purl.obolibrary.org/obo/DOID_0110496) "autosomal recessive nonsyndromic
    deafness 38"
  - [`DOID:0110497`](http://purl.obolibrary.org/obo/DOID_0110497) "autosomal recessive nonsyndromic
    deafness 39"
  - [`DOID:0110498`](http://purl.obolibrary.org/obo/DOID_0110498) "autosomal recessive nonsyndromic
    deafness 4"
  - [`DOID:0110499`](http://purl.obolibrary.org/obo/DOID_0110499) "autosomal recessive nonsyndromic
    deafness 40"
  - [`DOID:0110500`](http://purl.obolibrary.org/obo/DOID_0110500) "autosomal recessive nonsyndromic
    deafness 42"
  - [`DOID:0110501`](http://purl.obolibrary.org/obo/DOID_0110501) "autosomal recessive nonsyndromic
    deafness 44"
  - [`DOID:0110502`](http://purl.obolibrary.org/obo/DOID_0110502) "autosomal recessive nonsyndromic
    deafness 45"
  - [`DOID:0110503`](http://purl.obolibrary.org/obo/DOID_0110503) "autosomal recessive nonsyndromic
    deafness 46"
  - [`DOID:0110504`](http://purl.obolibrary.org/obo/DOID_0110504) "autosomal recessive nonsyndromic
    deafness 47"
  - [`DOID:0110505`](http://purl.obolibrary.org/obo/DOID_0110505) "autosomal recessive nonsyndromic
    deafness 48"
  - [`DOID:0110506`](http://purl.obolibrary.org/obo/DOID_0110506) "autosomal recessive nonsyndromic
    deafness 49"
  - [`DOID:0110507`](http://purl.obolibrary.org/obo/DOID_0110507) "autosomal recessive nonsyndromic
    deafness 5"
  - [`DOID:0110508`](http://purl.obolibrary.org/obo/DOID_0110508) "autosomal recessive nonsyndromic
    deafness 51"
  - [`DOID:0110509`](http://purl.obolibrary.org/obo/DOID_0110509) "autosomal recessive nonsyndromic
    deafness 53"
  - [`DOID:0110510`](http://purl.obolibrary.org/obo/DOID_0110510) "autosomal recessive nonsyndromic
    deafness 55"
  - [`DOID:0110511`](http://purl.obolibrary.org/obo/DOID_0110511) "autosomal recessive nonsyndromic
    deafness 59"
  - [`DOID:0110512`](http://purl.obolibrary.org/obo/DOID_0110512) "autosomal recessive nonsyndromic
    deafness 6"
  - [`DOID:0110513`](http://purl.obolibrary.org/obo/DOID_0110513) "autosomal recessive nonsyndromic
    deafness 61"
  - [`DOID:0110514`](http://purl.obolibrary.org/obo/DOID_0110514) "autosomal recessive nonsyndromic
    deafness 62"
  - [`DOID:0110515`](http://purl.obolibrary.org/obo/DOID_0110515) "autosomal recessive nonsyndromic
    deafness 63"
  - [`DOID:0110516`](http://purl.obolibrary.org/obo/DOID_0110516) "autosomal recessive nonsyndromic
    deafness 65"
  - [`DOID:0110517`](http://purl.obolibrary.org/obo/DOID_0110517) "autosomal recessive nonsyndromic
    deafness 66"
  - [`DOID:0110518`](http://purl.obolibrary.org/obo/DOID_0110518) "autosomal recessive nonsyndromic
    deafness 67"
  - [`DOID:0110519`](http://purl.obolibrary.org/obo/DOID_0110519) "autosomal recessive nonsyndromic
    deafness 68"
  - [`DOID:0110520`](http://purl.obolibrary.org/obo/DOID_0110520) "autosomal recessive nonsyndromic
    deafness 7"
  - [`DOID:0110521`](http://purl.obolibrary.org/obo/DOID_0110521) "autosomal recessive nonsyndromic
    deafness 70"
  - [`DOID:0110522`](http://purl.obolibrary.org/obo/DOID_0110522) "autosomal recessive nonsyndromic
    deafness 71"
  - [`DOID:0110523`](http://purl.obolibrary.org/obo/DOID_0110523) "autosomal recessive nonsyndromic
    deafness 74"
  - [`DOID:0110524`](http://purl.obolibrary.org/obo/DOID_0110524) "autosomal recessive nonsyndromic
    deafness 76"
  - [`DOID:0110525`](http://purl.obolibrary.org/obo/DOID_0110525) "autosomal recessive nonsyndromic
    deafness 77"
  - [`DOID:0110526`](http://purl.obolibrary.org/obo/DOID_0110526) "autosomal recessive nonsyndromic
    deafness 79"
  - [`DOID:0110527`](http://purl.obolibrary.org/obo/DOID_0110527) "autosomal recessive nonsyndromic
    deafness 8"
  - [`DOID:0110528`](http://purl.obolibrary.org/obo/DOID_0110528) "autosomal recessive nonsyndromic
    deafness 83"
  - [`DOID:0110529`](http://purl.obolibrary.org/obo/DOID_0110529) "autosomal recessive nonsyndromic
    deafness 84A"
  - [`DOID:0110530`](http://purl.obolibrary.org/obo/DOID_0110530) "autosomal recessive nonsyndromic
    deafness 84B"
  - [`DOID:0110531`](http://purl.obolibrary.org/obo/DOID_0110531) "autosomal recessive nonsyndromic
    deafness 85"
  - [`DOID:0110532`](http://purl.obolibrary.org/obo/DOID_0110532) "autosomal recessive nonsyndromic
    deafness 86"
  - [`DOID:0110533`](http://purl.obolibrary.org/obo/DOID_0110533) "autosomal recessive nonsyndromic
    deafness 88"
  - [`DOID:0110534`](http://purl.obolibrary.org/obo/DOID_0110534) "autosomal recessive nonsyndromic
    deafness 89"
  - [`DOID:0110535`](http://purl.obolibrary.org/obo/DOID_0110535) "autosomal recessive nonsyndromic
    deafness 9"
  - [`DOID:0110536`](http://purl.obolibrary.org/obo/DOID_0110536) "autosomal recessive nonsyndromic
    deafness 91"
  - [`DOID:0110537`](http://purl.obolibrary.org/obo/DOID_0110537) "autosomal recessive nonsyndromic
    deafness 93"
  - [`DOID:0110538`](http://purl.obolibrary.org/obo/DOID_0110538) "autosomal recessive nonsyndromic
    deafness 96"
  - [`DOID:0110539`](http://purl.obolibrary.org/obo/DOID_0110539) "autosomal recessive nonsyndromic
    deafness 97"
  - [`DOID:0110540`](http://purl.obolibrary.org/obo/DOID_0110540) "autosomal recessive nonsyndromic
    deafness 98"
  - [`DOID:0110541`](http://purl.obolibrary.org/obo/DOID_0110541) "autosomal dominant nonsyndromic
    deafness 1"
  - [`DOID:0110542`](http://purl.obolibrary.org/obo/DOID_0110542) "autosomal dominant nonsyndromic
    deafness 10"
  - [`DOID:0110543`](http://purl.obolibrary.org/obo/DOID_0110543) "autosomal dominant nonsyndromic
    deafness 11"
  - [`DOID:0110544`](http://purl.obolibrary.org/obo/DOID_0110544) "autosomal dominant nonsyndromic
    deafness 12"
  - [`DOID:0110545`](http://purl.obolibrary.org/obo/DOID_0110545) "autosomal dominant nonsyndromic
    deafness 13"
  - [`DOID:0110546`](http://purl.obolibrary.org/obo/DOID_0110546) "autosomal dominant nonsyndromic
    deafness 15"
  - [`DOID:0110547`](http://purl.obolibrary.org/obo/DOID_0110547) "autosomal dominant nonsyndromic
    deafness 16"
  - [`DOID:0110548`](http://purl.obolibrary.org/obo/DOID_0110548) "autosomal dominant nonsyndromic
    deafness 17"
  - [`DOID:0110549`](http://purl.obolibrary.org/obo/DOID_0110549) "autosomal dominant nonsyndromic
    deafness 18"
  - [`DOID:0110550`](http://purl.obolibrary.org/obo/DOID_0110550) "autosomal dominant nonsyndromic
    deafness 20"
  - [`DOID:0110551`](http://purl.obolibrary.org/obo/DOID_0110551) "autosomal dominant nonsyndromic
    deafness 21"
  - [`DOID:0110552`](http://purl.obolibrary.org/obo/DOID_0110552) "autosomal dominant nonsyndromic
    deafness 22"
  - [`DOID:0110553`](http://purl.obolibrary.org/obo/DOID_0110553) "autosomal dominant nonsyndromic
    deafness 23"
  - [`DOID:0110554`](http://purl.obolibrary.org/obo/DOID_0110554) "autosomal dominant nonsyndromic
    deafness 24"
  - [`DOID:0110555`](http://purl.obolibrary.org/obo/DOID_0110555) "autosomal dominant nonsyndromic
    deafness 25"
  - [`DOID:0110556`](http://purl.obolibrary.org/obo/DOID_0110556) "autosomal dominant nonsyndromic
    deafness 27"
  - [`DOID:0110557`](http://purl.obolibrary.org/obo/DOID_0110557) "autosomal dominant nonsyndromic
    deafness 28"
  - [`DOID:0110558`](http://purl.obolibrary.org/obo/DOID_0110558) "autosomal dominant nonsyndromic
    deafness 2A"
  - [`DOID:0110559`](http://purl.obolibrary.org/obo/DOID_0110559) "autosomal dominant nonsyndromic
    deafness 2B"
  - [`DOID:0110560`](http://purl.obolibrary.org/obo/DOID_0110560) "autosomal dominant nonsyndromic
    deafness 30"
  - [`DOID:0110561`](http://purl.obolibrary.org/obo/DOID_0110561) "autosomal dominant nonsyndromic
    deafness 31"
  - [`DOID:0110562`](http://purl.obolibrary.org/obo/DOID_0110562) "autosomal dominant nonsyndromic
    deafness 33"
  - [`DOID:0110563`](http://purl.obolibrary.org/obo/DOID_0110563) "autosomal dominant nonsyndromic
    deafness 36"
  - [`DOID:0110564`](http://purl.obolibrary.org/obo/DOID_0110564) "autosomal dominant nonsyndromic
    deafness 3A"
  - [`DOID:0110565`](http://purl.obolibrary.org/obo/DOID_0110565) "autosomal dominant nonsyndromic
    deafness 3B"
  - [`DOID:0110566`](http://purl.obolibrary.org/obo/DOID_0110566) "autosomal dominant nonsyndromic
    deafness 40"
  - [`DOID:0110567`](http://purl.obolibrary.org/obo/DOID_0110567) "autosomal dominant nonsyndromic
    deafness 41"
  - [`DOID:0110568`](http://purl.obolibrary.org/obo/DOID_0110568) "autosomal dominant nonsyndromic
    deafness 43"
  - [`DOID:0110569`](http://purl.obolibrary.org/obo/DOID_0110569) "autosomal dominant nonsyndromic
    deafness 44"
  - [`DOID:0110570`](http://purl.obolibrary.org/obo/DOID_0110570) "autosomal dominant nonsyndromic
    deafness 47"
  - [`DOID:0110571`](http://purl.obolibrary.org/obo/DOID_0110571) "autosomal dominant nonsyndromic
    deafness 48"
  - [`DOID:0110572`](http://purl.obolibrary.org/obo/DOID_0110572) "autosomal dominant nonsyndromic
    deafness 49"
  - [`DOID:0110573`](http://purl.obolibrary.org/obo/DOID_0110573) "autosomal dominant nonsyndromic
    deafness 4A"
  - [`DOID:0110574`](http://purl.obolibrary.org/obo/DOID_0110574) "autosomal dominant nonsyndromic
    deafness 4B"
  - [`DOID:0110575`](http://purl.obolibrary.org/obo/DOID_0110575) "autosomal dominant nonsyndromic
    deafness 5"
  - [`DOID:0110576`](http://purl.obolibrary.org/obo/DOID_0110576) "autosomal dominant nonsyndromic
    deafness 50"
  - [`DOID:0110577`](http://purl.obolibrary.org/obo/DOID_0110577) "autosomal dominant nonsyndromic
    deafness 51"
  - [`DOID:0110579`](http://purl.obolibrary.org/obo/DOID_0110579) "autosomal dominant nonsyndromic
    deafness 53"
  - [`DOID:0110580`](http://purl.obolibrary.org/obo/DOID_0110580) "autosomal dominant nonsyndromic
    deafness 54"
  - [`DOID:0110581`](http://purl.obolibrary.org/obo/DOID_0110581) "autosomal dominant nonsyndromic
    deafness 56"
  - [`DOID:0110582`](http://purl.obolibrary.org/obo/DOID_0110582) "autosomal dominant nonsyndromic
    deafness 58"
  - [`DOID:0110583`](http://purl.obolibrary.org/obo/DOID_0110583) "autosomal dominant nonsyndromic
    deafness 59"
  - [`DOID:0110584`](http://purl.obolibrary.org/obo/DOID_0110584) "autosomal dominant nonsyndromic
    deafness 6"
  - [`DOID:0110585`](http://purl.obolibrary.org/obo/DOID_0110585) "autosomal dominant nonsyndromic
    deafness 64"
  - [`DOID:0110586`](http://purl.obolibrary.org/obo/DOID_0110586) "autosomal dominant nonsyndromic
    deafness 65"
  - [`DOID:0110587`](http://purl.obolibrary.org/obo/DOID_0110587) "autosomal dominant nonsyndromic
    deafness 66"
  - [`DOID:0110588`](http://purl.obolibrary.org/obo/DOID_0110588) "autosomal dominant nonsyndromic
    deafness 67"
  - [`DOID:0110589`](http://purl.obolibrary.org/obo/DOID_0110589) "autosomal dominant nonsyndromic
    deafness 68"
  - [`DOID:0110590`](http://purl.obolibrary.org/obo/DOID_0110590) "autosomal dominant nonsyndromic
    deafness 69"
  - [`DOID:0110591`](http://purl.obolibrary.org/obo/DOID_0110591) "autosomal dominant nonsyndromic
    deafness 7"
  - [`DOID:0110592`](http://purl.obolibrary.org/obo/DOID_0110592) "autosomal dominant nonsyndromic
    deafness 70"
  - [`DOID:0110593`](http://purl.obolibrary.org/obo/DOID_0110593) "autosomal dominant nonsyndromic
    deafness 9"
  - [`OMIM:600792`](http://purl.obolibrary.org/obo/OMIM_600792)
  - [`UMLS:C1833319`](http://identifiers.org/umls/C1833319) "Deafness, Autosomal Recessive 5"
  - [`MESH:C563444`](http://id.nlm.nih.gov/mesh/C563444) "Deafness, Autosomal Recessive 5"
  - `MEDGEN:331485`
  - [`ICD10:H90.3`](https://icd.codes/icd9cm/H90.3)
  - `GARD:9166` "Autosomal dominant nonsyndromic hearing loss 24"
    **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:9919` "Autosomal recessive nonsyndromic hearing loss 55"
    **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:9934` "Autosomal dominant nonsyndromic hearing loss 53"
    **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `MIM:124900`
  - `MIM:220290`
  - `MIM:600060`
  - `MIM:600101`
  - `MIM:600316`
  - `MIM:600652`
  - `MIM:600791`
  - `MIM:600792`
  - `MIM:600965`
  - `MIM:600971`
  - `MIM:600974`
  - `MIM:600994`
  - `MIM:601071`
  - `MIM:601072`
  - `MIM:601316`
  - `MIM:601317`
  - `MIM:601369`
  - `MIM:601386`
  - `MIM:601412`
  - `MIM:601543`
  - `MIM:601544`
  - `MIM:601868`
  - `MIM:601869`
  - `MIM:602092`
  - `MIM:602459`
  - `MIM:603010`
  - `MIM:603098`
  - `MIM:603622`
  - `MIM:603629`
  - `MIM:603678`
  - `MIM:603720`
  - `MIM:603964`
  - `MIM:604060`
  - `MIM:604717`
  - `MIM:605192`
  - `MIM:605428`
  - `MIM:605583`
  - `MIM:605818`
  - `MIM:606012`
  - `MIM:606282`
  - `MIM:606346`
  - `MIM:606451`
  - `MIM:606705`
  - `MIM:607017`
  - `MIM:607039`
  - `MIM:607084`
  - `MIM:607101`
  - `MIM:607197`
  - `MIM:607239`
  - `MIM:607453`
  - `MIM:607821`
  - `MIM:607841`
  - `MIM:608219`
  - `MIM:608224`
  - `MIM:608264`
  - `MIM:608265`
  - `MIM:608372`
  - `MIM:608394`
  - `MIM:608565`
  - `MIM:608641`
  - `MIM:608645`
  - `MIM:608652`
  - `MIM:608653`
  - `MIM:609006`
  - `MIM:609129`
  - `MIM:609439`
  - `MIM:609533`
  - `MIM:609646`
  - `MIM:609647`
  - `MIM:609706`
  - `MIM:609823`
  - `MIM:609941`
  - `MIM:609946`
  - `MIM:609952`
  - `MIM:609965`
  - `MIM:610143`
  - `MIM:610153`
  - `MIM:610154`
  - `MIM:610212`
  - `MIM:610220`
  - `MIM:610248`
  - `MIM:610265`
  - `MIM:610419`
  - `MIM:611022`
  - `MIM:611451`
  - `MIM:612431`
  - `MIM:612433`
  - `MIM:612642`
  - `MIM:612643`
  - `MIM:612644`
  - `MIM:612645`
  - `MIM:612789`
  - `MIM:613074`
  - `MIM:613079`
  - `MIM:613285`
  - `MIM:613307`
  - `MIM:613391`
  - `MIM:613392`
  - `MIM:613453`
  - `MIM:613558`
  - `MIM:613685`
  - `MIM:613718`
  - `MIM:613865`
  - `MIM:613916`
  - `MIM:614035`
  - `MIM:614152`
  - `MIM:614211`
  - `MIM:614414`
  - `MIM:614614`
  - `MIM:614617`
  - `MIM:614861`
  - `MIM:614899`
  - `MIM:614934`
  - `MIM:614944`
  - `MIM:614945`
  - `MIM:615429`
  - `MIM:615540`
  - `MIM:615629`
  - `MIM:615649`
  - `MIM:615654`
  - `MIM:615837`
  - `MIM:615974`
  - `MIM:616042`
  - `MIM:616044`
  - `MIM:616340`
  - `MIM:616357`
  - `MIM:616515`
  - `MIM:616697`
  - `MIM:616705`
  - `MIM:616707`
  - `MIM:616968`
  - `MIM:616969`
  - `MIM:PS124900`
  - `MIM:PS220290`
  - `MIM:PS304500`
  - `ORDO:90625`
  - `ORDO:90635`
  - `ORDO:90636`
- Clique with 294 identifiers — typed as `biolink:Disease` — GARD CURIE already present via xref:
  - [`MONDO:0000910`](http://purl.obolibrary.org/obo/MONDO_0000910) "retinitis pigmentosa 6"
    **(preferred)**
  - [`DOID:0050572`](http://purl.obolibrary.org/obo/DOID_0050572) "cone-rod dystrophy"
  - [`DOID:0050661`](http://purl.obolibrary.org/obo/DOID_0050661) "vitelliform macular dystrophy"
  - [`DOID:0060745`](http://purl.obolibrary.org/obo/DOID_0060745) "Doyne honeycomb retinal
    dystrophy"
  - [`DOID:0060746`](http://purl.obolibrary.org/obo/DOID_0060746) "basal laminar drusen"
  - [`DOID:0060863`](http://purl.obolibrary.org/obo/DOID_0060863) "patterned macular dystrophy"
  - [`DOID:0080350`](http://purl.obolibrary.org/obo/DOID_0080350) "retinitis pigmentosa 77"
  - [`DOID:0110005`](http://purl.obolibrary.org/obo/DOID_0110005) "Leber congenital amaurosis 9"
  - [`DOID:0110016`](http://purl.obolibrary.org/obo/DOID_0110016) "Leber congenital amaurosis 2"
  - [`DOID:0110078`](http://purl.obolibrary.org/obo/DOID_0110078) "Leber congenital amaurosis 1"
  - [`DOID:0110079`](http://purl.obolibrary.org/obo/DOID_0110079) "Leber congenital amaurosis 8"
  - [`DOID:0110080`](http://purl.obolibrary.org/obo/DOID_0110080) "Leber congenital amaurosis 12"
  - [`DOID:0110118`](http://purl.obolibrary.org/obo/DOID_0110118) "Leber congenital amaurosis 16"
  - [`DOID:0110188`](http://purl.obolibrary.org/obo/DOID_0110188) "Leber congenital amaurosis 14"
  - [`DOID:0110189`](http://purl.obolibrary.org/obo/DOID_0110189) "Leber congenital amaurosis 15"
  - [`DOID:0110215`](http://purl.obolibrary.org/obo/DOID_0110215) "Leber congenital amaurosis 5"
  - [`DOID:0110216`](http://purl.obolibrary.org/obo/DOID_0110216) "Leber congenital amaurosis 11"
  - [`DOID:0110217`](http://purl.obolibrary.org/obo/DOID_0110217) "Leber congenital amaurosis 17"
  - [`DOID:0110291`](http://purl.obolibrary.org/obo/DOID_0110291) "Leber congenital amaurosis 10"
  - [`DOID:0110329`](http://purl.obolibrary.org/obo/DOID_0110329) "Leber congenital amaurosis 6"
  - [`DOID:0110330`](http://purl.obolibrary.org/obo/DOID_0110330) "Leber congenital amaurosis 13"
  - [`DOID:0110331`](http://purl.obolibrary.org/obo/DOID_0110331) "Leber congenital amaurosis 3"
  - [`DOID:0110332`](http://purl.obolibrary.org/obo/DOID_0110332) "Leber congenital amaurosis 4"
  - [`DOID:0110333`](http://purl.obolibrary.org/obo/DOID_0110333) "Leber congenital amaurosis 7"
  - [`DOID:0110352`](http://purl.obolibrary.org/obo/DOID_0110352) "retinitis pigmentosa 59"
  - [`DOID:0110353`](http://purl.obolibrary.org/obo/DOID_0110353) "retinitis pigmentosa 20"
  - [`DOID:0110354`](http://purl.obolibrary.org/obo/DOID_0110354) "retinitis pigmentosa 19"
  - [`DOID:0110355`](http://purl.obolibrary.org/obo/DOID_0110355) "retinitis pigmentosa 32"
  - [`DOID:0110356`](http://purl.obolibrary.org/obo/DOID_0110356) "retinitis pigmentosa 18"
  - [`DOID:0110357`](http://purl.obolibrary.org/obo/DOID_0110357) "retinitis pigmentosa 35"
  - [`DOID:0110358`](http://purl.obolibrary.org/obo/DOID_0110358) "retinitis pigmentosa 12"
  - [`DOID:0110359`](http://purl.obolibrary.org/obo/DOID_0110359) "retinitis pigmentosa 67"
  - [`DOID:0110360`](http://purl.obolibrary.org/obo/DOID_0110360) "retinitis pigmentosa 39"
  - [`DOID:0110361`](http://purl.obolibrary.org/obo/DOID_0110361) "retinitis pigmentosa 75"
  - [`DOID:0110362`](http://purl.obolibrary.org/obo/DOID_0110362) "retinitis pigmentosa 58"
  - [`DOID:0110363`](http://purl.obolibrary.org/obo/DOID_0110363) "retinitis pigmentosa 71"
  - [`DOID:0110364`](http://purl.obolibrary.org/obo/DOID_0110364) "retinitis pigmentosa 54"
  - [`DOID:0110365`](http://purl.obolibrary.org/obo/DOID_0110365) "retinitis pigmentosa 28"
  - [`DOID:0110366`](http://purl.obolibrary.org/obo/DOID_0110366) "retinitis pigmentosa 33"
  - [`DOID:0110367`](http://purl.obolibrary.org/obo/DOID_0110367) "retinitis pigmentosa 38"
  - [`DOID:0110368`](http://purl.obolibrary.org/obo/DOID_0110368) "retinitis pigmentosa 26"
  - [`DOID:0110369`](http://purl.obolibrary.org/obo/DOID_0110369) "retinitis pigmentosa 47"
  - [`DOID:0110370`](http://purl.obolibrary.org/obo/DOID_0110370) "retinitis pigmentosa 55"
  - [`DOID:0110371`](http://purl.obolibrary.org/obo/DOID_0110371) "retinitis pigmentosa 56"
  - [`DOID:0110372`](http://purl.obolibrary.org/obo/DOID_0110372) "retinitis pigmentosa 4"
  - [`DOID:0110373`](http://purl.obolibrary.org/obo/DOID_0110373) "retinitis pigmentosa 61"
  - [`DOID:0110374`](http://purl.obolibrary.org/obo/DOID_0110374) "retinitis pigmentosa 68"
  - [`DOID:0110375`](http://purl.obolibrary.org/obo/DOID_0110375) "retinitis pigmentosa 40"
  - [`DOID:0110376`](http://purl.obolibrary.org/obo/DOID_0110376) "retinitis pigmentosa 41"
  - [`DOID:0110377`](http://purl.obolibrary.org/obo/DOID_0110377) "retinitis pigmentosa 49"
  - [`DOID:0110378`](http://purl.obolibrary.org/obo/DOID_0110378) "retinitis pigmentosa 29"
  - [`DOID:0110379`](http://purl.obolibrary.org/obo/DOID_0110379) "retinitis pigmentosa 43"
  - [`DOID:0110380`](http://purl.obolibrary.org/obo/DOID_0110380) "retinitis pigmentosa 62"
  - [`DOID:0110381`](http://purl.obolibrary.org/obo/DOID_0110381) "retinitis pigmentosa 14"
  - [`DOID:0110382`](http://purl.obolibrary.org/obo/DOID_0110382) "retinitis pigmentosa 48"
  - [`DOID:0110383`](http://purl.obolibrary.org/obo/DOID_0110383) "retinitis pigmentosa 7"
  - [`DOID:0110384`](http://purl.obolibrary.org/obo/DOID_0110384) "retinitis pigmentosa 25"
  - [`DOID:0110385`](http://purl.obolibrary.org/obo/DOID_0110385) "retinitis pigmentosa 63"
  - [`DOID:0110386`](http://purl.obolibrary.org/obo/DOID_0110386) "retinitis pigmentosa 42"
  - [`DOID:0110387`](http://purl.obolibrary.org/obo/DOID_0110387) "retinitis pigmentosa 9"
  - [`DOID:0110388`](http://purl.obolibrary.org/obo/DOID_0110388) "retinitis pigmentosa 10"
  - [`DOID:0110389`](http://purl.obolibrary.org/obo/DOID_0110389) "retinitis pigmentosa 73"
  - [`DOID:0110390`](http://purl.obolibrary.org/obo/DOID_0110390) "retinitis pigmentosa 1"
  - [`DOID:0110391`](http://purl.obolibrary.org/obo/DOID_0110391) "retinitis pigmentosa 31"
  - [`DOID:0110392`](http://purl.obolibrary.org/obo/DOID_0110392) "retinitis pigmentosa 70"
  - [`DOID:0110393`](http://purl.obolibrary.org/obo/DOID_0110393) "retinitis pigmentosa 66"
  - [`DOID:0110394`](http://purl.obolibrary.org/obo/DOID_0110394) "retinitis pigmentosa 44"
  - [`DOID:0110395`](http://purl.obolibrary.org/obo/DOID_0110395) "retinitis pigmentosa 72"
  - [`DOID:0110396`](http://purl.obolibrary.org/obo/DOID_0110396) "retinitis pigmentosa 50"
  - [`DOID:0110397`](http://purl.obolibrary.org/obo/DOID_0110397) "retinitis pigmentosa 27"
  - [`DOID:0110398`](http://purl.obolibrary.org/obo/DOID_0110398) "retinitis pigmentosa 51"
  - [`DOID:0110399`](http://purl.obolibrary.org/obo/DOID_0110399) "retinitis pigmentosa 37"
  - [`DOID:0110400`](http://purl.obolibrary.org/obo/DOID_0110400) "retinitis pigmentosa 22"
  - [`DOID:0110401`](http://purl.obolibrary.org/obo/DOID_0110401) "retinitis pigmentosa 74"
  - [`DOID:0110402`](http://purl.obolibrary.org/obo/DOID_0110402) "retinitis pigmentosa 45"
  - [`DOID:0110403`](http://purl.obolibrary.org/obo/DOID_0110403) "retinitis pigmentosa 13"
  - [`DOID:0110404`](http://purl.obolibrary.org/obo/DOID_0110404) "retinitis pigmentosa 17"
  - [`DOID:0110405`](http://purl.obolibrary.org/obo/DOID_0110405) "retinitis pigmentosa 36"
  - [`DOID:0110406`](http://purl.obolibrary.org/obo/DOID_0110406) "retinitis pigmentosa 30"
  - [`DOID:0110407`](http://purl.obolibrary.org/obo/DOID_0110407) "retinitis pigmentosa 57"
  - [`DOID:0110408`](http://purl.obolibrary.org/obo/DOID_0110408) "retinitis pigmentosa 11"
  - [`DOID:0110409`](http://purl.obolibrary.org/obo/DOID_0110409) "retinitis pigmentosa 46"
  - [`DOID:0110410`](http://purl.obolibrary.org/obo/DOID_0110410) "retinitis pigmentosa 69"
  - [`DOID:0110411`](http://purl.obolibrary.org/obo/DOID_0110411) "retinitis pigmentosa 60"
  - [`DOID:0110412`](http://purl.obolibrary.org/obo/DOID_0110412) "retinitis pigmentosa 23"
  - [`DOID:0110413`](http://purl.obolibrary.org/obo/DOID_0110413) "retinitis pigmentosa 6"
  - [`DOID:0110414`](http://purl.obolibrary.org/obo/DOID_0110414) "retinitis pigmentosa 3"
  - [`DOID:0110415`](http://purl.obolibrary.org/obo/DOID_0110415) "retinitis pigmentosa 2"
  - [`DOID:0110416`](http://purl.obolibrary.org/obo/DOID_0110416) "retinitis pigmentosa 24"
  - [`DOID:0110417`](http://purl.obolibrary.org/obo/DOID_0110417) "retinitis pigmentosa 34"
  - [`DOID:0110418`](http://purl.obolibrary.org/obo/DOID_0110418) "retinitis pigmentosa Y-linked"
  - [`DOID:0110419`](http://purl.obolibrary.org/obo/DOID_0110419) "retinitis pigmentosa with or
    without situs inversus"
  - [`DOID:0110420`](http://purl.obolibrary.org/obo/DOID_0110420) "dominant pericentral pigmentary
    retinopathy"
  - [`DOID:0110421`](http://purl.obolibrary.org/obo/DOID_0110421) "late-adult onset retinitis
    pigmentosa"
  - [`DOID:0110422`](http://purl.obolibrary.org/obo/DOID_0110422) "autosomal recessive pericentral
    pigmentary retinopathy"
  - [`DOID:0110830`](http://purl.obolibrary.org/obo/DOID_0110830) "Usher syndrome type 1C"
  - [`DOID:0110831`](http://purl.obolibrary.org/obo/DOID_0110831) "Usher syndrome type 1D"
  - [`DOID:0110832`](http://purl.obolibrary.org/obo/DOID_0110832) "Usher syndrome type 1F"
  - [`DOID:0110833`](http://purl.obolibrary.org/obo/DOID_0110833) "Usher syndrome type 1E"
  - [`DOID:0110834`](http://purl.obolibrary.org/obo/DOID_0110834) "Usher syndrome type 1G"
  - [`DOID:0110835`](http://purl.obolibrary.org/obo/DOID_0110835) "Usher syndrome type 1H"
  - [`DOID:0110837`](http://purl.obolibrary.org/obo/DOID_0110837) "Usher syndrome type 1K"
  - [`DOID:0110838`](http://purl.obolibrary.org/obo/DOID_0110838) "Usher syndrome type 2A"
  - [`DOID:0110839`](http://purl.obolibrary.org/obo/DOID_0110839) "Usher syndrome type 2C"
  - [`DOID:0110840`](http://purl.obolibrary.org/obo/DOID_0110840) "Usher syndrome type 2D"
  - [`DOID:0110841`](http://purl.obolibrary.org/obo/DOID_0110841) "Usher syndrome type 3A"
  - [`DOID:0110842`](http://purl.obolibrary.org/obo/DOID_0110842) "Usher syndrome type 3B"
  - [`DOID:10584`](http://purl.obolibrary.org/obo/DOID_10584) "retinitis pigmentosa"
  - [`DOID:8500`](http://purl.obolibrary.org/obo/DOID_8500) "hereditary retinal dystrophy"
  - [`OMIM:312612`](http://purl.obolibrary.org/obo/OMIM_312612)
  - [`UMLS:C0035334`](http://identifiers.org/umls/C0035334) "Retinitis Pigmentosa"
  - [`UMLS:C0154860`](http://identifiers.org/umls/C0154860) "Hereditary retinal dystrophy"
  - [`UMLS:C0220701`](http://identifiers.org/umls/C0220701) "RETINITIS PIGMENTOSA 1"
  - [`UMLS:C1839368`](http://identifiers.org/umls/C1839368) "Retinitis Pigmentosa 6"
  - [`UMLS:C4551714`](http://identifiers.org/umls/C4551714) "Rod-Cone Dystrophy"
  - [`MESH:C535602`](http://id.nlm.nih.gov/mesh/C535602) "Doyne honeycomb retinal dystrophy"
  - [`MESH:C538365`](http://id.nlm.nih.gov/mesh/C538365) "Retinitis pigmentosa 1"
  - [`MESH:C563034`](http://id.nlm.nih.gov/mesh/C563034) "Basal Laminar Drusen"
  - [`MESH:C563320`](http://id.nlm.nih.gov/mesh/C563320) "Retinitis Pigmentosa 18"
  - [`MESH:C563437`](http://id.nlm.nih.gov/mesh/C563437) "Retinitis Pigmentosa 17"
  - [`MESH:C563526`](http://id.nlm.nih.gov/mesh/C563526) "Retinitis Pigmentosa 27"
  - [`MESH:C563676`](http://id.nlm.nih.gov/mesh/C563676) "Retinitis Pigmentosa 33"
  - [`MESH:C563685`](http://id.nlm.nih.gov/mesh/C563685) "Retinitis Pigmentosa 31"
  - [`MESH:C563689`](http://id.nlm.nih.gov/mesh/C563689) "Retinitis Pigmentosa 32"
  - [`MESH:C563991`](http://id.nlm.nih.gov/mesh/C563991) "Retinitis Pigmentosa 11"
  - [`MESH:C563992`](http://id.nlm.nih.gov/mesh/C563992) "Retinitis Pigmentosa 14"
  - [`MESH:C563999`](http://id.nlm.nih.gov/mesh/C563999) "Retinitis Pigmentosa 12"
  - [`MESH:C564008`](http://id.nlm.nih.gov/mesh/C564008) "Retinitis Pigmentosa 13"
  - [`MESH:C564065`](http://id.nlm.nih.gov/mesh/C564065) "Retinitis Pigmentosa 6"
  - [`MESH:C564140`](http://id.nlm.nih.gov/mesh/C564140) "Leber Congenital Amaurosis 11"
  - [`MESH:C564249`](http://id.nlm.nih.gov/mesh/C564249) "Retinitis Pigmentosa 26"
  - [`MESH:C564284`](http://id.nlm.nih.gov/mesh/C564284) "Retinitis Pigmentosa 7"
  - [`MESH:C564310`](http://id.nlm.nih.gov/mesh/C564310) "Retinitis Pigmentosa 30"
  - [`MESH:C564475`](http://id.nlm.nih.gov/mesh/C564475) "Retinitis Pigmentosa 34"
  - [`MESH:C564520`](http://id.nlm.nih.gov/mesh/C564520) "Retinitis Pigmentosa 3"
  - [`MESH:C565206`](http://id.nlm.nih.gov/mesh/C565206) "Retinitis Pigmentosa 35"
  - [`MESH:C565327`](http://id.nlm.nih.gov/mesh/C565327) "Leber Congenital Amaurosis 6"
  - [`MESH:C565697`](http://id.nlm.nih.gov/mesh/C565697) "Leber Congenital Amaurosis 12"
  - [`MESH:C565720`](http://id.nlm.nih.gov/mesh/C565720) "Leber Congenital Amaurosis 10"
  - [`MESH:C565778`](http://id.nlm.nih.gov/mesh/C565778) "Leber Congenital Amaurosis 4"
  - [`MESH:C565814`](http://id.nlm.nih.gov/mesh/C565814) "Leber Congenital Amaurosis 3"
  - [`MESH:C566425`](http://id.nlm.nih.gov/mesh/C566425) "Retinitis Pigmentosa 25"
  - [`MESH:C566431`](http://id.nlm.nih.gov/mesh/C566431) "Retinitis Pigmentosa 36"
  - [`MESH:C566637`](http://id.nlm.nih.gov/mesh/C566637) "Retinitis Pigmentosa 19"
  - [`MESH:C566706`](http://id.nlm.nih.gov/mesh/C566706) "Retinitis Pigmentosa 4"
  - [`MESH:C566715`](http://id.nlm.nih.gov/mesh/C566715) "Retinitis Pigmentosa 10"
  - [`MESH:C566716`](http://id.nlm.nih.gov/mesh/C566716) "Retinitis Pigmentosa 9"
  - [`MESH:C566718`](http://id.nlm.nih.gov/mesh/C566718) "Retinitis Pigmentosa 20"
  - [`MESH:C567005`](http://id.nlm.nih.gov/mesh/C567005) "Retinitis Pigmentosa 37"
  - [`MESH:C567197`](http://id.nlm.nih.gov/mesh/C567197) "Leber Congenital Amaurosis 13"
  - [`MESH:C567249`](http://id.nlm.nih.gov/mesh/C567249) "Retinitis Pigmentosa 46"
  - [`MESH:C567403`](http://id.nlm.nih.gov/mesh/C567403) "Retinitis Pigmentosa 29"
  - [`MESH:C567422`](http://id.nlm.nih.gov/mesh/C567422) "Retinitis Pigmentosa 41"
  - [`MESH:C567523`](http://id.nlm.nih.gov/mesh/C567523) "Retinitis Pigmentosa 2"
  - [`MESH:C567636`](http://id.nlm.nih.gov/mesh/C567636) "Leber Congenital Amaurosis 14"
  - [`MESH:C567854`](http://id.nlm.nih.gov/mesh/C567854) "Retinitis Pigmentosa 42"
  - [`MESH:D012174`](http://id.nlm.nih.gov/mesh/D012174) "Retinitis Pigmentosa"
  - [`MESH:D057826`](http://id.nlm.nih.gov/mesh/D057826) "Vitelliform Macular Dystrophy"
  - [`MEDDRA:10019898`](http://identifiers.org/meddra/10019898)
  - [`MEDDRA:10019899`](http://identifiers.org/meddra/10019899)
  - [`MEDDRA:10019900`](http://identifiers.org/meddra/10019900)
  - [`MEDDRA:10038914`](http://identifiers.org/meddra/10038914)
  - [`NCIT:C35194`](http://purl.obolibrary.org/obo/NCIT_C35194) "Hereditary Retinal Dystrophy"
  - [`NCIT:C85045`](http://purl.obolibrary.org/obo/NCIT_C85045) "Retinitis Pigmentosa"
  - `MEDGEN:333305`
  - [`ICD10:H35.5`](https://icd.codes/icd9cm/H35.5)
  - [`ICD10:H35.52`](https://icd.codes/icd9cm/H35.52)
  - [`ICD9:362.7`](http://translator.ncats.nih.gov/ICD9_362.7)
  - [`HP:0000510`](http://purl.obolibrary.org/obo/HP_0000510) "Rod-cone dystrophy"
  - `GARD:10120` "Vitelliform macular dystrophy 1" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:10790` "Cone-rod dystrophy" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:182` "Vitelliform macular dystrophy 2" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:1912` "Doyne honeycomb retinal dystrophy" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:5440` "Usher syndrome type 2" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:5694` "Retinitis pigmentosa" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `MIM:126600`
  - `MIM:126700`
  - `MIM:153700`
  - `MIM:153840`
  - `MIM:180100`
  - `MIM:180104`
  - `MIM:180105`
  - `MIM:180210`
  - `MIM:204000`
  - `MIM:204100`
  - `MIM:268000`
  - `MIM:268025`
  - `MIM:268060`
  - `MIM:276901`
  - `MIM:276902`
  - `MIM:276904`
  - `MIM:300029`
  - `MIM:300155`
  - `MIM:300424`
  - `MIM:300605`
  - `MIM:312600`
  - `MIM:312612`
  - `MIM:400004`
  - `MIM:600059`
  - `MIM:600105`
  - `MIM:600132`
  - `MIM:600138`
  - `MIM:600852`
  - `MIM:601067`
  - `MIM:601414`
  - `MIM:601718`
  - `MIM:602083`
  - `MIM:602097`
  - `MIM:602594`
  - `MIM:602772`
  - `MIM:604232`
  - `MIM:604393`
  - `MIM:604537`
  - `MIM:605472`
  - `MIM:606068`
  - `MIM:606943`
  - `MIM:607921`
  - `MIM:608133`
  - `MIM:608161`
  - `MIM:608380`
  - `MIM:608553`
  - `MIM:609913`
  - `MIM:609923`
  - `MIM:610282`
  - `MIM:610359`
  - `MIM:610599`
  - `MIM:610612`
  - `MIM:611131`
  - `MIM:611383`
  - `MIM:611755`
  - `MIM:612095`
  - `MIM:612165`
  - `MIM:612572`
  - `MIM:612632`
  - `MIM:612712`
  - `MIM:612943`
  - `MIM:613194`
  - `MIM:613341`
  - `MIM:613428`
  - `MIM:613464`
  - `MIM:613575`
  - `MIM:613581`
  - `MIM:613582`
  - `MIM:613617`
  - `MIM:613731`
  - `MIM:613750`
  - `MIM:613756`
  - `MIM:613758`
  - `MIM:613767`
  - `MIM:613769`
  - `MIM:613794`
  - `MIM:613801`
  - `MIM:613809`
  - `MIM:613810`
  - `MIM:613826`
  - `MIM:613827`
  - `MIM:613829`
  - `MIM:613835`
  - `MIM:613837`
  - `MIM:613843`
  - `MIM:613861`
  - `MIM:613862`
  - `MIM:613983`
  - `MIM:614180`
  - `MIM:614181`
  - `MIM:614186`
  - `MIM:614494`
  - `MIM:614504`
  - `MIM:614990`
  - `MIM:615233`
  - `MIM:615360`
  - `MIM:615434`
  - `MIM:615565`
  - `MIM:615725`
  - `MIM:615780`
  - `MIM:615922`
  - `MIM:616151`
  - `MIM:616152`
  - `MIM:616394`
  - `MIM:616469`
  - `MIM:616544`
  - `MIM:616562`
  - `MIM:617023`
  - `MIM:617304`
  - `MIM:PS169150`
  - `MIM:PS268000`
  - `ORDO:1243`
  - `ORDO:1872`
  - `ORDO:75376`
  - `ORDO:791`
  - `ORDO:99000`
  - `ORDO:99001`
  - `SNOMEDCT_US_2025_09_01:155113002`
  - `SNOMEDCT_US_2025_09_01:41799005`
- Clique with 229 identifiers — typed as `biolink:Disease` — GARD CURIE already present via xref:
  - [`MONDO:0000902`](http://purl.obolibrary.org/obo/MONDO_0000902) "agenesis of the corpus callosum
    with peripheral neuropathy" **(preferred)**
  - [`DOID:0050539`](http://purl.obolibrary.org/obo/DOID_0050539) "Charcot-Marie-Tooth disease type
    2"
  - [`DOID:0090003`](http://purl.obolibrary.org/obo/DOID_0090003) "agenesis of the corpus callosum
    with peripheral neuropathy"
  - [`DOID:0110148`](http://purl.obolibrary.org/obo/DOID_0110148) "Charcot-Marie-Tooth disease type
    1A"
  - [`DOID:0110149`](http://purl.obolibrary.org/obo/DOID_0110149) "Charcot-Marie-Tooth disease type
    1F"
  - [`DOID:0110150`](http://purl.obolibrary.org/obo/DOID_0110150) "Charcot-Marie-Tooth disease type
    1D"
  - [`DOID:0110151`](http://purl.obolibrary.org/obo/DOID_0110151) "Charcot-Marie-Tooth disease type
    1C"
  - [`DOID:0110152`](http://purl.obolibrary.org/obo/DOID_0110152) "Charcot-Marie-Tooth disease type
    1B"
  - [`DOID:0110153`](http://purl.obolibrary.org/obo/DOID_0110153) "Charcot-Marie-Tooth disease type
    1E"
  - [`DOID:0110154`](http://purl.obolibrary.org/obo/DOID_0110154) "Charcot-Marie-Tooth disease type
    2A1"
  - [`DOID:0110155`](http://purl.obolibrary.org/obo/DOID_0110155) "Charcot-Marie-Tooth disease type
    2A2A"
  - [`DOID:0110156`](http://purl.obolibrary.org/obo/DOID_0110156) "Charcot-Marie-Tooth disease type
    2B1"
  - [`DOID:0110157`](http://purl.obolibrary.org/obo/DOID_0110157) "Charcot-Marie-Tooth disease type
    2J"
  - [`DOID:0110158`](http://purl.obolibrary.org/obo/DOID_0110158) "Charcot-Marie-Tooth disease type
    2I"
  - [`DOID:0110159`](http://purl.obolibrary.org/obo/DOID_0110159) "Charcot-Marie-Tooth disease type
    2B"
  - [`DOID:0110160`](http://purl.obolibrary.org/obo/DOID_0110160) "Charcot-Marie-Tooth disease
    axonal type 2T"
  - [`DOID:0110161`](http://purl.obolibrary.org/obo/DOID_0110161) "Charcot-Marie-Tooth disease type
    2R"
  - [`DOID:0110163`](http://purl.obolibrary.org/obo/DOID_0110163) "Charcot-Marie-Tooth disease
    axonal type 2F"
  - [`DOID:0110164`](http://purl.obolibrary.org/obo/DOID_0110164) "Charcot-Marie-Tooth disease type
    2D"
  - [`DOID:0110165`](http://purl.obolibrary.org/obo/DOID_0110165) "Charcot-Marie-Tooth disease type
    2E"
  - [`DOID:0110166`](http://purl.obolibrary.org/obo/DOID_0110166) "Charcot-Marie-Tooth disease
    axonal type 2H"
  - [`DOID:0110167`](http://purl.obolibrary.org/obo/DOID_0110167) "Charcot-Marie-Tooth disease
    axonal type 2K"
  - [`DOID:0110168`](http://purl.obolibrary.org/obo/DOID_0110168) "Charcot-Marie-Tooth disease type
    2Y"
  - [`DOID:0110169`](http://purl.obolibrary.org/obo/DOID_0110169) "Charcot-Marie-Tooth disease
    axonal type 2P"
  - [`DOID:0110170`](http://purl.obolibrary.org/obo/DOID_0110170) "Charcot-Marie-Tooth disease
    axonal type 2Q"
  - [`DOID:0110173`](http://purl.obolibrary.org/obo/DOID_0110173) "Charcot-Marie-Tooth disease
    axonal type 2U"
  - [`DOID:0110174`](http://purl.obolibrary.org/obo/DOID_0110174) "Charcot-Marie-Tooth disease
    axonal type 2L"
  - [`DOID:0110175`](http://purl.obolibrary.org/obo/DOID_0110175) "Charcot-Marie-Tooth disease
    axonal type 2O"
  - [`DOID:0110177`](http://purl.obolibrary.org/obo/DOID_0110177) "Charcot-Marie-Tooth disease
    axonal type 2N"
  - [`DOID:0110179`](http://purl.obolibrary.org/obo/DOID_0110179) "Charcot-Marie-Tooth disease type
    2B2"
  - [`DOID:0110182`](http://purl.obolibrary.org/obo/DOID_0110182) "Charcot-Marie-Tooth disease
    axonal type 2C"
  - [`DOID:0110183`](http://purl.obolibrary.org/obo/DOID_0110183) "Charcot-Marie-Tooth disease type
    4C"
  - [`DOID:0110184`](http://purl.obolibrary.org/obo/DOID_0110184) "Charcot-Marie-Tooth disease type
    4J"
  - [`DOID:0110185`](http://purl.obolibrary.org/obo/DOID_0110185) "Charcot-Marie-Tooth disease type
    4A"
  - [`DOID:0110186`](http://purl.obolibrary.org/obo/DOID_0110186) "Charcot-Marie-Tooth disease type
    4D"
  - [`DOID:0110187`](http://purl.obolibrary.org/obo/DOID_0110187) "Charcot-Marie-Tooth disease type
    4K"
  - [`DOID:0110190`](http://purl.obolibrary.org/obo/DOID_0110190) "Charcot-Marie-Tooth disease type
    4B2"
  - [`DOID:0110191`](http://purl.obolibrary.org/obo/DOID_0110191) "Charcot-Marie-Tooth disease type
    4B1"
  - [`DOID:0110192`](http://purl.obolibrary.org/obo/DOID_0110192) "Charcot-Marie-Tooth disease type
    4H"
  - [`DOID:0110193`](http://purl.obolibrary.org/obo/DOID_0110193) "Charcot-Marie-Tooth disease type
    4F"
  - [`DOID:0110194`](http://purl.obolibrary.org/obo/DOID_0110194) "Charcot-Marie-Tooth disease type
    4B3"
  - [`DOID:0110195`](http://purl.obolibrary.org/obo/DOID_0110195) "congenital hypomyelinating
    neuropathy 1"
  - [`DOID:0110196`](http://purl.obolibrary.org/obo/DOID_0110196) "Charcot-Marie-Tooth disease type
    4G"
  - [`DOID:0110197`](http://purl.obolibrary.org/obo/DOID_0110197) "Charcot-Marie-Tooth disease
    dominant intermediate B"
  - [`DOID:0110198`](http://purl.obolibrary.org/obo/DOID_0110198) "Charcot-Marie-Tooth disease
    recessive intermediate C"
  - [`DOID:0110199`](http://purl.obolibrary.org/obo/DOID_0110199) "Charcot-Marie-Tooth disease
    dominant intermediate C"
  - [`DOID:0110200`](http://purl.obolibrary.org/obo/DOID_0110200) "Charcot-Marie-Tooth disease
    dominant intermediate D"
  - [`DOID:0110202`](http://purl.obolibrary.org/obo/DOID_0110202) "Charcot-Marie-Tooth disease
    dominant intermediate A"
  - [`DOID:0110203`](http://purl.obolibrary.org/obo/DOID_0110203) "Charcot-Marie-Tooth disease
    recessive intermediate D"
  - [`DOID:0110204`](http://purl.obolibrary.org/obo/DOID_0110204) "Charcot-Marie-Tooth disease
    recessive intermediate B"
  - [`DOID:0110205`](http://purl.obolibrary.org/obo/DOID_0110205) "Charcot-Marie-Tooth disease
    dominant intermediate E"
  - [`DOID:0110206`](http://purl.obolibrary.org/obo/DOID_0110206) "Charcot-Marie-Tooth disease
    dominant intermediate F"
  - [`DOID:0110207`](http://purl.obolibrary.org/obo/DOID_0110207) "Charcot-Marie-Tooth disease
    X-linked dominant 6"
  - [`DOID:0110208`](http://purl.obolibrary.org/obo/DOID_0110208) "Charcot-Marie-Tooth disease
    X-linked recessive 2"
  - [`DOID:0110209`](http://purl.obolibrary.org/obo/DOID_0110209) "Charcot-Marie-Tooth disease
    X-linked dominant 1"
  - [`DOID:0110210`](http://purl.obolibrary.org/obo/DOID_0110210) "Charcot-Marie-Tooth disease
    X-linked recessive 5"
  - [`DOID:0110211`](http://purl.obolibrary.org/obo/DOID_0110211) "Charcot-Marie-Tooth disease
    X-linked recessive 3"
  - [`DOID:0110212`](http://purl.obolibrary.org/obo/DOID_0110212) "Charcot-Marie-Tooth disease
    X-linked recessive 4"
  - [`DOID:10595`](http://purl.obolibrary.org/obo/DOID_10595) "Charcot-Marie-Tooth disease"
  - [`DOID:13137`](http://purl.obolibrary.org/obo/DOID_13137) "Werdnig-Hoffmann disease"
  - [`DOID:2477`](http://purl.obolibrary.org/obo/DOID_2477) "motor peripheral neuropathy"
  - [`OMIM:218000`](http://purl.obolibrary.org/obo/OMIM_218000)
  - [`orphanet:1496`](http://www.orpha.net/ORDO/Orphanet_1496)
  - [`UMLS:C0007959`](http://identifiers.org/umls/C0007959) "Charcot-Marie-Tooth Disease"
  - [`UMLS:C0027888`](http://identifiers.org/umls/C0027888) "Hereditary Motor and Sensory
    Neuropathies"
  - [`UMLS:C0043116`](http://identifiers.org/umls/C0043116) "HMN (Hereditary Motor Neuropathy)
    Proximal Type I"
  - [`UMLS:C0392553`](http://identifiers.org/umls/C0392553) "Hereditary peripheral neuropathy"
  - [`UMLS:C0795950`](http://identifiers.org/umls/C0795950) "Corpus callosum agenesis neuronopathy"
  - [`UMLS:C4721437`](http://identifiers.org/umls/C4721437) "Charcot-Marie-Tooth disease, Type 4E"
  - [`MESH:C535302`](http://id.nlm.nih.gov/mesh/C535302) "Charcot-Marie-Tooth disease, X-linked
    recessive, 2"
  - [`MESH:C535303`](http://id.nlm.nih.gov/mesh/C535303) "Charcot-Marie-Tooth disease, X-linked
    recessive, 3"
  - [`MESH:C535416`](http://id.nlm.nih.gov/mesh/C535416) "Charcot-Marie-Tooth disease, Type 2I"
  - [`MESH:C535419`](http://id.nlm.nih.gov/mesh/C535419) "Charcot-Marie-Tooth disease, Type 4A"
  - [`MESH:C535420`](http://id.nlm.nih.gov/mesh/C535420) "Charcot-Marie-Tooth disease, Type 4B1"
  - [`MESH:C535421`](http://id.nlm.nih.gov/mesh/C535421) "Charcot-Marie-Tooth disease, Type 4B2"
  - [`MESH:C536446`](http://id.nlm.nih.gov/mesh/C536446) "Corpus callosum agenesis neuronopathy"
  - [`MESH:C537984`](http://id.nlm.nih.gov/mesh/C537984) "Charcot-Marie-Tooth disease, Type 1C"
  - [`MESH:C537985`](http://id.nlm.nih.gov/mesh/C537985) "Charcot-Marie-Tooth disease, Type 1D"
  - [`MESH:C537989`](http://id.nlm.nih.gov/mesh/C537989) "Charcot-Marie-Tooth disease, Type 2B"
  - [`MESH:C537990`](http://id.nlm.nih.gov/mesh/C537990) "Charcot-Marie-Tooth disease, Type 2B1"
  - [`MESH:C537991`](http://id.nlm.nih.gov/mesh/C537991) "Charcot-Marie-Tooth disease, Type 2B2"
  - [`MESH:C564257`](http://id.nlm.nih.gov/mesh/C564257) "Charcot-Marie-Tooth Disease, Dominant
    Intermediate C"
  - [`MESH:C564333`](http://id.nlm.nih.gov/mesh/C564333) "Charcot-Marie-Tooth Disease, Dominant
    Intermediate D"
  - [`MESH:C564702`](http://id.nlm.nih.gov/mesh/C564702) "Charcot-Marie-Tooth Disease, Dominant
    Intermediate A"
  - [`MESH:C564703`](http://id.nlm.nih.gov/mesh/C564703) "Charcot-Marie-Tooth Disease, Dominant
    Intermediate B"
  - [`MESH:D002607`](http://id.nlm.nih.gov/mesh/D002607) "Charcot-Marie-Tooth Disease"
  - [`MESH:D015417`](http://id.nlm.nih.gov/mesh/D015417) "Hereditary Sensory and Motor Neuropathy"
  - [`MEDDRA:10008414`](http://identifiers.org/meddra/10008414)
  - [`MEDDRA:10019896`](http://identifiers.org/meddra/10019896)
  - [`MEDDRA:10034609`](http://identifiers.org/meddra/10034609)
  - [`MEDDRA:10034699`](http://identifiers.org/meddra/10034699)
  - [`MEDDRA:10075469`](http://identifiers.org/meddra/10075469)
  - [`MEDDRA:10077306`](http://identifiers.org/meddra/10077306)
  - [`NCIT:C75467`](http://purl.obolibrary.org/obo/NCIT_C75467) "Charcot-Marie-Tooth Disease"
  - [`SNOMEDCT:65017003`](http://snomed.info/id/65017003)
  - [`SNOMEDCT:702439002`](http://snomed.info/id/702439002)
  - `MEDGEN:162893`
  - [`ICD10:G60.0`](https://icd.codes/icd9cm/G60.0)
  - [`ICD9:356.0`](http://translator.ncats.nih.gov/ICD9_356.0)
  - [`ICD9:356.1`](http://translator.ncats.nih.gov/ICD9_356.1)
  - `GARD:12431` "Charcot-Marie-Tooth disease type 2" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:12435` "Charcot-Marie-Tooth disease axonal type 2P"
    **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:1245` "Charcot-Marie-Tooth disease, type IA" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:6034` "Charcot-Marie-Tooth disease" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:7883` "Werdnig-Hoffmann disease" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:9190` "Charcot-Marie-Tooth disease type 1E" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:9192` "Charcot-Marie-Tooth disease type 2B" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `GARD:9200` "Charcot-Marie-Tooth disease type 4B2" **(existing identifier, also added by GARD)**
    **(NOT emitted — prefix not registered in Biolink Model for `biolink:Disease`)**
  - `MIM:118200`
  - `MIM:118210`
  - `MIM:118220`
  - `MIM:118230`
  - `MIM:118300`
  - `MIM:214400`
  - `MIM:218000`
  - `MIM:253300`
  - `MIM:300905`
  - `MIM:302800`
  - `MIM:302801`
  - `MIM:302802`
  - `MIM:310490`
  - `MIM:311070`
  - `MIM:600882`
  - `MIM:601098`
  - `MIM:601382`
  - `MIM:601455`
  - `MIM:601472`
  - `MIM:601596`
  - `MIM:604484`
  - `MIM:604563`
  - `MIM:605253`
  - `MIM:605285`
  - `MIM:605588`
  - `MIM:605589`
  - `MIM:606071`
  - `MIM:606482`
  - `MIM:606483`
  - `MIM:606595`
  - `MIM:607677`
  - `MIM:607678`
  - `MIM:607684`
  - `MIM:607731`
  - `MIM:607734`
  - `MIM:607736`
  - `MIM:607791`
  - `MIM:607831`
  - `MIM:608323`
  - `MIM:608673`
  - `MIM:609260`
  - `MIM:609311`
  - `MIM:611228`
  - `MIM:613287`
  - `MIM:613641`
  - `MIM:614228`
  - `MIM:614436`
  - `MIM:614455`
  - `MIM:614895`
  - `MIM:615025`
  - `MIM:615185`
  - `MIM:615284`
  - `MIM:615376`
  - `MIM:615490`
  - `MIM:616039`
  - `MIM:616280`
  - `MIM:616684`
  - `MIM:616687`
  - `MIM:617017`
  - `MIM:PS118220`
  - `ORDO:100043`
  - `ORDO:100044`
  - `ORDO:100045`
  - `ORDO:100046`
  - `ORDO:101075`
  - `ORDO:101076`
  - `ORDO:101077`
  - `ORDO:101078`
  - `ORDO:101081`
  - `ORDO:101082`
  - `ORDO:101083`
  - `ORDO:101084`
  - `ORDO:101085`
  - `ORDO:101097`
  - `ORDO:101101`
  - `ORDO:101102`
  - `ORDO:139515`
  - `ORDO:1496`
  - `ORDO:228174`
  - `ORDO:254334`
  - `ORDO:284232`
  - `ORDO:300319`
  - `ORDO:329258`
  - `ORDO:352670`
  - `ORDO:352675`
  - `ORDO:363981`
  - `ORDO:369867`
  - `ORDO:391351`
  - `ORDO:397735`
  - `ORDO:397968`
  - `ORDO:435387`
  - `ORDO:435998`
  - `ORDO:443950`
  - `ORDO:64746`
  - `ORDO:90658`
  - `ORDO:93114`
  - `ORDO:98856`
  - `ORDO:99014`
  - `ORDO:99936`
  - `ORDO:99937`
  - `ORDO:99938`
  - `ORDO:99939`
  - `ORDO:99940`
  - `ORDO:99942`
  - `ORDO:99943`
  - `ORDO:99945`
  - `ORDO:99946`
  - `ORDO:99947`
  - `ORDO:99948`
  - `ORDO:99949`
  - `ORDO:99950`
  - `ORDO:99951`
  - `ORDO:99952`
  - `ORDO:99953`
  - `ORDO:99954`
  - `ORDO:99955`
  - `ORDO:99956`
  - `SNOMEDCT_US_2025_09_01:128202008`
  - `SNOMEDCT_US_2025_09_01:193158000`
  - `SNOMEDCT_US_2025_09_01:763135001`
  - `http://id.who.int/icd/entity/1443432032`
