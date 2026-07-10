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

## Files

- `clique-diff.summary.json` — per-compendium counts (committed).
- `clique-diff.csv` — per-clique change rows (committed; ~530 KB, 2,458 rows).
