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

This is measured as the **overall effect of this PR on Babel**: a
[`babel-clique-diff`](../../tools/CliqueDiff.md) of a `main` build (Babel *without* this PR — no MP)
against this branch (MP added, kept disjoint). Both sides were built the same day from the same
cached `babel_downloads`, so the UberGraph-derived concords match and the only difference is this
PR's code. See [`disjointness/clique-diff.csv`](disjointness/clique-diff.csv) and
[`disjointness/clique-diff.summary.json`](disjointness/clique-diff.summary.json) (the `about`
block records both build labels). The complementary "what does the MP *source* add" view is the
[`impact-report.md`](impact-report.md).

Headline counts:

- **`PhenotypicFeature.txt`: 60,718 → 75,469 cliques (+14,751, +24%).** The gain is dominated by
  the 14,750 wholly new MP-only phenotype cliques this PR adds. Because those cliques have no
  `main` counterpart, they surface **only** as the `clique_count.diff`, never as per-clique change
  rows — the diff iterates *before*-cliques, so a brand-new after-clique is invisible to it. This
  is exactly why the change-row counts below look small next to the impact report's ~14K new
  cliques: the two artifacts count different things (see the note at the end of this section).
- **`Disease.txt`: 365,466 → 365,466 (count unchanged).** MP is a phenotype ontology: it
  contributes no new disease cliques, and after the split it removes none.

After enforcement, **zero cliques in `Disease.txt` or `PhenotypicFeature.txt` contain both an HP
and an MP identifier.** The 93 per-clique change rows fall into two groups.

Disjointness — MP peeled out of cliques `main` had merged it into (via *unfiltered* HP→MP / EFO→MP
xrefs that this PR removes):

- `PhenotypicFeature.txt`: 26 MP members `regrouped` into their own cliques. Example: on `main`,
  [`EFO:0005414`](http://www.ebi.ac.uk/efo/EFO_0005414) "airway hyperresponsiveness" absorbed
  [`MP:0001952`](http://purl.obolibrary.org/obo/MP_0001952) "increased airway responsiveness"; this
  PR splits them.
- 8 `Disease.txt` cliques released an MP member that `moved` to `PhenotypicFeature.txt`. Example:
  [`MONDO:0005711`](http://purl.obolibrary.org/obo/MONDO_0005711) "congenital diaphragmatic hernia"
  released [`MP:0003924`](http://purl.obolibrary.org/obo/MP_0003924) "diaphragmatic hernia".
- 1 `dropped`: the stray untypeable [`MP:0005555`](http://purl.obolibrary.org/obo/MP_0005555)
  described above.

Contested-xref reshuffle — a side effect of MP's *presence* in the build, not of MP merging with
disease:

- 7 `Disease.txt` cliques (96 members, **no MP involved**) `regrouped`. These are cross-references
  shared by two near-synonymous MONDO cliques that `unique_prefixes` keeps separate (two MONDO
  identifiers may not share a clique); MP's presence in the build shifts which of the two claims
  the shared member. Example:
  [`MONDO:0004555`](http://purl.obolibrary.org/obo/MONDO_0004555) "kidney angiomyolipoma" and
  [`MONDO:0002603`](http://purl.obolibrary.org/obo/MONDO_0002603) "angiomyolipoma" swap five shared
  members (an HP, NCIT, SNOMEDCT, UMLS, MEDDRA). This redistributes members between existing
  disease cliques but creates and deletes none, which is why `Disease.txt`'s clique count is
  unchanged. Verified incidental rather than a real MP relationship: MP is not a member of any of
  these cliques and none of the swapped members appears in MP's concord; the effect is
  deterministic and independent of MP's position in `disease_concords` (moving MP to the end of
  the list produces a byte-identical diff), so it is a stable tie-break shift, not run-to-run
  noise. This is a general `glom()` `unique_prefixes` behavior (a contested cross-reference's
  winning clique is sensitive to the input set), not specific to MP; tracked in
  [#894](https://github.com/NCATSTranslator/Babel/issues/894).

Note — where the "14K" lives in each artifact. Both this clique-diff and the impact report use a
"before" that lacks MP (the impact report *excludes the MP source*; the `main` build simply never
ingested MP), so both agree that this PR adds ~14,750 MP phenotype cliques. They just report it in
different places: the impact report lists them as ~14,750 new-clique rows, whereas this clique-diff
— which only emits rows for *before*-cliques that changed — records them solely as the
`PhenotypicFeature.txt` `clique_count.diff` of +14,751. (An earlier version of this page instead
diffed an *overlap-allowed* build that already contained MP against the disjoint build; that
"before" already had the 14,750 cliques, so their count barely moved and the additions were
invisible — the confusion this baseline choice now avoids.)

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
