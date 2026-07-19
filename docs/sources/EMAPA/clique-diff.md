# Clique diff: anatomy before and after adding EMAPA

The [source-impact report](./impact-report.md) models what *adding* EMAPA contributes, but by
construction it only walks after-cliques that contain an EMAPA CURIE. It therefore cannot report
before-cliques that split, lose members, or disappear (see
[#895](https://github.com/NCATSTranslator/Babel/issues/895)). This page records a full
build-vs-build [`babel-clique-diff`](../../tools/CliqueDiff.md) that closes that gap.

Artifacts in [`clique-diff/`](./clique-diff/): `clique-diff.csv` (262 change rows) and
`clique-diff.summary.json`.

## What was compared

Both sides were built from the **same cached intermediates**
(`babel_outputs/intermediate/anatomy/`), on the same commit, changing only the configuration under
test:

- **before** — `anatomy` with `EMAPA` removed from `anatomy_prefixes`, `anatomy_ids`,
  `anatomy_concords` and `anatomy_unique_prefixes` (which is then `[UBERON, GO]`).
- **after** — `anatomy` as this branch ships it: the EMAPA ids file, the (empty) EMAPA concord,
  and `EMAPA` in `anatomy_unique_prefixes`.

Toggling configuration rather than checking out the pre-EMAPA branch matters, because the
deterministic `build_sets()` ordering fix
([#945](https://github.com/NCATSTranslator/Babel/issues/945)) must be present on **both** sides.
Built against a branch lacking it, the before side would draw its `unique_prefixes` tie-breaks at
random and the diff would not be reproducible. As a cross-check, the before side's 175,115 cliques
match the "pre-existing cliques" count the source-impact report computes independently.

Because both runs read the same concord files, no cross-reference goes missing between them. Every
difference below is a decision made *inside* a run.

## EMAPA was already in the compendia before this PR

This is the fact that makes the rest of the diff legible. EMAPA asserts no outgoing xrefs of its
own (see [mappings.md](./mappings.md)), but UBERON asserts 4,356 `hasDbXref` triples pointing *at*
EMAPA. Those rows live in the **UBERON** concord, so EMAPA CURIEs were already being promoted into
anatomy cliques long before EMAPA existed as a source:

| | cliques | cliques holding an EMAPA CURIE | distinct EMAPA CURIEs |
|---|---|---|---|
| before | 175,115 | 4,203 | 4,343 |
| after | 179,005 | 8,093 | 8,093 |

Note the before row: 4,203 cliques hold 4,343 EMAPA CURIEs, so some cliques held **more than one**.
After, the counts are equal — every clique holds at most one EMAPA identifier. That is
`anatomy_unique_prefixes` doing its job, and it is the source of most of the churn below.

## Summary of changes

262 change rows across 122 changed before-cliques.

| destination_kind | rows | members | meaning |
|---|---|---|---|
| `kept` | 122 | 492 | stayed under the same leader |
| `regrouped` | 70 | 70 | members redistributed to a different leader (the split case) |
| `moved` | 67 | 67 | retyped into a different compendium file |
| `dropped` | 3 | 3 | gone from every compared compendium |

Clique counts per compendium:

| compendium | before | after | diff |
|---|---|---|---|
| `AnatomicalEntity.txt` | 145,743 | 147,632 | +1,889 |
| `Cell.txt` | 9,197 | 9,197 | 0 |
| `CellularComponent.txt` | 9,469 | 9,469 | 0 |
| `GrossAnatomicalStructure.txt` | 10,706 | 12,707 | +2,001 |

The +1,889 and +2,001 sum to **+3,890**, exactly the pure-new clique count in the source-impact
report. `Cell` and `CellularComponent` are untouched, as expected: EMAPA is not among the Biolink
`id_prefixes` for either class, so no EMAPA CURIE can reach them.

## The 67 moved members

50 members moved `GrossAnatomicalStructure → AnatomicalEntity` and 17 moved the other way. These
are retypings, not restructurings. `classify_anatomy_clique()` trusts source ontologies in the
order GO, CL, UBERON, EMAPA; adding EMAPA to that precedence, and typing its organ/tissue
descendants as `biolink:GrossAnatomicalStructure`, reassigns the type of cliques whose only typed
member is now an EMAPA term.

## The 70 regrouped members

These are cliques that held two or more EMAPA CURIEs before, and are split apart now that `EMAPA`
is a unique prefix. 122 UBERON terms cross-reference more than one EMAPA term, so this was
expected; `glom()` refuses any merge whose union would hold two identifiers sharing a
`unique_prefixes` prefix.

## The 3 dropped members — all are non-terms

Three identifiers disappear from the anatomy compendia entirely, and all three are EMAPA CURIEs
with no `rdfs:label`:

| before leader | before leader label | dropped CURIE | surviving CURIE |
|---|---|---|---|
| [`UBERON:0002490`](http://purl.obolibrary.org/obo/UBERON_0002490) | "frontal suture" | `EMAPA:35358` | [`EMAPA:19226`](http://purl.obolibrary.org/obo/EMAPA_19226) "frontal suture" |
| [`UBERON:0005185`](http://purl.obolibrary.org/obo/UBERON_0005185) | "renal medulla collecting duct" | `EMAPA:35459` | [`EMAPA:28061`](http://purl.obolibrary.org/obo/EMAPA_28061) "medullary collecting duct" |
| [`UBERON:0007213`](http://purl.obolibrary.org/obo/UBERON_0007213) | "mesenchyme derived from head neural crest" | `EMAPA:16271` | [`EMAPA:16169`](http://purl.obolibrary.org/obo/EMAPA_16169) "head mesenchyme derived from neural crest" |

The mechanism is the same in all three cases. Each UBERON term cross-references *two* EMAPA terms,
and before the change both sat in one clique. After, `anatomy_unique_prefixes` forbids that, so
only one can stay — and the one that stays is the one present in the EMAPA ids file. The dropped
CURIE is in no ids file, so there is no row to seed a clique of its own, and it disappears.

None of the three is a live EMAPA term, and for two of them the ontology explicitly says so:

| CURIE | `owl:deprecated` | [`IAO:0100001`](http://purl.obolibrary.org/obo/IAO_0100001) "term replaced by" |
|---|---|---|
| `EMAPA:35358` | `true` | `EMAPA:19226` — the CURIE that survives |
| `EMAPA:35459` | `true` | `EMAPA:28061` — the CURIE that survives |
| `EMAPA:16271` | *not set* | *none* |

For `EMAPA:35358` and `EMAPA:35459`, EMAPA itself records the term as obsolete with obsolescence
reason [`IAO:0000227`](http://purl.obolibrary.org/obo/IAO_0000227) "terms merged", and names as its
replacement exactly the CURIE Babel keeps. The outcome is the one the ontology asks for.

`EMAPA:16271` is a different case: it carries **no axioms at all** — no `owl:deprecated`, no label,
no replacement. It is a dangling xref target, a CURIE UBERON references that never existed as an
EMAPA term. A deprecation-based rule would not identify it; absence from the ids file does. See
[#911](https://github.com/NCATSTranslator/Babel/issues/911).

All three are absent from `babel_downloads/EMAPA/labels`, which is why `write_emapa_ids()` never
collected them: they are not reachable by `part_of` or `subClassOf` from
[`EMAPA:0`](http://purl.obolibrary.org/obo/EMAPA_0) "anatomical structure" because they are not
live terms in the ontology.

So this PR **removes three obsolete identifiers** that the build was carrying purely because a
stale UBERON xref pointed at them. That is a correctness improvement, not a regression.

### Which CURIE wins is not yet decided on merit

Worth knowing when reading the table above: `glom()` keeps whichever competing CURIE it encounters
**first**, and since `build_sets()` now sorts its output, that is the lexicographically smallest
one. In all three cases the live term happens to sort below the obsolete one
(`19226 < 35358`, `28061 < 35459`, `16169 < 16271`), so the right term wins — but that is luck, not
policy. A future release pairing a live term with an obsolete one that sorts lower would strand the
live term instead, stably and silently.
[#945](https://github.com/NCATSTranslator/Babel/issues/945) tracks deciding the tie-break on
validity rather than sort order.

## Reproducing

Both sides come from one set of cached intermediates; only the compendium-building rules re-run,
so the second build takes minutes and needs no network.

```bash
# after: build anatomy as this branch ships it
uv run snakemake -c all anatomy
mkdir -p data/clique-diff/after && cp babel_outputs/compendia/*.txt data/clique-diff/after/

# before: remove EMAPA from anatomy_prefixes / anatomy_ids / anatomy_concords /
# anatomy_unique_prefixes in config.yaml, then rebuild only the compendia.
# Delete the target sentinel too -- without it Snakemake reports "Nothing to be done"
# and silently rebuilds nothing (see docs/RunningBabel.md, "Common build issues").
rm -f babel_outputs/reports/anatomy_done babel_outputs/compendia/*.txt
uv run snakemake -c all anatomy --rerun-triggers mtime
mkdir -p data/clique-diff/before && cp babel_outputs/compendia/*.txt data/clique-diff/before/
git checkout config.yaml

uv run babel-clique-diff \
    --before data/clique-diff/before --after data/clique-diff/after \
    --files AnatomicalEntity.txt Cell.txt CellularComponent.txt GrossAnatomicalStructure.txt \
    --before-label "anatomy at babel-1.18 + #781 with EMAPA removed from anatomy_prefixes/ids/concords/unique_prefixes" \
    --after-label  "anatomy at babel-1.18 + #781 (EMAPA ids + concord + anatomy_unique_prefixes)" \
    --note "Isolates adding EMAPA as an anatomy source. Both sides built from identical cached intermediates with the deterministic build_sets() ordering fix applied, so the only variable is EMAPA itself." \
    --out-csv  docs/sources/EMAPA/clique-diff/clique-diff.csv \
    --out-json docs/sources/EMAPA/clique-diff/clique-diff.summary.json
```

`--rerun-triggers mtime` keeps a `config.yaml` edit from invalidating the expensive
UberGraph-backed ids and concord rules, which must stay byte-identical across the two sides.
