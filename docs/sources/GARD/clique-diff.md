# Clique diff: disease before and after adding GARD

The [source-impact report](./impact-report.md) models what *adding* GARD contributes, but by
construction it only walks after-cliques that contain a GARD CURIE. It therefore cannot report
before-cliques that split, lose members, or disappear (see
[#895](https://github.com/NCATSTranslator/Babel/issues/895)), and — as this page shows — it also
cannot say *which* clique a newly added GARD identifier landed in when two of them compete for it.
Two build-vs-build [`babel-clique-diff`](../../tools/CliqueDiff.md) runs close both gaps.

Each directory is named for the *change* it measures, not for the tool:

- [`on-addition/`](./on-addition/) — `main` vs this branch. Answers "does adding GARD restructure
  anything?"
- [`mistyped-xref/`](./mistyped-xref/) — this branch with vs without the
  `input_data/doid_badxrefs.txt` entry. Answers "what does that one dropped row actually change?"

## Headline: adding GARD is purely additive

**No before-clique loses, gains a different leader, is retyped, or splits.** All 2,160 changed
before-cliques are changed only because they *gained* GARD identifiers; every one of their existing
members is classified `kept`.

| destination_kind | rows | meaning |
|---|---|---|
| `regrouped` | 0 | no members redistributed to a different leader |
| `leader_changed` | 0 | no clique's preferred identifier was reassigned |
| `moved` | 0 | no members retyped into a different compendium file |
| `dropped` | 0 | no members gone from the compared compendia |

Clique counts per compendium:

| compendium | before | after | diff |
|---|---|---|---|
| `Disease.txt` | 365,087 | 379,406 | +14,319 |
| `PhenotypicFeature.txt` | 75,477 | 75,477 | 0 |

The +14,319 is exactly the pure-new clique count in the source-impact report, and it is the whole
difference: 440,564 → 454,883 across the two compendia. `PhenotypicFeature.txt` is untouched, as
expected — `disease_extra_prefixes` is a per-class allowlist applied to `biolink:Disease` only, so
no GARD CURIE can reach a phenotype clique even if one were xrefed into it.

## What the additive headline hides: a mistyped DOID xref

[`DOID:0061030`](http://purl.obolibrary.org/obo/DOID_0061030) "hemophilia" writes its GARD xref as
`GARD:0418`, a typo for [`GARD:10418`](https://rarediseases.info.nih.gov/?gard_id=10418)
"Hemophilia". Unpadded it becomes `GARD:418` "Essential pentosuria" — which
[`DOID:0111258`](http://purl.obolibrary.org/obo/DOID_0111258) "pentosuria" also xrefs. Two cliques
therefore claim the same new identifier.

They do not merge: `DISEASE_UNIQUE_PREFIXES` includes MONDO, and both cliques already hold one
([`MONDO:0018660`](http://purl.obolibrary.org/obo/MONDO_0018660) "hemophilia" and
[`MONDO:0009846`](http://purl.obolibrary.org/obo/MONDO_0009846) "pentosuria"), so `glom()` refuses
the union. Instead the contested identifier is awarded to whichever clique claims it first, and
DOID's concord lists hemophilia's row before pentosuria's — so **the hemophilia clique ends up
holding a rare-disease identifier labelled "Essential pentosuria", and pentosuria never gets its own
registry term.** `input_data/doid_badxrefs.txt` drops the hemophilia row, which puts `GARD:418`
where it belongs.

[`mistyped-xref/clique-diff.csv`](./mistyped-xref/clique-diff.csv) is that one change in isolation —
three rows, the whole effect of the entry:

| before clique | destination | kind | members |
|---|---|---|---|
| `MONDO:0018660` "hemophilia" (11) | `MONDO:0009846` "pentosuria" (12) | `regrouped` | 1 — `GARD:418` "Essential pentosuria" |
| `MONDO:0018660` "hemophilia" (11) | `MONDO:0018660` "hemophilia" (10) | `kept` | 10 |
| `MONDO:0009846` "pentosuria" (11) | `MONDO:0009846` "pentosuria" (12) | `kept` | 11 |

### Neither standard artifact would have caught this

Worth recording, because it is a limit of the tooling rather than of this change:

- The **source-impact report** sees only that `GARD:418` joined *an* existing clique. Landing in the
  wrong one is not a category it has.
- The **`on-addition/` clique diff is byte-identical with and without the fix.** `GARD:418` is a new
  identifier in both builds, and `babel-clique-diff` classifies *before*-clique members — no
  before-member moves either way. Both builds report the same 2,160 `kept` rows.

What surfaced it was reading the two cliques out of the finished compendia directly, which is the
rule [`AGENTS.md`](../../../AGENTS.md) states for clique-membership questions. It is also why the
isolating diff above is run branch-vs-branch rather than main-vs-branch: with the disputed CURIE
present on *both* sides, its move becomes visible.

## What was compared

Both sides were built from the **same cached intermediates**
(`babel_outputs/intermediate/disease/`), with only the code and configuration under test changing:

| | before | after |
|---|---|---|
| `on-addition/` | `main` at `a3ae3e4d` — no GARD ingest, DOID concord built without GARD unpadding | this branch — GARD ingested, DOID's GARD xrefs unpadded, bad-xref entry active |
| `mistyped-xref/` | this branch, `DOID:0061030 GARD:418` commented out of `input_data/doid_badxrefs.txt` | this branch, entry active |

Reproduce with:

```bash
uv run snakemake -c 4 babel_outputs/compendia/Disease.txt --forcerun get_disease_doid_relationships
uv run babel-clique-diff --before <before-dir> --after <after-dir> \
    --files Disease.txt PhenotypicFeature.txt \
    --out-csv clique-diff.csv --out-json clique-diff.summary.json
```

Put the target *before* `--forcerun`: `--forcerun` takes a list, so a target written after it is
swallowed as another rule name and Snakemake falls back to building the entire pipeline.

The full `on-addition/` per-row CSV (2,160 rows, all `kept`) is not committed: it is 737 KB
carrying no information the summary lacks, and it goes stale on the next build.
`mistyped-xref/clique-diff.csv` is committed in full, at three rows.
