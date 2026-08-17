# DOID overused xrefs: one ICD code, one mega-clique

DOID's concord was not filtered through `remove_overused_xrefs`, so its `hasDbXref` rows were fed
to `glom()` as equivalences. DOID xrefs ICD-10 billing codes, which are one-per-disease-family by
construction, so a single code merged every subtype that cited it. This note records the
measurement behind adding `"DOID"` to `OVERUSE_FILTERED_CONCORDS`
(`src/createcompendia/diseasephenotype.py`); see issue #1029.

## The mechanism

```text
MONDO:0019064 "hereditary spastic paraplegia"
  --oio:exactMatch--> DOID:2476            (grouping term <-> grouping term, correct)
DOID:2476             --xref--> ICD10:G11.4
DOID:0110764 "hereditary spastic paraplegia 11" --xref--> ICD10:G11.4
DOID:0110782 "hereditary spastic paraplegia 31" --xref--> ICD10:G11.4
... 60 DOID terms, all citing the same code
```

`ICD10:G11.4` is the code [`DOID:2476`](http://purl.obolibrary.org/obo/DOID_2476) "hereditary
spastic paraplegia" carries — one code for the whole family. Because every subtype carries it too,
`glom()` merged 61 mutually-exclusive HSP subtypes into one 223-identifier clique.

MONDO is not at fault. Its concord's most-shared target is claimed by just two subjects, i.e.
essentially 1:1 curated exact matches, and the `MONDO:0019064 -> DOID:2476` edge is correct. Every
many-to-one edge here is DOID's. This is the failure mode
[`docs/sources/CLAUDE.md`](../CLAUDE.md) documents under "An OBO `hasDbXref` is not an
equivalence".

## What is overused

831 xref targets in DOID's concord are claimed by two or more DOID subjects. By target prefix:
MESH 248, ICD10 245, SNOMEDCT 126, ORDO 59, UMLS 41, NCIT 35, ICD0 33, ICD9 20, GARD 11, MIM 11,
KEGG.DISEASE 2. So this is not only an ICD problem — but the ICD codes are the ones claimed by
dozens of terms apiece, and they dominate the head of the list.

The eight most-claimed targets, with their ICD-10 label and one example DOID term each:

| target | ICD-10 label | DOID subjects | one of them |
| --- | --- | --- | --- |
| `ICD10:H90.3` | Sensorineural hearing loss, bilateral | 134 | [`DOID:0050566`](http://purl.obolibrary.org/obo/DOID_0050566) "X-linked nonsyndromic deafness" |
| `ICD10:H35.5` | Hereditary retinal dystrophy | 107 | [`DOID:0050572`](http://purl.obolibrary.org/obo/DOID_0050572) "cone-rod dystrophy" |
| `ICD10:G11.4` | Hereditary spastic paraplegia | 60 | [`DOID:0060245`](http://purl.obolibrary.org/obo/DOID_0060245) "Mast syndrome" |
| `ICD10:G60.0` | Hereditary motor and sensory neuropathy | 58 | [`DOID:10595`](http://purl.obolibrary.org/obo/DOID_10595) "Charcot-Marie-Tooth disease" |
| `ICD10:Q12.0` | Congenital cataract | 44 | [`DOID:0110260`](http://purl.obolibrary.org/obo/DOID_0110260) "cataract 7" |
| `ICD10:I42.0` | Dilated cardiomyopathy | 38 | [`DOID:12930`](http://purl.obolibrary.org/obo/DOID_12930) "dilated cardiomyopathy" |
| `ICD10:E23.0` | Hypopituitarism | 32 | [`DOID:9406`](http://purl.obolibrary.org/obo/DOID_9406) "hypopituitarism" |
| `ICD10:Q34.8` | Other specified congenital malformations of respiratory system | 32 | [`DOID:0110594`](http://purl.obolibrary.org/obo/DOID_0110594) "primary ciliary dyskinesia 1" |

Sampled from the head of the list rather than spread across it, because the point being made is
about the most-claimed targets specifically. Every ICD-10 label above names a disease *family* or
a symptom, never one disease — which is precisely why citing one from each subtype fuses them.

### The full record

[`overused-xrefs/overused-targets.csv`](overused-xrefs/overused-targets.csv) has all 831 targets,
2,833 rows, one row per (target, subject) pair with both endpoints labelled:

```csv
target,target_label,target_prefix,subject_count,subject,subject_label
ICD10:G11.4,Hereditary spastic paraplegia,ICD10,60,DOID:0110764,hereditary spastic paraplegia 11
ICD10:G11.4,Hereditary spastic paraplegia,ICD10,60,DOID:0110782,hereditary spastic paraplegia 31
```

Sort by `subject_count` and scan `subject_label`: a target whose subjects carry many different
names is one that fuses unrelated concepts. Every DOID subject is labelled; 84% of target rows
are. What stays blank is informative in its own right — ORDO (148 rows) and ICD0 (91) have no
label source in a Babel checkout, and the unlabelled `SNOMEDCT_US_2025_09_01` rows (152) are
retired SNOMED concepts whose only UMLS strings are marked obsolete, i.e. DOID cross-referencing
codes that no longer exist. `GARD` cells are labelled only if you also have the GARD download
from #980.

While generating this: DOID emits Orphanet xrefs as `ORDO:2822`, but
`build_disease_doid_relationships`'s `other_prefixes` map has no `ORDO` entry, so they are never
normalized to Babel's `orphanet:` prefix. Unrelated to overuse, but probably worth its own look.

## Effect on cliques

Replaying `compute_cliques_for_impact_report()` over a complete local `disease` intermediate set
(all 10 ids files, all 8 concords), with and without `"DOID"` in `OVERUSE_FILTERED_CONCORDS`:

| | DOID unfiltered | DOID filtered |
| --- | --- | --- |
| identifiers | 770,091 | 769,586 |
| cliques | 440,990 | 440,972 |
| largest clique | 294 | 89 |
| cliques with >=50 identifiers | 60 | 13 |
| cliques with >=20 identifiers | 923 | 698 |
| `MONDO:0019064` "hereditary spastic paraplegia" | 223 | 16 |
| `MONDO:0000912` "autosomal recessive nonsyndromic hearing loss 5" | 281 | 7 |
| `MONDO:0000910` "retinitis pigmentosa 6" | 294 | 7 |

Roughly three-quarters of the largest disease cliques existed only because of these xrefs. The
cost is small: 505 identifiers leave the graph, because `remove_overused_xrefs` drops only the
*overused* rows — a genuinely 1:1 ICD mapping is still merged, so an ICD code that names exactly
one disease keeps normalizing to it.

## Regenerating

Two commands, because the target list is a general concord audit while the clique numbers are
specific to this decision:

```bash
# the CSV -- any concord can be audited this way; see docs/tools/OverusedXrefs.md
uv run babel-overused-xrefs \
    --concord babel_outputs/intermediate/disease/concords/DOID \
    --out docs/sources/DOID/overused-xrefs/overused-targets.csv \
    --mrconso babel_downloads/UMLS/MRCONSO.RRF

# the clique table above
uv run python docs/sources/DOID/overused-xrefs/scripts/measure_overused_xrefs.py \
    [--intermediate-root babel_outputs/intermediate]
```

Both go through production code — the tool shares `find_overused_xref_targets()` with the script,
and the script imports `compute_cliques_for_impact_report()` and toggles the production
`OVERUSE_FILTERED_CONCORDS` — so neither measurement can drift from what the build does. Drop
`--mrconso` and the ICD-10/SNOMED label columns come out empty.

## Open before release

Two questions this measurement could not settle. Both were raised on PR #1031 and are unresolved
as of this note; whoever closes them should update this section rather than delete it.

- [ ] **Confirm on a real build with `babel-clique-diff`.** Everything above is a *replay*, which
  only sees cliques the build already produced — it cannot show cliques that a change creates,
  splits, or moves *between* compendia (see [`docs/sources/CLAUDE.md`](../CLAUDE.md), "Replaying a
  pipeline function beats rebuilding to measure a change"). The clique-size table is therefore a
  strong signal, not a build guarantee, and the "cliques" totals in particular are the numbers most
  likely to move. The intermediate set behind it is one local `disease` build, not a released one.
- [ ] **Decide whether prefix-agnostic filtering is the treatment we want.**
  `remove_overused_xrefs` drops *any* target claimed by 2+ DOID subjects, so it also removes DOID's
  MESH (248 targets), SNOMEDCT (126), ORDO (59), UMLS (41) and NCIT (35) rows, not only the 245
  ICD-10 ones — see `overused-xrefs/overused-targets.csv` for exactly which. That is the same
  treatment MONDO/HP/EFO/MP already get, and it is why the fix is one line; but it is broader than
  "stop trusting ICD codes", and no one has looked at whether the non-ICD drops are losses. The
  surgical alternative is a fail-closed `allowed_prefixes` on `doid.build_xrefs()` (the MP
  treatment, [`docs/sources/MP/mappings.md`](../MP/mappings.md)), which states the intent
  explicitly at the cost of a curated prefix list that has to be maintained.
