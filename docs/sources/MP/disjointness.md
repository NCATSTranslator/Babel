# Keeping MP disjoint from HP

At the request of the disease/phenotype SMEs, Babel keeps Human Phenotype (HP) and
Mammalian Phenotype (MP) identifiers **completely distinct**: no clique may contain both an
HP and an MP identifier. Human phenotypes and mouse phenotypes behave differently enough
that conflating them is undesirable, so a "human phenotype" clique must never absorb a
mouse-phenotype identifier (and vice versa).

MP is still allowed to merge with non-HP disease identifiers (MONDO, MESH, …); only HP
triggers a separation. The historical "allow overlap" behavior is preserved on the
[`add-mpo`](https://github.com/NCATSTranslator/Babel/pull/790) branch as a fallback in case
this decision is revisited.

## Why `unique_prefixes` is not enough

The natural first guess — add MP to `glom()`'s `unique_prefixes` — does **not** work.
`unique_prefixes` only forbids *two identifiers sharing the same prefix* in one clique (two
HPs, two MPs); it does nothing to stop an HP and an MP from co-occurring. Dropping MP's own
xref concord is also insufficient: the HP concord emits direct `HP→MP` xref rows and the EFO
concord direct `EFO→MP` rows, and HP and MP merge transitively through shared MESH/SNOMED/MONDO
identifiers regardless.

## How it works: a post-glom split

After glom, `diseasephenotype.split_mutually_exclusive_cliques()` enforces the constant
`MUTUALLY_EXCLUSIVE_PREFIX_GROUPS = [[HP, MP]]`: any clique holding both an HP and an MP
identifier is split so that HP (and every non-group member — MONDO, MESH, …) stays in the
clique while the MP identifiers are peeled into a clique of their own. HP is listed first, so
the existing human/disease clique is preserved and MP is the part that splits off.

The split is the final step of `compute_cliques_for_impact_report()`, which is the single
code path shared by the real build (`build_compendium`) and the source-impact report, so both
see identical, already-split cliques. Mirrors the type-driven split precedent in
`src/createcompendia/chemicals.py`.

One downstream effect: the split can strand a lone identifier that appears in a concord but
in no ids file (here, exactly one obsolete MP,
[`MP:0005555`](http://purl.obolibrary.org/obo/MP_0005555)). Such a clique has no member with
a declared Biolink type, so `create_typed_sets()` now drops it with a warning instead of
aborting the build.

## Impact

Measured by [`babel-clique-diff`](../../tools/README.md) comparing the overlap-allowed build
(before) against the disjoint build (after); see
[`disjointness/clique-diff.csv`](disjointness/clique-diff.csv) and
[`disjointness/clique-diff.summary.json`](disjointness/clique-diff.summary.json). The
"added" view (pure-new MP cliques) is in the regenerated
[`impact-report.md`](impact-report.md).

After enforcement, **zero cliques in `Disease.txt` or `PhenotypicFeature.txt` contain both an
HP and an MP identifier** (down from 110+ mixed cliques in `PhenotypicFeature.txt` alone).

Added (new MP cliques):

- 14,641 pure-new MP-only cliques, plus 15 existing non-HP phenotype cliques that MP still
  expands (e.g. EFO/MONDO partners) — see the regenerated source-impact report.

Split (existing cliques that lost their MP members):

- In `PhenotypicFeature.txt`, 114 MP members were `regrouped` out of 109 HP-bearing cliques
  into their own cliques (the after-build has 199 more PhenotypicFeature cliques as a result).
  Example: [`HP:0000048`](http://purl.obolibrary.org/obo/HP_0000048) "Bifid scrotum" lost
  [`MP:0009203`](http://purl.obolibrary.org/obo/MP_0009203) "external male genitalia
  hypoplasia", which became its own MP clique.

Moved (MP retyped out of `Disease.txt`):

- 94 MP members that had merged into HP-bearing *disease* cliques moved from `Disease.txt` to
  `PhenotypicFeature.txt` once peeled off. Example:
  [`MONDO:0000811`](http://purl.obolibrary.org/obo/MONDO_0000811) "anomalous left coronary
  artery from the pulmonary artery" kept its 10 human members (incl. an HP) and released
  [`MP:0010475`](http://purl.obolibrary.org/obo/MP_0010475) "anomalous pulmonary origin of
  left coronary artery".

Deleted (dropped):

- 1 member — the stray untypeable [`MP:0005555`](http://purl.obolibrary.org/obo/MP_0005555)
  described above.

## Related work

- [#790](https://github.com/NCATSTranslator/Babel/pull/790) (`add-mpo`) — the original MP
  ingestion with HP/MP overlap allowed; preserved as the fallback.
- [#300](https://github.com/NCATSTranslator/Babel/pull/300) — the earlier
  `add-mammal-phenotype-ontology` attempt and its SSSOM MP↔HP/NCIT bridging questions.
- [#883](https://github.com/NCATSTranslator/Babel/pull/883) — the original home of the
  `babel-clique-diff` tool (now its own PR) and the deferred MONDO close-match-guard fix.
  These numbers were measured against the current (predicate-keyed, effectively no-op) close
  behavior, so a later close-match-guard fix changing disease merging will not contradict them.
- [#742](https://github.com/NCATSTranslator/Babel/pull/742) /
  [#781](https://github.com/NCATSTranslator/Babel/pull/781) — the source-impact / EMAPA
  infrastructure this builds on.
