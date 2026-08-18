# DOID mappings: an ICD code is not an equivalence

DOID cross-references ICD-10, ICD-9 and ICD-O codes with `hasDbXref`, and every concord row is fed
to `glom()` as an equivalence assertion. An ICD code names a disease *family*, so one code merges
every subtype that cites it. Babel therefore drops DOID's ICD xrefs where the concord is built,
via `DOID_EXCLUDED_XREF_PREFIXES` in `src/createcompendia/diseasephenotype.py`; see issue #1029.

## The mechanism

```text
MONDO:0019064 "hereditary spastic paraplegia"
  --oio:exactMatch--> DOID:2476            (grouping term <-> grouping term, correct)
DOID:2476             --xref--> ICD10:G11.4
DOID:0110764 "hereditary spastic paraplegia 11" --xref--> ICD10:G11.4
DOID:0110782 "hereditary spastic paraplegia 31" --xref--> ICD10:G11.4
... 60 DOID terms, all citing the same code
```

`ICD10:G11.4` is "Hereditary spastic paraplegia" — one code for the whole family. Because every
subtype carries it too, `glom()` merged 61 mutually-exclusive HSP subtypes into one 223-identifier
clique.

MONDO is not at fault. Its concord's most-shared target is claimed by just two subjects — i.e.
essentially 1:1 curated exact matches — and the `MONDO:0019064 -> DOID:2476` edge is correct. Every
many-to-one edge here is DOID's. This is the failure mode [`docs/sources/CLAUDE.md`](../CLAUDE.md)
documents under "An OBO `hasDbXref` is not an equivalence".

## Why all ICD rows go, not just the overused ones

The obvious fix is `remove_overused_xrefs` (drop any target claimed by 2+ subjects), which is what
MONDO/HP/EFO/MP already get. It is the wrong instrument for DOID's ICD problem in *both*
directions:

- **It under-cleans ICD.** Only 245 of DOID's 2,476 distinct ICD-10 targets are overused, so
  **4,837 of the 6,420 ICD rows are 1:1** and survive the filter untouched.
