# DOID mappings: an ICD code shared by two diseases is not an equivalence

DOID cross-references ICD-10, ICD-9 and ICD-O codes with `hasDbXref`, and every concord row is fed
to `glom()` as an equivalence assertion. An ICD code often names a disease *family*, and then one
code merges every subtype that cites it. Babel drops exactly those: `remove_overused_xrefs` is
scoped to DOID's ICD prefixes (`OVERUSE_FILTERED_CONCORDS` in
`src/createcompendia/diseasephenotype.py`), so an ICD code claimed by two or more DOID terms is
dropped and a code claimed by one is kept. See issue #1029.

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

## Why the filter is scoped to ICD, and why it is a filter rather than an exclusion

Two instruments were available and neither is right on its own, which is why the filter takes an
argument naming the namespaces it may act on:

- **`remove_overused_xrefs` unscoped** — what MONDO/HP/EFO/MP get — **over-cleans everything else.**
  It drops 618 MeSH, 271 SNOMED, 148 ORDO and 88 UMLS rows, including correct ones.
  [`MESH:D010195`](http://id.nlm.nih.gov/mesh/D010195) "Pancreatitis" is claimed by both
  [`DOID:4989`](http://purl.obolibrary.org/obo/DOID_4989) "pancreatitis" (correct) and
  [`DOID:2913`](http://purl.obolibrary.org/obo/DOID_2913) "acute pancreatitis" (too narrow) — the
  filter discards both, losing a genuine equivalence to suppress an over-broad one.
- **A categorical prefix exclusion over-cleans ICD.** Only 298 of DOID's 5,135 distinct ICD targets
  are claimed twice; **4,837 of the 6,425 ICD rows are 1:1**, and many are plainly right
  ([`ICD10:A01.0`](https://icd.who.int/browse10/2019/en#/A01.0) "Typhoid fever" ->
  [`DOID:13258`](http://purl.obolibrary.org/obo/DOID_13258) "typhoid fever"). Dropping the
  namespace deleted all 4,837 to suppress the 1,583.

Scoping the overuse filter to the ICD prefixes takes the useful half of each: only ICD is policed,
and within ICD only the codes that demonstrably name more than one DOID term. The four merge engines
go and the 1:1 rows stay.

The argument for the categorical exclusion was that a 1:1 code today is an accident of granularity —
`ICD10:A01.0` would fuse every typhoid subtype DOID might add tomorrow. The scoped filter answers
that by construction: it recounts on every build, so the row goes the day a second subtype cites it.
Paying the cost of 4,837 deleted mappings today to insure against that is the worse trade.

Measured by rebuilding the DOID concord through `build_disease_doid_relationships()` and replaying
`compute_cliques_for_impact_report()` over a complete local `disease` intermediate set. All three
columns use the current prefix rename map (below), so they differ only in ICD treatment — none of
them is a build that ever shipped, and the middle column never will be. That is the point: it prices
the alternative fix, which a before/after clique diff structurally cannot do.

| | ICD kept | overuse-filtered | **ICD overuse-filtered** | ICD excluded |
| --- | --- | --- | --- | --- |
| identifiers | 757,770 | 757,389 | **757,474** | 752,649 |
| cliques | 440,661 | 440,616 | 440,645 | 440,645 |
| largest clique | 307 | 83 | 99 | 92 |
| cliques with >=50 identifiers | 53 | 11 | 23 | 16 |
| cliques with >=20 identifiers | 834 | 599 | 747 | 609 |
| `MONDO:0000912` "AR nonsyndromic hearing loss 5" | 288 | 6 | 6 | 6 |

The third column is what ships. Against the categorical exclusion it **keeps 4,825 more
identifiers** — very nearly the 4,837 1:1 rows — while fixing the same mega-cliques:
`MONDO:0000912` goes from 288 members to 6 either way, and the largest clique in the build falls
from 307 to 99.

It does leave more large cliques than the exclusion (23 vs 16 at `>=50`, 747 vs 609 at `>=20`).
That residue is real and worth naming: a DOID ICD row that is 1:1 *within DOID* can still bridge
DOID to HP or EFO, which emit ICD codes of their own — the cross-source overlap counted in
[issue #1035](https://github.com/NCATSTranslator/Babel/issues/1035). The filter only sees one
concord at a time, so it cannot catch those; that is the ICD question that remains open, not this
one.

Two cautions on reading the table. The `>=50` and `>=20` rows are not a like-for-like ranking of
"which is cleaner", because the unscoped filter also breaks up MeSH/SNOMED merges this change
deliberately leaves alone. And the per-clique probes are no longer a clean signal in the `ICD kept`
column: with every ICD row present, `glom()`'s `DISEASE_UNIQUE_PREFIXES` refuses merges that would
put two MONDO ids in one clique, so the family fragments instead of showing up at full size and a
given MONDO can land in a small piece of it. `largest clique` is the honest measure of the raw
problem; only `MONDO:0000912` is kept above, as the one probe the fragmentation does not distort.

## What is dropped, and what is kept

DOID's concord carries **6,425 ICD rows** (ICD10 3,687, ICD9 2,238, ICD0 495, ICD11 5) across 5,135
distinct codes. They all stay in the concord — the filter runs at glom time — so
[`mappings/icd-targets.csv`](mappings/icd-targets.csv) lists every one with both endpoints
labelled, and `babel-overused-xrefs` can still audit them.

**Dropped: 1,583 rows on 298 codes claimed by 2+ DOID terms.** These are the merge engines:

| target | label | DOID terms citing it |
| --- | --- | --- |
| `ICD10:H90.3` | Sensorineural hearing loss, bilateral | 134 |
| `ICD10:H35.5` | Hereditary retinal dystrophy | 107 |
| `ICD10:G11.4` | Hereditary spastic paraplegia | 60 |
| `ICD10:G60.0` | Hereditary motor and sensory neuropathy | 58 |

[`ICD10:G11.4`](https://icd.who.int/browse10/2019/en#/G11.4) is the worked case: it is
"Hereditary spastic paraplegia", carried by [`DOID:2476`](http://purl.obolibrary.org/obo/DOID_2476)
and by all 60 of its subtypes, so `glom()` fused 61 mutually-exclusive diseases into one clique.

**Kept: 4,837 rows on 4,837 codes cited by exactly one DOID term.** These read as ordinary
equivalences and are the reason the categorical exclusion was replaced:

| target | label | subject |
| --- | --- | --- |
| `ICD10:A01.0` | Typhoid fever | [`DOID:13258`](http://purl.obolibrary.org/obo/DOID_13258) "typhoid fever" |
| `ICD10:G56.3` | Lesion of radial nerve | [`DOID:12170`](http://purl.obolibrary.org/obo/DOID_12170) "radial nerve lesion" |
| `ICD9:363.43` | Angioid streaks of choroid | [`DOID:979`](http://purl.obolibrary.org/obo/DOID_979) "angioid streaks of choroid" |

By prefix, the dropped 298 codes are ICD10 245, ICD0 33, ICD9 20. Samples above are drawn from
opposite ends of the file — the most-cited codes, then 1:1 rows spread across it — rather than its
head, since the point turns on both shapes existing.

**`ICD0` rows survive the filter but never reach a compendium.** `ICD0` is not registered in
`biolink:Disease`'s `id_prefixes`, so `write_compendium()` drops every one of the 462 that the
filter keeps — after they have already done their merging in `glom()`. A build-vs-build count
confirms it: ICD members go from 38 to 4,438 across the two disease compendia, all of them `ICD10`
(2,241), `ICD9` (2,192) and `icd11` (5), with `ICD0` contributing nothing either side. That is the
same defect as MONDO's `ICD10CM:`, so it is tracked with it in
[issue #1035](https://github.com/NCATSTranslator/Babel/issues/1035) rather than here; it is not a
regression this change introduces, and dropping `ICD0` at the source would be a second, separate
judgement about whether an ICD-O morphology code is ever a disease equivalence.

## Overuse in DOID's other namespaces is still open

DOID is in `OVERUSE_FILTERED_CONCORDS` **scoped to ICD**, so overuse outside ICD is untouched.

- [ ] 537 non-ICD targets (1,258 rows) are still claimed by 2+ DOID terms: MESH 248, SNOMEDCT 130,
  orphanet 59, UMLS 41, NCIT 35, GARD 11, OMIM 11, KEGG.DISEASE 2. Some are wrong and some
  (pancreatitis, papilloma) are right, so this needs per-case review rather than widening the scope
  to `None`, plus the question of whether MONDO/UMLS already supply the correct mappings anyway.
  The record is [`mappings/overused-targets.csv`](mappings/overused-targets.csv), which lists all
  835 overused targets — the 298 ICD ones the filter drops and the 537 it does not — so filter on
  `target_prefix` to see just what still merges.

  Widening is a one-word change (`OVERUSE_FILTERED_CONCORDS["DOID"] = None`), which is the point of
  scoping it this way: the decision is per-namespace and reversible, not baked into how the concord
  is written.

## Open before release

- [x] **Confirmed on a real build with `babel-clique-diff`**, two local `disease` builds of the same
  intermediates — the PR's base commit against its head. Result in
  [`mappings/clique-diff.csv`](mappings/clique-diff.csv) and
  [`mappings/clique-diff.json`](mappings/clique-diff.json):

  | | before | after |
  | --- | --- | --- |
  | identifiers across both compendia | 738,483 | **744,528** |
  | `Disease.txt` cliques | 365,510 | 365,085 |
  | `PhenotypicFeature.txt` cliques | 75,478 | 75,477 |

  3,740 cliques changed, 699 members regrouped, 8 moved between compendia, **5 dropped**. The
  clique count falls by 425 while identifiers rise by 6,045: the renames and the kept ICD rows
  mostly *add members to existing cliques* rather than merging cliques together, which is what a
  mapping that was previously joining nothing should do.
- [ ] **5 identifiers are lost, and they need an SME.** `DOID:0080409` "familial adenomatous
      polyposis 1", `orphanet:733` "Familial adenomatous polyposis", `orphanet:321` "Multiple
      osteochondromas", `OMIM:133701` and `OMIM:600209` are in a compendium before this change and
      in none after. The mechanism is not a filter: the new mappings pull them into cliques that
      HP's type-vote turns into `biolink:PhenotypicFeature`, and none of `DOID`/`OMIM`/`orphanet` is
      registered for that class, so `write_compendium()` drops them silently. `UMLS:C1851413`
      "EXOSTOSES, MULTIPLE, TYPE II" moving into the
      [`HP:0002762`](http://purl.obolibrary.org/obo/HP_0002762) "Exostoses" clique is the worked
      case. The question is whether the merge is right — a disease and the phenotype named for it
      are not obviously the same clique — and if it is not, the fix is a pair in
      `input_data/disease_badxrefs.txt`, not a change here. This is the check
      [`docs/sources/CLAUDE.md`](../CLAUDE.md) describes under "Where an identifier ends up is a
      claim about it".
- [ ] **EFO and HP emit ICD xrefs too** (62 and 46 rows), and MONDO emits 2,030 under the other
      spelling, `ICD10CM:`. Tracked in
      [issue #1035](https://github.com/NCATSTranslator/Babel/issues/1035), which also records the 21
      codes that unifying the spellings would newly merge, and why `diseasephenotype.py`'s HP
      `ignore_list=["ICD"]` — a latent no-op — must not be "fixed" before that question is settled.

## Prefixes DOID spells its own way

Beyond ICD, every xref target has to reach the Babel prefix its clique uses, or it is a merge hazard
of exactly the same shape: a CURIE no ids file carries joins nothing, gets dropped by
`write_compendium()` as an unregistered prefix — and still reaches `glom()` first, fusing every DOID
term that cites it. A rename that is missing does not error. It is silent.

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
answer (their ICD xrefs are largely 1:1 and often correct). See issue #1035.

## Regenerating

Both CSVs come from the built concord, which now keeps its ICD rows — no special pre-filter build
is needed any more.

```bash
# every ICD row, kept or dropped: --min-subjects 1 lists them all, and subject_count says which
# side of the filter each falls on
uv run babel-overused-xrefs --concord babel_outputs/intermediate/disease/concords/DOID \
    --min-subjects 1 --target-prefixes ICD10,ICD9,ICD0,ICD11 \
    --out docs/sources/DOID/mappings/icd-targets.csv --mrconso babel_downloads/UMLS/MRCONSO.RRF

# every overused target in the concord, ICD and not
uv run babel-overused-xrefs --concord babel_outputs/intermediate/disease/concords/DOID \
    --out docs/sources/DOID/mappings/overused-targets.csv --mrconso babel_downloads/UMLS/MRCONSO.RRF

# the clique table above, all four scenarios
uv run python docs/sources/DOID/mappings/scripts/measure_icd_xrefs.py
```

The measurement script rebuilds the concord through production
`build_disease_doid_relationships()` and toggles the production constants, and the tool shares
`find_overused_xref_targets()` with it, so neither can drift from what the build does.
