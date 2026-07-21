# Clique diff: anatomy before and after adding EMAPA

The [source-impact report](./impact-report.md) models what *adding* EMAPA contributes, but by
construction it only walks after-cliques that contain an EMAPA CURIE. It therefore cannot report
before-cliques that split, lose members, or disappear (see
[#895](https://github.com/NCATSTranslator/Babel/issues/895)). This page records a full
build-vs-build [`babel-clique-diff`](../../tools/CliqueDiff.md) that closes that gap.

Artifacts in [`clique-diff/`](./clique-diff/): `clique-diff.csv` (empty apart from its header, since
there are no change rows) and `clique-diff.summary.json`.

## Headline: adding EMAPA is purely additive

**No before-clique changes in any way.** Nothing splits, nothing is retyped, nothing loses a member,
and no identifier is dropped from any of the four anatomy compendia. Every difference between the
two sides is a brand-new clique made only of EMAPA identifiers.

| destination_kind | rows | meaning |
|---|---|---|
| `regrouped` | 0 | no members redistributed to a different leader |
| `moved` | 0 | no members retyped into a different compendium file |
| `dropped` | 0 | no members gone from the compared compendia |

Clique counts per compendium:

| compendium | before | after | diff |
|---|---|---|---|
| `AnatomicalEntity.txt` | 145,743 | 147,565 | +1,822 |
| `Cell.txt` | 9,197 | 9,197 | 0 |
| `CellularComponent.txt` | 9,469 | 9,469 | 0 |
| `GrossAnatomicalStructure.txt` | 10,706 | 12,637 | +1,931 |

The +1,822 and +1,931 sum to **+3,753**, exactly the pure-new clique count in the source-impact
report, and the totals go 175,115 → 178,868. `Cell` and `CellularComponent` are untouched, as
expected: EMAPA is not among the Biolink `id_prefixes` for either class, so no EMAPA CURIE can
reach them.

## What was compared

Both sides were built from the **same cached intermediates**
(`babel_outputs/intermediate/anatomy/`), on the same commit, changing only the configuration under
test:

- **before** — `anatomy` with `EMAPA` removed from `anatomy_prefixes`, `anatomy_ids` and
  `anatomy_concords`.
- **after** — `anatomy` as this branch ships it: the EMAPA ids file and the (empty) EMAPA concord.

Neither side lists `EMAPA` in `anatomy_unique_prefixes`; see
[README.md](./README.md#emapa-is-not-a-unique-prefix-sme-check) for that decision and why it is the
single biggest determinant of this diff.

Toggling configuration rather than checking out the pre-EMAPA branch matters, because the
deterministic `build_sets()` ordering fix
([#945](https://github.com/NCATSTranslator/Babel/issues/945)) must be present on **both** sides.
As a cross-check, the before side's 175,115 cliques match the "pre-existing cliques" count the
source-impact report computes independently.

Because both runs read the same concord files, no cross-reference goes missing between them. Every
difference is a decision made *inside* a run.

## EMAPA was already in the compendia before this PR

This is the fact that makes the rest of the diff legible. EMAPA asserts no outgoing xrefs of its
own (see [mappings.md](./mappings.md)), but UBERON asserts 4,356 `hasDbXref` triples pointing *at*
EMAPA. Those rows live in the **UBERON** concord, so EMAPA CURIEs were already being promoted into
anatomy cliques long before EMAPA existed as a source:

| | cliques | cliques holding an EMAPA CURIE | distinct EMAPA CURIEs |
|---|---|---|---|
| before | 175,115 | 4,203 | 4,343 |
| after | 178,868 | 7,956 | 8,096 |

On both sides some cliques hold **more than one** EMAPA CURIE (140 more CURIEs than cliques, after).
That is the direct consequence of leaving `EMAPA` out of `anatomy_unique_prefixes`, and it is what
keeps this diff free of splits and drops. The 122 UBERON terms that carry multiple EMAPA xrefs are
listed in full in [`multi-emapa-xrefs.csv`](./multi-emapa-xrefs.csv).

## Why an earlier version of this diff showed 262 changes

An earlier revision of this PR did list `EMAPA` in `anatomy_unique_prefixes`, and the diff then
showed 262 change rows across 122 changed before-cliques: 70 members regrouped, 67 retyped, and
**three identifiers dropped from the compendia entirely** (`EMAPA:35358`, `EMAPA:35459`,
`EMAPA:16271` — each a deprecated or dangling CURIE that lost a `unique_prefixes` contest and had
no ids-file row to fall back on).

All of that was an artifact of the restriction, not of adding EMAPA. With EMAPA unrestricted:

- the 70 regroupings do not happen — a UBERON term keeps all of its EMAPA mappings in one clique;
- the 67 retypings do not happen — they were downstream of those splits;
- the three dropped CURIEs stay exactly where they were before this PR, so **no published
  identifier is withdrawn** and the sign-offs that removal required are moot.

### The three CURIEs fail in two different ways

They are still not live EMAPA terms, and Babel still carries them only because a UBERON xref points
at them. But they are not the same kind of problem, which matters for how they eventually get
cleaned up. Queried against `<http://reasoner.renci.org/ontology>` in UberGraph:

| CURIE | triples | `owl:deprecated` | [`IAO:0100001`](http://purl.obolibrary.org/obo/IAO_0100001) "term replaced by" | `rdfs:label` |
|---|---|---|---|---|
| `EMAPA:35358` | 9 | `true` | [`EMAPA:19226`](http://purl.obolibrary.org/obo/EMAPA_19226) "frontal suture" | none |
| `EMAPA:35459` | 9 | `true` | [`EMAPA:28061`](http://purl.obolibrary.org/obo/EMAPA_28061) "medullary collecting duct" | none |
| `EMAPA:16271` | **0** | — | — | none |

`EMAPA:35358` and `EMAPA:35459` are **properly deprecated**, and in each case the replacement EMAPA
nominates is exactly the CURIE that already leads the clique — so the ontology endorses the outcome.

`EMAPA:16271` is a different case entirely: it has **no triples at all**. It is not deprecated; it
simply is not an EMAPA term in this snapshot. It is a dangling xref target, a CURIE
[`UBERON:0007213`](http://purl.obolibrary.org/obo/UBERON_0007213) "mesenchyme derived from head
neural crest" references that was never there to begin with. (The query covers the `ontology` graph
only, so this means "not asserted there", not "never existed in any EMAPA release".)

The consequence: **a deprecation-keyed rule would clean up the first two and miss the third**, since
there is no `owl:deprecated` flag to key on. What excludes `EMAPA:16271` today is its absence from
the EMAPA ids file, which `write_emapa_ids()` builds by traversal from
[`EMAPA:0`](http://purl.obolibrary.org/obo/EMAPA_0) "anatomical structure" — a term with no axioms
is unreachable and so never collected. Any eventual fix
([#911](https://github.com/NCATSTranslator/Babel/issues/911)) needs to handle both shapes. Either
way it is a deprecation/validity problem, not something adding a new source should do as a side
effect.

## Reproducing

Both sides come from one set of cached intermediates; only the compendium-building rules re-run,
so each build takes minutes and needs no network.

```bash
# after: build anatomy as this branch ships it
rm -f babel_outputs/reports/anatomy_done
uv run snakemake -c all anatomy --rerun-triggers mtime
mkdir -p data/clique-diff/after && cp babel_outputs/compendia/*.txt data/clique-diff/after/

# before: remove EMAPA from anatomy_prefixes / anatomy_ids / anatomy_concords in config.yaml,
# then rebuild only the compendia. Delete the target sentinel too -- without it Snakemake reports
# "Nothing to be done" and silently rebuilds nothing (see docs/RunningBabel.md, "Common build
# issues").
rm -f babel_outputs/reports/anatomy_done babel_outputs/compendia/*.txt
uv run snakemake -c all anatomy --rerun-triggers mtime
mkdir -p data/clique-diff/before && cp babel_outputs/compendia/*.txt data/clique-diff/before/
git checkout config.yaml

uv run babel-clique-diff \
    --before data/clique-diff/before --after data/clique-diff/after \
    --files AnatomicalEntity.txt Cell.txt CellularComponent.txt GrossAnatomicalStructure.txt \
    --before-label "anatomy at main + #781 with EMAPA removed from anatomy_prefixes/ids/concords" \
    --after-label  "anatomy at main + #781 (EMAPA ids + concord; EMAPA NOT in anatomy_unique_prefixes)" \
    --note "Isolates adding EMAPA as an anatomy source. Both sides built from identical cached intermediates with the deterministic build_sets() ordering fix applied, so the only variable is EMAPA itself." \
    --out-csv  docs/sources/EMAPA/clique-diff/clique-diff.csv \
    --out-json docs/sources/EMAPA/clique-diff/clique-diff.summary.json
```

`--rerun-triggers mtime` keeps a `config.yaml` edit from invalidating the expensive
UberGraph-backed ids and concord rules, which must stay byte-identical across the two sides.

Restore the after-side compendia (`cp data/clique-diff/after/*.txt babel_outputs/compendia/`)
before regenerating the source-impact report: its "final compendium-assigned" counts read whatever
is in `babel_outputs/compendia/`, and reporting them off the before side is a silent, plausible
error.