- **It over-cleans everything else.** It drops 618 MeSH, 271 SNOMED, 148 ORDO and 88 UMLS rows,
  including correct ones. [`MESH:D010195`](http://id.nlm.nih.gov/mesh/D010195) "Pancreatitis" is
  claimed by both [`DOID:4989`](http://purl.obolibrary.org/obo/DOID_4989) "pancreatitis" (correct)
  and [`DOID:2913`](http://purl.obolibrary.org/obo/DOID_2913) "acute pancreatitis" (too narrow) —
  the filter discards both, losing a genuine equivalence to suppress an over-broad one.

Overuse is a statistical proxy; "an ICD code names a disease family" is a statement about what the
namespace *means*, so it stays true across DOID releases instead of shifting with each one.

Measured by rebuilding the DOID concord through `build_disease_doid_relationships()` and replaying
`compute_cliques_for_impact_report()` over a complete local `disease` intermediate set:

| | as built | overuse-filtered | **ICD excluded** |
| --- | --- | --- | --- |
| identifiers | 770,091 | 769,586 | 764,974 |
| cliques | 440,990 | 440,972 | 440,985 |
| largest clique | 294 | 89 | 103 |
| cliques with >=50 identifiers | 60 | 13 | 20 |
| cliques with >=20 identifiers | 923 | 698 | **681** |
| `MONDO:0019064` "hereditary spastic paraplegia" | 223 | 16 | 15 |
| `MONDO:0000912` "AR nonsyndromic hearing loss 5" | 281 | 7 | 7 |
| `MONDO:0000910` "retinitis pigmentosa 6" | 294 | 7 | 7 |

Both treatments fix the three mega-cliques. The overuse filter wins on the largest-clique and
`>=50` counts, because it also breaks up MeSH/SNOMED merges this change deliberately leaves alone;
the exclusion wins on `>=20`. **The argument for the exclusion is correctness, not the smaller
number.**

## What is dropped, and what that costs

6,420 rows: ICD10 3,683, ICD9 2,237, ICD0 495, ICD11 5. Every one is listed with both endpoints
labelled in [`mappings/icd-targets.csv`](mappings/icd-targets.csv).

The rows that motivated the change — one code, dozens of mutually-exclusive subtypes:

| target | label | DOID terms citing it |
| --- | --- | --- |
| `ICD10:H90.3` | Sensorineural hearing loss, bilateral | 134 |
| `ICD10:H35.5` | Hereditary retinal dystrophy | 107 |
| `ICD10:G11.4` | Hereditary spastic paraplegia | 60 |
| `ICD10:G60.0` | Hereditary motor and sensory neuropathy | 58 |

**Be clear about the cost:** 4,837 of the dropped rows are 1:1, and some of those read as perfectly
good equivalences:

| target | label | subject |
| --- | --- | --- |
| `ICD10:A01.0` | Typhoid fever | [`DOID:13258`](http://purl.obolibrary.org/obo/DOID_13258) "typhoid fever" |
| `ICD10:G56.3` | Lesion of radial nerve | [`DOID:12170`](http://purl.obolibrary.org/obo/DOID_12170) "radial nerve lesion" |
| `ICD9:363.43` | Angioid streaks of choroid | [`DOID:979`](http://purl.obolibrary.org/obo/DOID_979) "angioid streaks of choroid" |

Those merges are lost. The judgement this doc records is that an ICD code is a classification for
billing and statistics rather than an identifier for a disease, so a 1:1 mapping today is an
accident of granularity rather than a guarantee — `ICD10:A01.0` would fuse every typhoid subtype
DOID might add tomorrow, exactly as `ICD10:G11.4` does now. If that trade is judged wrong, the
alternative is a curated allowlist of the 1:1 codes, which `mappings/icd-targets.csv` is the
worksheet for.

Samples above are drawn from opposite ends of the file — the most-cited targets, then 1:1 rows
spread across it — rather than its head, since the point turns on both shapes existing.

## Overuse in DOID's other namespaces is still open

- [ ] DOID is deliberately **not** in `OVERUSE_FILTERED_CONCORDS`. After the ICD exclusion, 533 of
  its xref targets are still claimed by 2+ subjects: MESH 248, SNOMEDCT 126, ORDO 59, UMLS 41,
  NCIT 35, GARD 11, MIM 11, KEGG.DISEASE 2. Some are wrong and some (pancreatitis, papilloma) are
  right, so this needs per-case review rather than a blanket filter, plus the question of whether
  MONDO/UMLS already supply the correct mappings anyway. The record is
  [`mappings/overused-targets.csv`](mappings/overused-targets.csv), generated from the
  post-exclusion concord so it and `icd-targets.csv` do not overlap.

## Open before release

- [ ] **Confirm on a real build with `babel-clique-diff`.** Everything here is a *replay*, which
  only sees cliques the build already produced — it cannot show cliques a change creates, splits,
  or moves *between* compendia (see [`docs/sources/CLAUDE.md`](../CLAUDE.md), "Replaying a pipeline
  function beats rebuilding to measure a change"). The intermediate set behind these numbers is one
  local `disease` build, not a released one.
- [ ] **EFO and HP leak ICD xrefs too** (62 and 46 rows). Their treatment is not obviously DOID's:
  both are already overuse-filtered, and what survives is largely 1:1 and often correct —
  `HP:0000421` "Epistaxis" -> `ICD10:R04.0` is a genuine equivalence, since ICD-10 R-codes are
  symptom codes. Separately, `diseasephenotype.py`'s HP build passes `ignore_list=["ICD"]`, which
  never matches `ICD10:`/`ICD9:`/`ICD0:` because `ubergraph.build_sets` compares prefixes by exact
  equality — a latent no-op, though "fixing" it would delete the good rows.

## Prefixes DOID spells its own way

The ICD rows are dropped, but every *other* xref target has to reach the Babel prefix its clique
uses, or it is a merge hazard of exactly the same shape: a CURIE no ids file carries joins nothing,
gets dropped by `write_compendium()` as an unregistered prefix — and still reaches `glom()` first,
fusing every DOID term that cites it. A rename that is missing does not error. It is silent.

The renames each disease source needs now live in one reviewable block,
`config.yaml: disease_xref_prefixes`, applied by `babel_utils.norm()` and validated against
`src/prefixes.py` when loaded. Three were missing for DOID:

- **`SNOMEDCT_US_2025_09_01:` and six other release stamps.** DOID stamps its SNOMED prefix with
  the release it was drawn from, so the map's four pinned dates had gone stale: of the 5,358 SNOMED
  rows in the release measured here, exactly **one** matched a listed date. `norm()` now retries a
  missed prefix with a trailing `_YYYY_MM_DD` stripped, so the map names the stem `SNOMEDCT_US`
  once — the spelling HP's map already used — and a future DOID release needs no edit.
- **`MIM:` — 6,483 rows.** `MIM` is an alternative CURIE prefix for OMIM
  ([issue #321](https://github.com/NCATSTranslator/Babel/issues/321)); both now standardize to
  `OMIM` until the Biolink Model registers `MIM`, at which point that issue flips the direction.
  332 of those rows are phenotypic series (`MIM:PS303350`), which Babel spells
  `OMIM.PS:303350` — the `PS` belongs to the prefix, not to the local id — so this one rename
  depends on the local id and not just the source prefix. `Text.omim_curie()` holds that rule for
  both `norm()` and `Text.opt_to_curie()`.
- **`ORDO:2822` — 2,321 rows.** DOID's spelling of Orphanet, which Babel writes `orphanet:`. MONDO
  and HP already emit `orphanet:`, so until now none of DOID's Orphanet mappings could join theirs.

One is known and deliberately left for its own change: **`ICD10:` vs `ICD10CM:`**, where DOID, EFO
and HP emit one spelling and MONDO the other — two namespaces for one vocabulary. DOID's ICD rows
are dropped outright by this change, so what remains is a MONDO/EFO/HP question with a different
answer (their ICD xrefs are largely 1:1 and often correct). See issue #1032.

## Regenerating

```bash
# every row the ICD exclusion drops -- needs a concord built with DOID_EXCLUDED_XREF_PREFIXES=[]
uv run babel-overused-xrefs --concord <pre-exclusion DOID concord> \
    --min-subjects 1 --target-prefixes ICD10,ICD9,ICD0,ICD11 \
    --out docs/sources/DOID/mappings/icd-targets.csv --mrconso babel_downloads/UMLS/MRCONSO.RRF

# what overuse remains afterwards
uv run babel-overused-xrefs --concord babel_outputs/intermediate/disease/concords/DOID \
    --out docs/sources/DOID/mappings/overused-targets.csv --mrconso babel_downloads/UMLS/MRCONSO.RRF

# the clique table above, all three scenarios
uv run python docs/sources/DOID/mappings/scripts/measure_icd_xrefs.py
```

The measurement script rebuilds the concord through production
`build_disease_doid_relationships()` and toggles the production constants, and the tool shares
`find_overused_xref_targets()` with it, so neither can drift from what the build does.
