# `source-impact-report` — what does adding this source do?

Answers "what does adding *source X* do to Babel's cliques?" by re-glomming the intermediate
ids/concords twice — once with the source's files excluded, once with them included — and
diffing the two clique states.

```bash
uv run source-impact-report --source EMAPA
```

Writes `docs/sources/<SOURCE>/impact-report.md` plus an `impact-report/` subdirectory holding
the full detail files. Commit `new-cliques.csv`, `modified-cliques.csv`, and `new-xrefs.tsv`;
`modified-cliques.json` is gitignored because it grows roughly linearly with the source.

[`docs/AddingNewSources.md`](../AddingNewSources.md) is the workflow guide — when to run this,
how to read it, and how to assemble the intermediate inputs from a `stars.renci.org` snapshot
when a full local build is impractical. This page documents the tool itself.

The Snakemake rule `report_source_impact` shells out to this console script, so the two never
drift:

```bash
uv run snakemake babel_outputs/reports/source_impact/EMAPA.md
```

## Modes

- `--mode synthetic` (default) re-gloms in memory with and without the source. Needs the
  intermediate ids/concords and a registered pipeline hook. `glom()` runs twice, so memory cost
  doubles: anatomy is tractable on a laptop, chemical or gene needs an HPC node.
- `--mode remote` compares against the finished compendia of a previous published build, given
  `--remote-url` (e.g. `https://stars.renci.org/var/babel/2025dec11/`). The fallback when
  synthetic mode is too expensive or no hook is registered.
- `--mode both` runs each and reports them side by side.

Run `uv run source-impact-report --help` for the full flag list, including the roots
(`--intermediate-root`, `--compendia-root`, `--downloads-root`), the sample limits, and
`--no-biolink-lookup` for offline use.

## `PIPELINE_CONFIG`, the registry

`src/tools/source_impact_report/cli.py` holds `PIPELINE_CONFIG`, mapping each
[`babel_pipeline`](../../CLAUDE.md) to the hooks the report needs. Without an entry the report
still runs: it warns, skips the synthetic clique diff for that pipeline, and falls back to remote
mode if `--remote-url` was supplied.

An entry needs **more than just `compute_fn`**:

| Key | What it is |
|-----|------------|
| `compute_fn` | The pipeline's `compute_cliques_for_impact_report`, returning `(clique_dict, types_dict)` and accepting `excluded_sources`. |
| `compendium_files` | The compendium filenames this pipeline writes. |
| `compendium_prefixes` | The prefixes whose `labels` files are loaded to enrich clique samples. |
| `clique_classifier` | A `classify_*_clique` callable returning a clique's Biolink type. |
| `biolink_types` | The types whose `id_prefixes` order decides the preferred CURIE. |

Omit `clique_classifier` / `biolink_types` and every clique renders with a blank `biolink_type`,
while `preferred_curie()` silently falls back to the lexicographically-smallest CURIE — a `DOID`
or `Fyler` leader instead of `MONDO` or `HP`. Extract the classifier from the pipeline's
`create_typed_sets()` so the report types and orders identifiers exactly like the build does.

To register a new pipeline, split its `build_compendia()` into a "compute cliques in memory"
helper and a "write compendia" wrapper (see `src/createcompendia/anatomy.py` for the template),
then add the entry. The report loads preferred labels for each prefix listed under
`<pipeline>_prefixes` in `config.yaml`, so adding a new prefix there is what makes the new
source's labels visible — no separate change to the CLI is needed.

## What it cannot see

The "before" state is always "the same inputs with this source excluded", so the report only ever
shows cliques that were **added, expanded, or merged**.

- **Split, shrunk, and dropped cliques are not reported.** `diff_cliques` only walks
  after-cliques containing a source CURIE, so a before-clique that lost members or was split
  apart — by `unique_prefixes` rejecting a merge, or by a post-glom split like
  `split_mutually_exclusive_cliques` — produces no row. Both clique states are computed, so this
  is a missing pass rather than missing data:
  [#895](https://github.com/NCATSTranslator/Babel/issues/895). Use
  [`babel-clique-diff`](CliqueDiff.md) meanwhile — and always, for a change that restructures
  existing cliques or that isn't "add a source" at all.
- **Typing happens after the diff.** The synthetic diff is over untyped cliques.
- **Conflation is invisible.** DrugChemical and GeneProtein conflation runs after compendia are
  written, so a source contributing bridging xrefs looks quieter than its true downstream effect.

## Layout

The CLI is a thin frontend; its logic lives in `src/` where the pipeline can reach it:

- `src/tools/source_impact_report/cli.py` — argparse and `PIPELINE_CONFIG`.
- [`src/model/source.py`](../../src/model/source.py) — discovers where a source contributes.
- [`src/model/glom_diff.py`](../../src/model/glom_diff.py) — diffs the two glom states. (Not
  `compendium_diff.py`, which backs [`babel-clique-diff`](CliqueDiff.md).)
- [`src/reports/source_impact.py`](../../src/reports/source_impact.py) and
  `source_impact_details.py` — render the markdown, JSON, and detail files.
