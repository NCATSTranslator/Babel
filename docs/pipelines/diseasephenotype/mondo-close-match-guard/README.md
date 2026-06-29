# MONDO close-match guard: activating `close=` in disease glom

This directory documents the before/after impact of fixing a latent bug in how the
disease/phenotype build reads the `MONDO_close` concord, and is the evidence for the change
in `src/createcompendia/diseasephenotype.py` that activates glom's close-match guard.

## What the guard is for

`glom()` takes a `close=` map (`src/babel_utils.py`). For each MONDO identifier in a
candidate merged clique, it looks up that MONDO's *close* (but not *exact*) matches; if one
of those close-match identifiers would end up in the same clique, the merge is blocked. The
intent is to stop a close match from being silently promoted to an exact match — a MONDO
disease and a merely *close* MEDDRA/MONDO/ORDO term should not normalize together.

The close-match pairs come from `MONDO_close`, a 3-column concord
(`subject  predicate  object`, e.g. `MONDO:0000739  oio:closeMatch  MEDDRA:10051962`)
written by `ubergraph.build_sets(..., set_type="close")`.

## The bug

`compute_cliques_for_impact_report()` (formerly `build_compendium()`) read `MONDO_close`
with `close_mondos[x[0]].add(x[1])` — keying the subject to **column 2, the predicate**
(`oio:closeMatch`) rather than **column 3, the object**. No clique ever contains the literal
string `oio:closeMatch`, so the guard's `if cd in newset` test never matched and the guard
was a **silent no-op** on every build, on `main` and before it. Close matches were free to
collapse into exact cliques.

The fix is one character of intent: key on `x[2]` (the close-match object), matching the
`(stuff[0], stuff[2])` parsing every other concord in that function already uses.

## Impact of activating the guard

Measured on a full local `disease` build (Biolink 4.4.3), same intermediate ids/concords,
differing only in `x[1]` vs `x[2]`. glom is deterministic (two `x[1]` builds were byte
-identical at the clique level), so every difference below is signal, not run-to-run noise.

- **1,219 identifiers — all MEDDRA — are dropped from `Disease.txt`.** They were present
  only because the dormant guard let them merge into a MONDO disease clique; once the guard
  correctly keeps them out, they have no independent disease typing in this pipeline and
  fall out of the compendium entirely. Example: `MEDDRA:10044701` and `MEDDRA:10058084`
  leave [`MONDO:0000088`](http://purl.obolibrary.org/obo/MONDO_0000088) "precocious puberty".
- **1,191 of 365,465 Disease cliques** lose at least one member; net Disease clique count
  rises by 20 (365,465 → 365,485) and PhenotypicFeature by 13.
- **`PhenotypicFeature.txt` is essentially unaffected** (1 clique changed, 0 drops) — the
  close pairs are MONDO-subject, so the effect is concentrated in the disease compendium.

The headline number is in `summary.json` as `dropped_member_count`.

## The decision this evidence supports

Dropping 1,219 MEDDRA codes from the disease compendia means they will no longer normalize
to their previously-assigned MONDO disease. That is *correct* if these are genuinely
distinct concepts (the guard's premise), but it is a **coverage loss** if downstream
consumers rely on that MEDDRA → MONDO normalization. Per the project rule that we do not
drop valid identifiers without good reason, this is an SME call — hence a standalone PR with
this analysis rather than a change riding along with an unrelated feature.

## Artifacts

- `clique-diff.csv` — every changed clique, one row per (before-clique, after-destination)
  group, with `destination_kind` in `kept` / `regrouped` / `moved` / `dropped`.
- `dropped-members.csv` — the 1,219 dropped CURIEs, each with the MONDO clique (and its
  label) it was dropped from. The SME-facing review list.
- `summary.json` — per-compendium counts.

## Regenerating

```bash
# Build the baseline (x[1], guard dormant) and the fixed (x[2], guard active) compendia,
# saving each build's Disease.txt / PhenotypicFeature.txt into separate directories, then:
uv run babel-clique-diff \
    --before <x1-compendia-dir> --after <x2-compendia-dir> \
    --files Disease.txt PhenotypicFeature.txt \
    --out-csv docs/pipelines/diseasephenotype/mondo-close-match-guard/clique-diff.csv \
    --out-json docs/pipelines/diseasephenotype/mondo-close-match-guard/summary.json
```

See `docs/tools/README.md` ("`tools/clique_diff`") for the general build-vs-build diff tool.
