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

This is measured with [`babel-clique-diff`](../../tools/CliqueDiff.md) comparing two builds of
`Disease.txt`/`PhenotypicFeature.txt` from the **identical, already-pulled** disease/phenotype
concords and ids (`data/branch-mp/intermediate/disease`, one UberGraph pull): a `before` build with
`split_mutually_exclusive_cliques()` disabled (HP/MP overlap allowed, matching pre-PR behavior) and
an `after` build with it enabled (this PR's actual disjointness behavior). See
[`disjointness/clique-diff.csv`](disjointness/clique-diff.csv) and
[`disjointness/clique-diff.summary.json`](disjointness/clique-diff.summary.json) (the `about`
block records both build labels). The complementary "what does the MP *source* add" view is the
[`impact-report.md`](impact-report.md).

**Why this baseline, not a `main`-vs-branch diff.** An earlier version of this section compared a
`main` build (no MP at all) against this branch, built the same day from the same cached
`babel_downloads` — but their UberGraph-derived HP and MONDO concords were pulled at different
times, and `ubergraph.build_sets()` writes each subject's xref targets by iterating a Python `set`
whose order is randomized per process. `glom()` resolves a `unique_prefixes` conflict by keeping
whichever bridge it processes **first**, so two builds from the same underlying data can pick
different winners. Of that comparison's 93 change rows, 33 (from 21 before-cliques containing no MP
identifier at all) turned out to be this ordering noise rather than the disjointness change under
test — confirmed by re-glomming that branch's own inputs with the MP source fully excluded, which
reproduced all 33. General order-sensitivity is tracked in
[#894](https://github.com/NCATSTranslator/Babel/issues/894); PR
[#901](https://github.com/NCATSTranslator/Babel/pull/901) proposes sorting `build_sets()`'s output
to fix it at the source, but is deliberately not part of this branch — it changes contested-xref
tie-breaking build-wide, which is a broader, separately-measured effect.

This page sidesteps that problem instead of waiting on #901: holding the concords fixed and only
toggling the split means both builds share one glom state right up until
`split_mutually_exclusive_cliques()` runs, so the diff **cannot** contain ordering noise by
construction — verified below (zero non-`kept` rows lack an MP identifier). The trade-off is that,
unlike the `main`-vs-branch comparison, this baseline already contains MP (via the same intermediate
files), so it cannot show the ~14,750 wholly-new MP-only cliques the source itself adds — that
number lives in [`impact-report.md`](impact-report.md) instead (see the note at the end of this
section).

Headline counts:

- **`PhenotypicFeature.txt`: 75,275 → 75,469 cliques (+194, +0.26%).** Every added clique is an MP
  identifier peeled out of an HP-bearing clique it had been merged into.
- **`Disease.txt`: 365,466 → 365,466 (count unchanged).** The split only ever moves an MP member to
  its own (possibly new) `PhenotypicFeature.txt` clique; it never creates or deletes a `Disease.txt`
  clique.

After enforcement, **zero cliques in `Disease.txt` or `PhenotypicFeature.txt` contain both an HP
and an MP identifier.** The 390 per-clique change rows are exactly the disjointness split's effect
— every non-`kept` row involves an MP identifier (verified programmatically against the CSV):

- `PhenotypicFeature.txt`: 106 MP members `regrouped` into their own cliques. Example:
  [`HP:0000048`](http://purl.obolibrary.org/obo/HP_0000048) "Bifid scrotum" released
  [`MP:0009203`](http://purl.obolibrary.org/obo/MP_0009203) "external male genitalia hypoplasia",
  which became its own MP clique.
- 88 `Disease.txt` cliques released an MP member that `moved` to `PhenotypicFeature.txt`. Example:
  [`MONDO:0000811`](http://purl.obolibrary.org/obo/MONDO_0000811) "anomalous left coronary artery
  from the pulmonary artery" kept its human members and released
  [`MP:0010475`](http://purl.obolibrary.org/obo/MP_0010475) "anomalous pulmonary origin of left
  coronary artery".
- 1 `dropped`: the stray untypeable [`MP:0005555`](http://purl.obolibrary.org/obo/MP_0005555)
  described above.

Note — where the "14K" lives. This clique-diff's `before` already contains MP (both builds read the
same `data/branch-mp/intermediate/disease` concords/ids), so it cannot see MP's ~14,750 wholly-new
cliques — only the split's redistribution of MP members that were merged into HP-bearing cliques.
The impact report's `before` instead excludes the MP source entirely, so it lists those ~14,750
additions directly as new-clique rows. Read the two artifacts together: the impact report answers
"what does adding MP do", this page answers "what does keeping MP disjoint from HP do", and neither
number substitutes for the other.

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
- [#900](https://github.com/NCATSTranslator/Babel/issues/900) — the bad MONDO `exactMatch`
  (`MONDO:0003425` → `SNOMEDCT:78097002`) worked around in `input_data/mondo_badxrefs.txt`, to be
  reported upstream to MONDO.
- [#894](https://github.com/NCATSTranslator/Babel/issues/894) /
  [#901](https://github.com/NCATSTranslator/Babel/pull/901) — `build_sets()`'s concord-write
  order nondeterminism that motivated switching this page's baseline to a same-concords
  overlap-allowed-vs-disjoint diff instead of a `main`-vs-branch diff.
- [#742](https://github.com/NCATSTranslator/Babel/pull/742) /
  [#781](https://github.com/NCATSTranslator/Babel/pull/781) — the source-impact / EMAPA
  infrastructure this builds on.
