# Debugging DrugChemical conflation regressions

This page captures how to investigate "these identifiers used to be conflated and now aren't"
problems in the DrugChemical conflation, using Babel issue
[#754](https://github.com/NCATSTranslator/Babel/issues/754) (Carbidopa) as the worked example. It
records both the diagnosis approach and the durable instrumentation we added so the next such
regression is debuggable from retained build artifacts instead of guesswork.

See `docs/Conflation.md` for the conflation output spec, and
`src/createcompendia/drugchemical.py` for the implementation.

## The motivating problem (#754)

Carbidopa fragmented across Babel versions. Reading the published conflation outputs from
`https://stars.renci.org/var/babel_outputs/<version>/conflation/DrugChemical.txt` directly:

- **2024oct24** (Prod, correct) — one clique led by `CHEBI:3395`:
  `["CHEBI:3395", "CHEBI:39585", "PUBCHEM.COMPOUND:146037278", RXCUI:…×27, "UMLS:C1881339"]`.
- **2025sep1** (CI, regressed) — `CHEBI:3395` and `PUBCHEM.COMPOUND:146037278` are gone,
  `CHEBI:192511` is new, and the ~27 RXCUIs plus `UMLS:C1881339` survive. (`CHEBI:39585` and
  `CHEBI:192511` also each appear twice in that line — a separate write/ordering duplication bug
  worth fixing independently; see the prefix-grouping/expansion in `build_conflation()`.)

Because the RxCUI bridge barely changed but the two *chemical* endpoints dropped out, the regression
most likely lives at the **compendium** level (CHEBI:3395 / PUBCHEM no longer share a clique with
the bridge RxCUIs, or got reclassified into a Biolink type a filter rejects), not purely in
conflation logic. Confirming that requires comparing the *inputs* between the two versions — which
is exactly what was hard, because we did not retain enough intermediate detail.

## How DrugChemical conflation merges cliques (and where it can drop things)

`build_conflation()` (`src/createcompendia/drugchemical.py`) builds a list of subject/object CURIE
pairs, normalizes each CURIE to its clique leader, runs `glom()` to merge transitively-connected
pairs, and writes each merged set as one conflation. The pairs come from four sources:

- The RXNORM and UMLS concords (`intermediate/drugchemical/concords/{RXNORM,UMLS}`): each
  `RXCUI:a <pred> RXCUI:b` (or `UMLS:…`) pair is kept **only if both endpoints are RxCUIs that
  belong to a Drug or chemical clique** (looked up via `load_cliques_containing_rxcui()`). If either
  endpoint is not in such a clique, the pair is dropped. This is the primary RxNorm→CHEBI/PUBCHEM
  bridge, and historically the drop was silent.
- The PUBCHEM_RXNORM concord (`RXCUI:a linked PUBCHEM.COMPOUND:b`): the most direct CHEBI/PUBCHEM ↔
  RxCUI link. Pairs are dropped if an endpoint does not resolve to a clique, has no preferred CURIE,
  normalizes to a self-pair, or has a Biolink type that is not a `biolink:ChemicalEntity`
  descendant.
- The manual concord file (`input_data/manual_concords/drugchemical.tsv`): pairs are dropped if a
  CURIE is not in any chemical compendium, or both normalize to the same leader.
- Post-glom: a merged set that collapses to a single identifier after normalization is dropped.

RxCUIs only enter chemical cliques (and thus become usable bridges) via `write_rxnorm_ids()` in
`src/datahandlers/umls.py`, which types each RxCUI by its RxNorm TTY: `DF` (dose form) is excluded
entirely; `IN`/`PIN` → ChemicalEntity; `MIN` → MolecularMixture; everything else → Drug. A RxCUI
typed `Drug` lands in `Drug.txt`, and `biolink:Drug` is **not** a `biolink:ChemicalEntity`
descendant — so the PubChem-path type filter can sever a `Drug`-typed RxCUI bridge. Also note
`build_rxnorm_relationships()` drops a relationship whose subject maps to more than one object
(multi-ingredient drugs), to avoid "everything is everything" over-glomming.

## The durable instrumentation (added for #754)

The core gap was that every one of those drop reasons existed only as a `logger.warning` on STDERR,
which Snakemake discards once a rule succeeds (`src/util.py` deliberately writes no log files), so a
past run left no trace of *why* a cross-reference was dropped. We added:

`ConflationExclusionRecorder` (`src/createcompendia/drugchemical.py`) writes one row per dropped
pair to a gzipped TSV that is now a **declared output** of the `drugchemical_conflation` rule:

```text
babel_outputs/reports/drugchemical/excluded_pairs.tsv.gz
```

Columns: `source, reason, subject, object, subject_type, object_type, detail`. Reason codes mirror
the drop sites listed above: `rxcui_not_in_any_clique`, `no_preferred_curie`, `self_pair`,
`non_chemical_type`, `manual_concord_not_in_compendium`, `manual_concord_self_pair`,
`single_identifier_conflation`. A per-`(source, reason)` summary is also logged and folded into
`babel_outputs/metadata/DrugChemical.yaml` under the `Exclusions` block.

Because it lands under `reports/`, the file is published with every run and retained. Diagnosing a
future "why was X dropped?" becomes one command:

```bash
zcat babel_outputs/reports/drugchemical/excluded_pairs.tsv.gz | grep CHEBI:3395
```

If the dropped CURIE is *not* in the report at all, that itself is informative: the pair was never
generated upstream (the link is missing from the concord), pointing at the compendium-building /
RxCUI typing layer rather than the conflation filter.

The recorder is conflation-scoped today but written to be reusable; `geneprotein.py` could adopt it.
The `build_rxnorm_relationships()` multi-ingredient drop happens during concord building (a
different rule) and is **not** yet captured — instrumenting it would require that rule to emit its
own exclusions file. See the TODO list below.

## Diagnosing #754 once the inputs are available (deferred)

The full root-cause diagnosis is deferred until we have richer retained inputs to diff —
specifically the intermediate concord/identifier Parquet export from
[PR #704](https://github.com/NCATSTranslator/Babel/pull/704). Once both that export and the new
exclusion report exist in a run, the procedure is:

1. Confirm the regression in `conflation/DrugChemical.txt` (done; see above).
2. Check the new `reports/drugchemical/excluded_pairs.tsv.gz`: is `CHEBI:3395` /
   `PUBCHEM.COMPOUND:146037278` / a bridge RxCUI present with a `reason`? If yes, the reason names
   the filter to fix. If absent, the link was never generated → step 4.
3. Use the intermediate-concord Parquet (PR #704) to check whether the raw
   `RXCUI ↔ PUBCHEM.COMPOUND:146037278` and `RXCUI ↔ RXCUI` edges still exist for the Carbidopa
   RxCUIs. This is the diff that 2024oct24 could not support, because that version published no
   `intermediate/` tree.
4. Inspect the compendia (or the published `duckdb/` Edge table, where available) to see which
   clique each key CURIE lands in and whether that clique contains the bridge RxCUIs (e.g.
   `SELECT clique_leader, curie FROM Edge WHERE curie IN ('CHEBI:3395', 'RXCUI:203437', …)`).
   A SmallMolecule↔MolecularMixture split or a Drug reclassification of a bridge RxCUI is the likely
   culprit.
5. Decide conflation-level vs compendium-level, and only then write the fix plus a pinned regression
   test in `tests/createcompendia/test_drugchemical.py` (a fixture-driven `build_conflation()` run
   asserting the expected Carbidopa clique membership). If the fix needs a curated edge, add the
   pair to `input_data/manual_concords/drugchemical.tsv`.

## Reproducing the conflation locally (when needed)

You do not need to rebuild the chemical compendia (a 512G / 6h rule) or download any source files to
re-run just the conflation. Download these from a full-output version under
`https://stars.renci.org/var/babel_outputs/<version>/` and place them at the matching local paths:

- `intermediate/drugchemical/concords/{RXNORM,UMLS,PUBCHEM_RXNORM}` and their `metadata-*.yaml`
- `compendia/Drug.txt` and the other chemical compendia (`config.yaml` `chemical_outputs`)
- `icRDF.tsv` (top level)

`input_data/manual_concords/drugchemical.tsv` is already in the repo. Then run the
`drugchemical_conflation` rule. Caveat: the rule loads all chemical compendia into Python dicts and
has no SLURM `mem=` override (defaults to 64G); on a full build it can exceed that, so use a
largemem node or trimmed fixture compendia. Note again that `2024oct24` did not publish
`intermediate/`, so the concords can only be downloaded for versions that did (e.g. `2025sep1`).

A reminder lives in `CLAUDE.md`: use `https://stars.renci.org/var/babel_outputs/` (full identifiers)
for debugging, **not** `https://stars.renci.org/var/babel/` (externally-shareable subset only).

## TODO / future improvements

- Land PR #704 (intermediate concord/identifier Parquet export) and improve it so the Carbidopa
  diff above is a single query; see the TODOs filed on that PR.
- Instrument `build_rxnorm_relationships()`'s multi-ingredient and one-to-one relationship drops
  with their own exclusion report (separate rule output) so concord-build-time drops are also
  retained.
- Fix the duplicate-CURIE write bug (a conflation array should not list `CHEBI:39585` twice).
- Add the pinned Carbidopa regression test once the root cause and fix are confirmed.
