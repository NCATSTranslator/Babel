# Clique diff: anatomy before and after adding EMAPA

The [source-impact report](./impact-report.md) models what *adding* EMAPA contributes, but by
construction it only walks after-cliques that contain an EMAPA CURIE. It therefore cannot report
before-cliques that split, lose members, or disappear (see
[#895](https://github.com/NCATSTranslator/Babel/issues/895)). This page records a full
build-vs-build [`babel-clique-diff`](../../tools/README.md) that closes that gap.

Artifacts in [`clique-diff/`](./clique-diff/): `clique-diff.csv` (262 change rows) and
`clique-diff.summary.json`.

## What was compared

Both sides were built from the **same cached intermediates**
(`babel_outputs/intermediate/anatomy/`), changing only the code and configuration under test:

- **before** — `anatomy` built at `main`. Its `config.yaml` names no EMAPA anywhere:
  `anatomy_ids` and `anatomy_concords` exclude it, and `anatomy_unique_prefixes` is
  `[UBERON, GO]`.
- **after** — `anatomy` built at `add-emapa-actual`, which adds the EMAPA ids file, the (empty)
  EMAPA concord, and `EMAPA` to `anatomy_unique_prefixes`.

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
| after | 179,006 | 8,094 | 8,094 |

Note the before row: 4,203 cliques hold 4,343 EMAPA CURIEs, so some cliques held **more than one**.
After, the counts are equal — every clique holds at most one EMAPA identifier. That is
`anatomy_unique_prefixes` doing its job, and it is the source of most of the churn below.

## Summary of changes

262 change rows across 122 changed before-cliques.

| destination_kind | rows | meaning |
|---|---|---|
| `kept` | 122 | 492 members stayed under the same leader |
| `moved` | 71 | retyped into a different compendium file |
| `regrouped` | 67 | members redistributed to a different leader (the split case) |
| `dropped` | 2 | gone from every compared compendium |

Clique counts per compendium:

| compendium | before | after | diff |
|---|---|---|---|
| `AnatomicalEntity.txt` | 145,743 | 147,638 | +1,895 |
| `Cell.txt` | 9,197 | 9,197 | 0 |
| `CellularComponent.txt` | 9,469 | 9,469 | 0 |
| `GrossAnatomicalStructure.txt` | 10,706 | 12,702 | +1,996 |

The +1,895 and +1,996 sum to **+3,891**, exactly the pure-new clique count in the source-impact
report. `Cell` and `CellularComponent` are untouched, as expected: EMAPA is not among the Biolink
`id_prefixes` for either class, so no EMAPA CURIE can reach them.

## The 71 moved members

16 members moved `AnatomicalEntity → GrossAnatomicalStructure` and 55 moved the other way. These
are retypings, not restructurings. `classify_anatomy_clique()` trusts source ontologies in the
order GO, CL, UBERON, EMAPA; adding EMAPA to that precedence, and typing its organ/tissue
descendants as `biolink:GrossAnatomicalStructure`, reassigns the type of cliques whose only typed
member is now an EMAPA term.

## The 67 regrouped members

These are cliques that held two or more EMAPA CURIEs before, and are split apart now that `EMAPA`
is a unique prefix. 116 UBERON terms cross-reference more than one EMAPA term, so this was
expected; `glom()` refuses any merge whose union would hold two identifiers sharing a
`unique_prefixes` prefix.

## The 2 dropped members — both are non-terms

Only two identifiers disappear from the anatomy compendia entirely, and both are EMAPA CURIEs:

| before leader | before leader label | dropped CURIE |
|---|---|---|
| [`UBERON:0005185`](http://purl.obolibrary.org/obo/UBERON_0005185) | "renal medulla collecting duct" | `EMAPA:35459` |
| [`UBERON:0007213`](http://purl.obolibrary.org/obo/UBERON_0007213) | "mesenchyme derived from head neural crest" | `EMAPA:16271` |

The mechanism is the same in both cases. `UBERON:0005185` cross-references *two* EMAPA terms,
[`EMAPA:28061`](http://purl.obolibrary.org/obo/EMAPA_28061) "medullary collecting duct" and
`EMAPA:35459`. Before, both sat in one clique. After, `anatomy_unique_prefixes` forbids that, so
only one can stay — and the one that stays is the one present in the EMAPA ids file. `EMAPA:35459`
is not in the ids file, so there is no ids row to seed a clique of its own, and it drops out
entirely. `UBERON:0007213` behaves identically with
[`EMAPA:16169`](http://purl.obolibrary.org/obo/EMAPA_16169) "head mesenchyme derived from neural
crest" surviving and `EMAPA:16271` dropping.

Neither dropped CURIE is a real EMAPA term:

- `EMAPA:35459` carries `owl:deprecated true` in UberGraph and has no `rdfs:label`.
- `EMAPA:16271` has no `rdfs:label` at all — a dangling xref target.

Both are absent from `babel_downloads/EMAPA/labels`, which is why `write_emapa_ids()` never
collected them: they are not reachable by `part_of` or `subClassOf` from
[`EMAPA:0`](http://purl.obolibrary.org/obo/EMAPA_0) "anatomical structure" because they are not
live terms in the ontology.

So this PR **removes two obsolete identifiers** that `main` was carrying purely because a stale
UBERON xref pointed at them. That is a correctness improvement, not a regression.

## Reproducing

```bash
# after: build anatomy on this branch
uv run snakemake -c all anatomy

# before: run main's build_compendia over the *same* intermediates, output redirected
git worktree add --detach /tmp/main-wt main
# in the worktree, set config download/intermediate dirs to this repo and
# output_directory to a scratch dir, then call anatomy.build_compendia(...)

uv run babel-clique-diff \
    --before /path/to/before/compendia --after babel_outputs/compendia \
    --files AnatomicalEntity.txt Cell.txt CellularComponent.txt GrossAnatomicalStructure.txt \
    --before-label "anatomy built at main (no EMAPA source)" \
    --after-label  "anatomy built at add-emapa-actual" \
    --note "Isolates adding EMAPA as an anatomy source, from identical cached intermediates" \
    --out-csv  docs/sources/EMAPA/clique-diff/clique-diff.csv \
    --out-json docs/sources/EMAPA/clique-diff/clique-diff.summary.json
```
