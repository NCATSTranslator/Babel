# MONDO close-match guard: before/after clique diff

This directory records the build-vs-build clique diff that measures the effect of activating
`glom()`'s MONDO close-match guard.

- Bug: [#912](https://github.com/NCATSTranslator/Babel/issues/912)
- Fix: [#888](https://github.com/NCATSTranslator/Babel/pull/888) (`fix-mondo-close-guard`)

## What the change is

`glom()`'s `close={MONDO: ...}` guard (`src/babel_utils.py`) is meant to stop a MONDO term from
merging with a CURIE that is only a *close* (not exact) match. The loader that fed it keyed each
MONDO subject to column 2 of the `MONDO_close` concord (the predicate, `oio:closeMatch`) instead of
column 3 (the close-match object CURIE), so the recorded value never appeared in any clique and the
guard never fired — a silent no-op since it was introduced in 2021. The fix keys on the object
column, activating the guard. See #912 for the full history.

## How this diff was produced

Both compendia were built from the **same cached disease intermediates**
(`babel_outputs/intermediate/disease/`); the only thing that differs between the two builds is
`src/createcompendia/diseasephenotype.py` (`close_mondos` keyed on `x[2]` vs `x[1]`), so the diff
isolates exactly this change and nothing else.

```text
babel-clique-diff \
  --before <main, predicate-keyed close (no-op guard)>/compendia \
  --after  <fix-mondo-close-guard, object-keyed close (guard active)>/compendia \
  --files Disease.txt PhenotypicFeature.txt
```

`clique-diff.summary.json` is the headline; `clique-diff.csv` has one row per
(changed before-clique, after-destination) group.

## Result

Activating the guard changes disease clique merging as intended: close-but-not-exact matches no
longer collapse into exact MONDO cliques.

### Disease.txt

- 1,228 before-cliques changed (out of 365,466).
- **1,218 members dropped** from the compared compendia — **every one is a MEDDRA identifier**.
  These are the close-match MEDDRA terms that were reaching MONDO disease cliques transitively
  through the UMLS concord; the activated guard pulls them back out, and with the merge refused
  they leave the disease output entirely.
- 114 members regrouped (redistributed within Disease.txt; mostly MEDDRA and UMLS).
- 72 members moved to PhenotypicFeature.txt (a handful of cliques retyped once the MEDDRA members
  no longer anchored them to a MONDO disease leader).
- Net clique count +20 (365,466 → 365,486): a few cliques split as close matches peeled off.

The 1,218 figure matches the ~1,219 MEDDRA drop reported in the earlier combined analysis on
[#883](https://github.com/NCATSTranslator/Babel/pull/883).

### PhenotypicFeature.txt

Essentially unaffected: 1 changed clique, 0 dropped members, 2 members moved. The guard is
MONDO-scoped, and MONDO cliques are disease-typed, so phenotype cliques barely move.

## Cliques that actually split — SME review needed

The 1,218 dropped identifiers are all MEDDRA, and MEDDRA is barely used downstream, so those
drops are low-stakes. The changes that need a subject-matter expert's eye are the small number of
cliques that did not merely shed a MEDDRA term but **structurally split**, moving a real
(non-MEDDRA) identifier out of the MONDO clique. There are 23 of these (the net Disease clique
count rose by 20): 19 split a piece off into a brand-new clique, and 4 re-attached the piece to a
different, already-existing MONDO clique.

**Why a real identifier gets ejected.** When the guard fires, `glom()` drops the *entire* pairwise
concord link, not just the offending MEDDRA term (it `continue`s past the whole merge). So if a
legitimate UMLS/DOID exact-equivalent of a MONDO term happens to arrive in the same group as a
MEDDRA that MONDO only *close*-matches, that UMLS/DOID identifier is ejected as collateral damage.
That is why many rows below pair a MONDO term with an **identically labelled** UMLS/DOID concept
(marked ⚠ — a strong signal the split is a regression, e.g. the two `multiple endocrine neoplasia`
DOID splits, or `toxic oil syndrome` ↔ `Toxic oil syndrome`). Others separate a genuinely distinct
close concept and are improvements — e.g.
[`MONDO:0009297`](http://purl.obolibrary.org/obo/MONDO_0009297) "familial renal glucosuria"
correctly no longer subsumes the broader `UMLS:C0017980` "Glycosuria, Renal". Each row needs an SME
to decide which it is.

These 23 rows are also in `split-cliques.csv` (a `near_identical_label` column flags the ⚠ cases
and an empty `sme_assessment` column is there to fill in). Members shown below are examples (up to
five per row); see `clique-diff.csv` for the full membership.

### Split into a brand-new clique (19)

- ⚠ **MONDO:0000889** "haemophilus meningitis" → new clique **UMLS:C0276028** "Haemophilus
  influenzae meningitis" (+ 2 MEDDRA)
- **MONDO:0001561** "pyloric stenosis" → new clique **UMLS:C0162651** "Gastric outlet obstruction"
  (+ UMLS:C1541124 "Pyloric obstruction", SNOMEDCT:244815007, 2 MEDDRA)
- **MONDO:0007064** "SCID due to adenosine deaminase deficiency" → new clique **UMLS:C0268124**
  "Adenosine deaminase deficiency" (+ 2 MEDDRA)
- ⚠ **MONDO:0007540** "multiple endocrine neoplasia type 1" → new clique **DOID:10017** "multiple
  endocrine neoplasia type 1" (+ ICD10:E31.21, ICD9:258.01, 2 MEDDRA)
- **MONDO:0007896** "acute monocytic leukemia" → new clique **UMLS:C0457334** "Acute monoblastic
  leukemia" (+ NCIT:C7171, 4 MEDDRA)
- **MONDO:0008303** "familial male-limited precocious puberty" → new clique **UMLS:C1504412**
  "Testotoxicosis" (+ 1 MEDDRA)
- ⚠ **MONDO:0009020** "macular corneal dystrophy" → new clique **UMLS:C0024439** "Macular corneal
  dystrophy" (+ 1 MEDDRA)
- **MONDO:0009297** "familial renal glucosuria" → new clique **UMLS:C0017980** "Glycosuria, Renal"
  (+ 2 MEDDRA) — *improvement (distinct broader concept)*
- **MONDO:0010269** "Coats disease" → new clique **UMLS:C0154832** "Exudative retinopathy" (+
  HP:0007898, SNOMEDCT:25506007, 2 MEDDRA)
- **MONDO:0015274** "chronic beryllium disease" → new clique **UMLS:C0005138** "Berylliosis" (+
  NCIT:C197848, SNOMEDCT:8247009, 1 MEDDRA)
- ⚠ **MONDO:0016421** "toxic oil syndrome" → new clique **UMLS:C0409998** "Toxic oil syndrome" (+ 2
  MEDDRA)
- ⚠ **MONDO:0017169** "multiple endocrine neoplasia" → new clique **DOID:3125** "multiple endocrine
  neoplasia" (+ 4 MEDDRA)
- ⚠ **MONDO:0017201** "Spasmus nutans" → new clique **UMLS:C1527306** "spasmus nutans" (+ 1 MEDDRA)
- **MONDO:0018301** "interstitial cystitis" → new clique **UMLS:C0600040** "Chronic interstitial
  cystitis" (+ 2 MEDDRA)
- ⚠ **MONDO:0018952** "argyria" → new clique **UMLS:C0003782** "Argyria" (+ 3 SNOMEDCT, 1 MEDDRA)
- **MONDO:0019136** "Zygomycosis" → new clique **UMLS:C0026718** "Mucormycosis" (+ MESH:D009091, 1
  MEDDRA)
- ⚠ **MONDO:0019168** "pyomyositis" → new clique **UMLS:C1704275** "Pyomyositis" (+ 1 MEDDRA)
- **MONDO:0019735** "polymyalgia rheumatica" → new clique **UMLS:C1527406** "Rhizomelic
  pseudopolyarthritis" (+ 1 MEDDRA)
- ⚠ **MONDO:0020115** "secondary polycythemia" → new clique **UMLS:C5848252** "Secondary
  polycythemia" (+ 4 MEDDRA)

### Re-attached to a different existing MONDO clique (4)

- **MONDO:0015597** "palmoplantar pustulosis" → **MONDO:0013626** "psoriasis 14, pustular" (moved
  HP:0100847, SNOMEDCT:27520001, UMLS:C0030246, 1 MEDDRA)
- **MONDO:0016575** "primary ciliary dyskinesia" → **MONDO:0009484** "primary ciliary dyskinesia 1"
  (moved UMLS:C4551720, 2 MEDDRA)
- **MONDO:0016702** "oligoastrocytoma" → **MONDO:0003268** "mixed glioma" (moved NCIT:C129323,
  UMLS:C0280793, 2 MEDDRA)
- **MONDO:0017850** "sirenomelia" → **MONDO:0010831** "familial caudal dysgenesis" (moved
  HP:0010497, SNOMEDCT:253191000, 3 MEDDRA)

## Files

- `clique-diff.summary.json` — per-compendium counts (committed).
- `clique-diff.csv` — per-clique change rows (committed; ~530 KB, 2,458 rows).
- `split-cliques.csv` — the 23 structural splits above, for SME review (committed; ~3 KB).
