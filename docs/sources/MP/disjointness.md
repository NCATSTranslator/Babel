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

- 14,750 pure-new MP-only cliques and **no** expanded existing cliques — see the regenerated
  source-impact report. (Before EFO→MP xrefs were filtered at the EFO source, 15 of these were
  instead EFO/MONDO cliques that MP expanded; dropping those untrusted xrefs turns them into
  pure-new MP-only cliques. See "Keeping MP disjoint from EFO" below.)

Split (existing cliques that lost their MP members):

- In `PhenotypicFeature.txt`, 109 MP members were `regrouped` out of 109 HP-bearing cliques
  into their own cliques (the after-build has 199 more PhenotypicFeature cliques as a result:
  109 regrouped plus the 90 moved out of `Disease.txt` below). Example:
  [`HP:0000048`](http://purl.obolibrary.org/obo/HP_0000048) "Bifid scrotum" lost
  [`MP:0009203`](http://purl.obolibrary.org/obo/MP_0009203) "external male genitalia
  hypoplasia", which became its own MP clique.

Moved (MP retyped out of `Disease.txt`):

- 90 MP members that had merged into HP-bearing *disease* cliques moved from `Disease.txt` to
  `PhenotypicFeature.txt` once peeled off. Example:
  [`MONDO:0000811`](http://purl.obolibrary.org/obo/MONDO_0000811) "anomalous left coronary
  artery from the pulmonary artery" kept its 10 human members (incl. an HP) and released
  [`MP:0010475`](http://purl.obolibrary.org/obo/MP_0010475) "anomalous pulmonary origin of
  left coronary artery".

Deleted (dropped):

- 1 member — the stray untypeable [`MP:0005555`](http://purl.obolibrary.org/obo/MP_0005555)
  described above.

## Keeping MP disjoint from EFO (filtered at the EFO source)

MP is also kept out of EFO cliques, but by a different mechanism. The source-impact report
surfaced ~15 cliques where an EFO phenotype term and an MP term co-occurred, every one of them
created by a **direct `oboInOwl:hasDbXref` row asserted by EFO** in
`intermediate/disease/concords/EFO` (see the impact report's `new-xrefs.tsv`).

EFO is a species-agnostic / human-leaning ontology, so an EFO term xref'd to an MP term is
ambiguous: it may denote a human-specific phenotype (which, like HP, must stay disjoint from MP)
or a genuinely mammalian one. It is *not impossible* for EFO to carry an MP-specific identifier,
but there is no reliable signal to distinguish those cases. Since no individual EFO→MP xref can
be trusted, Babel drops them all **at the EFO source**: `efo.make_concords()` is called with
`excluded_target_prefixes=[MP]` (the constant `diseasephenotype.EFO_EXCLUDED_XREF_PREFIXES`), so
`concords/EFO` never emits an EFO↔MP link (neither `skos:exactMatch` nor `oboInOwl:hasDbXref`).

### Why source-filtering rather than another post-glom split

The HP/MP problem needed a post-glom split because HP and MP merge *transitively* through shared
MESH/SNOMED/MONDO identifiers, so dropping a concord alone could not guarantee disjointness. The
EFO/MP situation is narrower: MP's own UberGraph xrefs point at anatomy/GO/cell/Fyler targets
outside the disease identifier space, so the direct EFO→MP xref is effectively the only bridge.
Removing it at the source is therefore sufficient in practice, and it avoids overstating the
policy — a broad `[EFO, MP]` split would assert "EFO and MP are never equivalent," which is
stronger than we can justify given EFO may hold legitimately-mammalian terms we cannot identify.
Dropping the untrusted direct evidence is the more honest expression of "we don't trust these
xrefs."

This removes *direct* evidence only. The regenerated source-impact report is the check that it is
enough: after filtering, no EFO-led `expanded` rows remain in `modified-cliques.csv` and no EFO→MP
rows remain in `new-xrefs.tsv`. If a future EFO/MP release introduced a transitive bridge (a shared
MESH/UMLS/SNOMED identifier), it would reappear there, at which point adding `[EFO, MP]` to
`MUTUALLY_EXCLUSIVE_PREFIX_GROUPS` is the backstop. (HP→MP direct xrefs are unaffected by this
filter and continue to be handled by the `[HP, MP]` split above.)

## Related work

- [#790](https://github.com/NCATSTranslator/Babel/pull/790) (`add-mpo`) — the original MP
  ingestion with HP/MP overlap allowed; preserved as the fallback.
- [#300](https://github.com/NCATSTranslator/Babel/pull/300) — the earlier
  `add-mammal-phenotype-ontology` attempt and its SSSOM MP↔HP/NCIT bridging questions.
- [#885](https://github.com/NCATSTranslator/Babel/pull/885) — the `babel-clique-diff` tool used
  to measure the impact above (split out of the original combined #883).
- [#888](https://github.com/NCATSTranslator/Babel/pull/888) (`fix-mondo-close-guard`) — the
  deferred MONDO close-match-guard fix (keying glom's `close=` map on the object rather than the
  predicate), also split out of #883. The numbers on this page were measured against the current
  predicate-keyed, effectively no-op close behavior that this branch preserves, so #888 activating
  the guard and changing disease merging will not contradict them.
- [#742](https://github.com/NCATSTranslator/Babel/pull/742) /
  [#781](https://github.com/NCATSTranslator/Babel/pull/781) — the source-impact / EMAPA
  infrastructure this builds on.
