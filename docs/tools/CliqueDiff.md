# `babel-clique-diff` — diff the cliques of two builds

Compares the finished JSONL compendia of two Babel builds and reports which cliques split,
merged, or lost members, and — most usefully — which CURIEs were *dropped* from the output
entirely.

```bash
uv run babel-clique-diff \
    --before <baseline-compendia-dir> --after <comparison-compendia-dir> \
    --files Disease.txt PhenotypicFeature.txt \
    --before-label "main (no MP)" --after-label "mp-hp-disjoint" \
    --note "isolates PR #886" \
    --out-csv diff.csv --out-json summary.json
```

`--before-label`/`--after-label`/`--note` are optional but recommended: they are recorded in the
summary's `about` block so the artifact is self-describing (a reader never has to guess which build
was before vs after, or what the diff isolates). Labels default to the directory paths.

The CLI is `src/tools/clique_diff/cli.py`; the diff itself is
[`src/model/compendium_diff.py`](../../src/model/compendium_diff.py), so a pipeline rule or a
second tool can reuse it.

## When to use this rather than the source impact report

[`source-impact-report`](SourceImpactReport.md) answers "what does adding *source X* do?" by
re-glomming intermediate ids/concords with vs. without one source. Its "before" is always "the
same inputs with this source excluded", so it only ever shows added, expanded, or merged
cliques — never cliques that split, lose members, or disappear.

`babel-clique-diff` answers "how did the cliques change between *build A* and *build B*?" given
the same inputs but different code, config, or upstream data. Because it works on finished
compendia rather than glom state, it can compare a local build against a published
`stars.renci.org` build without re-running glom. That makes it the right tool for:

- any glom-logic change (close-match handling, `unique_prefixes`, overuse filtering);
- a change that pulls members back out, such as a disjointness policy;
- a change that isn't "add a source" at all, which synthetic mode cannot model even in principle;
- a release regression check.

Build both sides from the same cached intermediates so the diff isolates the one change; it then
doubles as a completeness check. Commit a worked example's output alongside the change that
motivated it, under `docs/sources/<SOURCE>/<change>/` or `docs/pipelines/<pipeline>/<change>/` —
always the small `clique-diff.summary.json`, plus the per-row `clique-diff.csv` when reasonably
sized.

## What is (and isn't) diffed

Per compendium line, the tool reads exactly two fields: the clique's **leader** (the
preferred identifier, `identifiers[0].i`) and its **membership** (the full set of
`identifiers[*].i` CURIEs). A clique is unchanged only if *both* are identical between
builds; if either changed, every before-clique member is classified into one row per
`destination_kind`:

- `kept` — same leader, and the member is still under it.
- `leader_changed` — the whole clique's membership is byte-identical, but its preferred
  identifier was reassigned to a different member (e.g. a Biolink `id_prefixes` priority
  change, or `NodeFactory` tie-breaking, picked a new leader).
- `regrouped` — the member moved to a different clique within the same compared compendium
  file (a real split/merge).
- `moved` — the CURIE still exists in the after build, but in a clique under a different
  compendium file (e.g. `Disease.txt` → `PhenotypicFeature.txt`) — it was retyped to a
  different Biolink type. `destination_compendium` names that file.
- `dropped` — the CURIE is absent from every compared after compendium.

Everything else in a compendium record — `type` (Biolink type), `identifiers[*].l`
(labels), `identifiers[*].d`/`t` (descriptions/taxa), `preferred_name`, `ic`, and
`clique_identifier_count` — is **not compared**. In particular:

- A clique's Biolink `type` is not diffed directly. A type change is only visible
  indirectly, as `moved`, and only when the before- and after-type's compendium files are
  both passed to `--files` — a type change between two files neither of which was passed
  is invisible to this tool.
- Label, description, and taxon changes on an otherwise-unchanged clique are invisible;
  such a clique is reported as fully unchanged (no row at all).
- Not every row is caused by the change under test. When a build uses
  `glom(..., unique_prefixes=…)`, a cross-reference contested by two same-prefix cliques is awarded
  to one of them by a tie-break that is sensitive to the input *set*, so adding or removing an
  *unrelated* source can reshuffle members between existing same-prefix cliques (deterministically,
  without creating or deleting any). Expect a few such incidental rows; see
  [NCATSTranslator/Babel#894](https://github.com/NCATSTranslator/Babel/issues/894) and the worked
  example in `docs/sources/MP/disjointness.md`.

## Reading a row

Every row names both endpoints of a move: the before-clique it left (`before_leader`,
`before_leader_label`, `before_leader_type`, `before_size`) and the after-clique it landed in
(`destination`, `destination_label`, `destination_type`, `after_size`), plus
`destination_compendium`, the file that after-clique lives in. `destination_compendium` equals
`compendium` on every kind except `moved`, which is precisely the case where the destination
lives elsewhere — so a retyped member's new home is readable straight off the row. Members are
grouped by destination *clique*, so a before-clique whose members scatter across several
after-cliques gets one row per destination.

`dropped` is the only kind with no destination clique: `destination` is the literal
`(dropped)`, and `destination_label`, `destination_compendium`, `destination_type` are empty
with `after_size` 0.

Labels and Biolink types are not part of change detection, but they *are* emitted as
read-only annotation columns to make the CSV legible without a separate lookup. So is
`example_members`, which lists up to five members as `CURIE "label"` using before-build
labels — a sample, not the full membership, so read `member_count` for the true size of the
group.

## Summary JSON

`--out-json` writes a self-describing summary, `{"about": …, "compendia": …}`. `about` carries
the two build labels, the `note`, and the compared `files`. `compendia` maps each filename to its
counts: a nested `clique_count` (`before`/`after`/`diff`/`diff_percent`) plus
`changed_before_cliques`, `dropped_member_count` (the headline regression signal),
`moved_member_count`, `regrouped_member_count`, and `leader_changed_count`.

`diff_percent` is `null` when the before build had no cliques in that compendium but the after
build has some: the percentage is undefined, and `0.0` would misread as "unchanged". It is `0.0`
only when the two counts genuinely match.

Note that we are deliberately not interested in additions that don't modify an existing clique:
this tool is primarily meant to track how a software change changes the outputs, not whether new
additions were included. Additions *will* be counted in the summary JSON, but *will not* be included
in the change rows (we may add an optional `--include-additions` options in the future to support
this if needed). The [source impact report](SourceImpactReport.md) is really interested in new
additions and tracks those. See `docs/sources/MP/disjointness.md` for a worked example of this exact
reconciliation.
