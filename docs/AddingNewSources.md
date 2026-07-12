# Adding a new source to Babel

This document walks through wiring a new identifier source into Babel and validating the
addition. EMAPA is the worked example throughout.

**Terminology** — two concepts that are easy to confuse:

- **pipeline** (`anatomy`, `chemical`, `diseasephenotype`, …) — the intermediate-file namespace,
  called `babel_pipeline` in code. Paths below use `<pipeline>` as a placeholder. Usually
  corresponds to the src/createcompendia/<pipeline>.py file that generates these outputs. Sometimes,
  untyped compendia will be generated before being assigned Biolink Types (e.g. `chemical`).
- **Biolink type** (`biolink:AnatomicalEntity`, `biolink:SmallMolecule`, …) — the class URI stored
  in compendia. A single pipeline may generate multiple Biolink types (one per file) or even one
  file containing multiple Biolink types (leftover_umls.txt -> umls.txt is the only current example
  of this).

A third, unrelated concept: **`umls_semantic_type`** (or `sty`) is a UMLS TUI code / tree string
used only inside the UMLS ingest (see `docs/sources/UMLS/Leftover.md`) — don't conflate it with
either pipeline or Biolink type. Avoid the bare phrase "semantic type" for any of the three unless
quoting an external vocabulary (e.g. "UMLS semantic type").

## What "adding a source" means

A Babel source contributes two kinds of intermediate artefacts under
`babel_outputs/intermediate/<pipeline>/`:

- an `ids/<SOURCE>` file listing the CURIEs the source supplies, with a second column
  declaring each row's Biolink type;
- a `concords/<SOURCE>` file listing cross-references the source asserts, as
  `CURIE1\trelation\tCURIE2` triples.

`build_compendia()` in each `src/createcompendia/*.py` module loads every ids and concord
file for its pipeline, calls `glom()` to build equivalence cliques, types each clique with
`create_typed_sets`, and writes one compendium JSONL per Biolink output type.

A source can span multiple pipelines (MESH contributes to anatomy, chemical, disease, and
more), multiple Biolink types within one pipeline (UBERON's anatomy ids file declares both
`biolink:AnatomicalEntity` and `biolink:GrossAnatomicalStructure`), and multiple prefixes.

## Step-by-step: wiring a new source

### 1. Register the prefix

Add a constant to `src/prefixes.py`:

```python
EMAPA = "EMAPA"
```

If your prefix does not yet appear in the Biolink Model's `id_prefixes` for the target
Biolink class, raise that with the Biolink team — the model determines preferred-identifier
ordering inside `NodeFactory`.

### 2. Add a data handler (if needed)

Sources that need a non-trivial download, file parse, or external API call get a module
under `src/datahandlers/<source>.py`. EMAPA queries UberGraph live and uses the shared
`src/ubergraph.py` `build_sets()` helper instead. OBO ontologies generally fit the
UberGraph pattern: declare the root CURIE and the target Biolink type, and reuse the
shared loader.

### 3. Add a compendium-building hook

In `src/createcompendia/<pipeline>.py`:

- Add an entry to the per-pipeline registry (e.g. `ANATOMY_OBO_SOURCES` in `anatomy.py`).
- Add a `write_<source>_ids(outfile)` function. **Give every CURIE a presumptive Biolink
  type in column 2** (`CURIE\tbiolink:Type`, no header). Be as specific as the source's
  structure allows — e.g. EMAPA types descendants of
  [`EMAPA:35949`](http://purl.obolibrary.org/obo/EMAPA_35949) "organ" and
  [`EMAPA:35868`](http://purl.obolibrary.org/obo/EMAPA_35868) "tissue" as
  `biolink:GrossAnatomicalStructure` and everything else as `biolink:AnatomicalEntity`.
  If the chosen Biolink type's `id_prefixes` does not yet include your prefix, the build
  will drop those identifiers — the impact report flags this via the survival columns.
- Add concord-extraction logic. For OBO sources sharing `build_anatomy_obo_relationships()`,
  this means adding the source to the open-file map and the prefix list. Other sources have
  bespoke extraction functions (`build_anatomy_umls_relationships`, etc.).
- Include the source's prefix in the `unique_prefixes` argument to `glom()` if its
  identifiers must remain pairwise-unique within a clique.

### 4. Wire Snakemake rules

In `src/snakefiles/<pipeline>.snakefile`:

- Add an ids rule whose output is `intermediate/<pipeline>/ids/<SOURCE>`. Use
  `retries: 3` for any network-backed rule (UberGraph, FTP, HTTP). UberGraph rules need
  this only as a Snakemake-level safety net: `TripleStore.execute_query` already retries
  each individual SPARQL call up to 3 times with exponential back-off (configurable via
  `config["sparql"]["max_attempts"]` and `retry_base_delay_seconds`), so a full UberGraph
  rule failure indicates something more persistent than a single-request glitch.
- Add the source's concord output and metadata YAML to the existing concord-building rule.

### 5. Update `config.yaml`

Add the source name to the per-pipeline config lists:

- `<pipeline>_prefixes`
- `<pipeline>_ids`
- `<pipeline>_concords`
- `generate_dirs_for_labels_and_synonyms_prefixes` if the source produces its own labels
  and synonyms (UberGraph-backed sources typically do not).

### 6. Add source documentation

Create `docs/sources/<SOURCE>/` with at least:

- `README.md` — what the source is, how it is integrated, and pointers to sibling files.
- `impact-report.md` — generated by the tooling below, with an `impact-report/`
  subdirectory of full detail files.

Optional expansion files: `download.md`, `filtering.md`, `mappings.md`.

Wherever a doc file mentions a specific ontology term by CURIE, link it to its OBO PURL
and include the preferred label in double-quotes:

```markdown
[`EMAPA:0`](http://purl.obolibrary.org/obo/EMAPA_0) "Anatomical structure"
```

Resolve CURIEs with `src/util.py:get_biolink_prefix_map()` (`converter.expand("EMAPA:0")`).
Preferred labels are in `babel_downloads/<PREFIX>/labels` (tab-separated `CURIE\tlabel`).

### 7. Add tests

- Unit tests in `tests/datahandlers/` for any new parsing or extraction helper.
- Network-marked tests for downloads.
- A pipeline-marked test in `tests/pipeline/test_<source>_pipeline.py` using the pattern
  from `test_emapa_pipeline.py`: a fixture that invokes the write function and caches its
  output, plus assertions that the ids and concord files have non-empty, syntactically-valid
  content. Add the fixture to `tests/pipeline/conftest.py` and `VOCABULARY_REGISTRY`.

### 8. Register the source for the impact report (optional, recommended)

The synthetic comparison mode needs a per-pipeline compute hook. Anatomy is wired via
`anatomy.compute_cliques_for_impact_report`. For other pipelines, split that pipeline's
`build_compendia()` into a "compute cliques in memory" helper and a "write compendia" wrapper, then
register the helper in `PIPELINE_CONFIG` in `src/tools/source_impact_report/cli.py` (see
[docs/tools/SourceImpactReport.md](tools/SourceImpactReport.md)).

The report also loads preferred labels for each prefix listed under `<pipeline>_prefixes` in
`config.yaml` to enrich the clique samples. Adding the new prefix there (step 5) is therefore
what makes the new source's labels visible in the rendered report — no separate change to the
CLI is needed.

Without a registered hook the impact report still runs — it warns and skips the synthetic
clique diff for that pipeline, and falls back to remote mode if you supply `--remote-url`.

## Validating the addition

After the intermediate ids and concord files have been built, generate a source-impact report:

```bash
uv run source-impact-report --source <SOURCE>
```

Default output is `docs/sources/<SOURCE>/impact-report.md`. Commit it alongside the source's
docs so the PR captures the build state at the time the source was introduced.

For compendia too large to re-glom on a laptop, pair synthetic with a remote-build comparison:

```bash
uv run source-impact-report --source <SOURCE> --mode both \
    --remote-url https://stars.renci.org/var/babel/2025dec11/
```

The Snakemake convenience rule writes the same output to the build-artifact tree:

```bash
uv run snakemake -c 1 babel_outputs/reports/source_impact/<SOURCE>.md
```

### Running a full local build

If the pipeline fits on a single machine, build all its intermediates and compendia locally
and run the report against the populated `babel_outputs/` tree. Anatomy is comfortably
tractable; other pipelines may not be.

```bash
export UMLS_API_KEY=...   # required for UMLS-backed rules

uv run snakemake -c all <pipeline>
uv run source-impact-report --source <SOURCE>
```

The Snakemake target name matches the pipeline name (e.g. `anatomy`, `chemical`). Building
the full target also produces compendia, which populates section 2's "final
compendium-assigned" counts; without compendia present that section is blank.

Caveats:

- A previous interrupted run can leave the working directory locked. Clear it with
  `uv run snakemake --unlock` before retrying.
- UberGraph-backed rules carry `retries: 3`, but a full UberGraph outage will propagate.
- The full target rebuilds upstream sources, so numbers reflect data fetched at build time.

### Generating the report without a full pipeline build

Synthetic mode re-runs `glom()` over the intermediate files of **every** source for the
pipeline, not just the new one, so it needs that whole set on disk. The practical approach
on a laptop is to assemble the inputs from a published build:

1. **Pick a recent build snapshot** at `https://stars.renci.org/var/babel/` (`<recent-build>`).
   Its `intermediate/<pipeline>/` directory holds all existing sources' ids and concords.

2. **Download the baseline intermediate set** for each affected pipeline:

   ```bash
   BASE="https://stars.renci.org/var/babel/<recent-build>/intermediate/anatomy"
   ROOT="/tmp/impact/intermediate/anatomy"
   mkdir -p "$ROOT/ids" "$ROOT/concords"
   for f in UBERON GO CL MESH NCIT UMLS; do
       curl -sf "$BASE/ids/$f" -o "$ROOT/ids/$f"
   done
   for f in UBERON GO CL UMLS WIKIDATA; do
       curl -sf "$BASE/concords/$f" -o "$ROOT/concords/$f"
   done
   ```

3. **Generate the new source's intermediate files locally** and place them alongside the
   downloaded files in `$ROOT/ids` and `$ROOT/concords`.

4. **Run synthetic mode** against the assembled directory:

   ```bash
   uv run source-impact-report --source <SOURCE> --mode synthetic \
       --intermediate-root /tmp/impact/intermediate \
       --output docs/sources/<SOURCE>/impact-report.md
   ```

`--compendia-root` is read only for section 2's "final compendium-assigned" counts; with
no local compendia, leave it pointing at a non-existent path.

**Refreshing a report after a typing or extraction change** — regenerate the affected source
files before re-running the tool. Calling the writer directly is cheapest:

```bash
uv run python -c "import src.createcompendia.anatomy as a; a.write_emapa_ids('babel_outputs/intermediate/anatomy/ids/EMAPA')"
```

The Snakemake rule treats an existing ids file as up-to-date unless you delete it or pass
`--forcerun`, so the direct call avoids a no-op rule run.

### Reading the report

The generated Markdown has four sections:

1. **Identifiers added** — totals by prefix and by pipeline. The total should match the
   row count of `ids/<SOURCE>`; unexpected prefixes indicate an extraction bug.
2. **Biolink types** — source-declared types vs. final compendium-assigned types. A large
   mismatch usually means glom is pulling source CURIEs into cliques typed differently than
   declared — may be intentional or a bug. Final compendium-assigned counts are read from
   on-disk compendia and lag until compendia are rebuilt.
3. **Cross-references added** — total concord rows plus partner-prefix breakdown. Unexpected
   prefixes indicate the extraction did not filter the right xref namespaces (compare to
   the `ignore_list` in `build_anatomy_obo_relationships()` or the `allowed_prefixes` in
   `build_disease_obo_relationships()`). See "Auditing a source's xrefs" below — a clean
   section 4 does **not** mean section 3 is clean.
4. **Clique impact** — for each pipeline with a registered compute hook:
   - **new cliques** composed only of source identifiers (with percentage increase over
     the pre-existing count),
   - **existing cliques** that contain source identifiers, split into structurally grown
     (at least one new member added) and promotion-only (source CURIE was already present
     via another source's xref; the ids file now types it explicitly),
   - **merged cliques** where source CURIEs bridged previously-separate cliques.

   Samples (up to 3 each) are ranked by review-worthiness — most distinct member labels
   first, so over-promiscuous xrefs surface early. Rankings are fully deterministic. Watch
   for merges joining very different concepts — usually a sign of an over-broad xref.

   **Caveat:** section 4 is computed from intermediate files and cannot see downstream
   Biolink prefix filtering, so its counts are an upper bound. The survival columns in the
   detail files make this explicit per identifier.

If the report shows no synthetic diff for your pipeline, either it is not registered in
`PIPELINE_CONFIG` or the intermediate files were incomplete.

#### Detail files for SME review

Alongside `impact-report.md`, the tool writes an `impact-report/` subdirectory with the
full, uncapped data as CSV/TSV files (GitHub renders these as sortable tables). Pass
`--no-detail-files` to skip. All files are deterministically sorted (clean diffs).

The three committed files:

- **`new-cliques.csv`** — one row per pure-new clique. Columns: `pipeline, preferred_id,
  preferred_label, biolink_type, member_count, equivalent_ids`, plus survival columns
  `preferred_id_would_survive, needs_biolink_registration, unsupported_prefixes`.
- **`modified-cliques.csv`** — one row per source identifier landing in an existing clique.
  Includes `change_kind` (`expanded`/`merged`), `added_kind` (`added` = structurally new,
  `preexisting` = already present via xref), survival columns, and the clique's full
  `equivalent_ids`. Filter `added_kind = added` for structural growth, or
  `would_be_added = false` for identifiers that will be dropped downstream.
- **`new-xrefs.tsv`** — one row per cross-reference touching a source CURIE, scanned across
  all concord files. Columns: `pipeline, subject, subject_label, predicate, object,
  object_label, asserted_by, status` (`added` = new source's concord asserts it;
  `from_other_source` = another source's concord touches a source CURIE).

`modified-cliques.json` is written locally but gitignored.

##### Survival columns

`write_compendium` keeps only identifiers whose prefix is in the Biolink Model's
`id_prefixes` for the clique's Biolink type and silently drops the rest.

- `would_be_added` — `true`/`false`/blank (blank if no clique type or `--no-biolink-lookup`).
- `needs_biolink_registration = true` — the prefix must be registered in the Biolink Model
  for that class before Babel can emit it. EMAPA's `biolink:GrossAnatomicalStructure` terms
  are the live example: EMAPA is not yet in that class's `id_prefixes`, so they show
  `would_be_added = false`.

#### Promoted vs. truly added — a common surprise

For ontologies that other Babel sources already xref, the new source's CURIEs may already
be present in "before" cliques as xref leaves. The ids file then promotes those leaves to
first-class typed identifiers without adding anything structurally. EMAPA is the canonical
example: its 4,188 "expanded" cliques are all promotion-only, because UBERON's concord
already brings EMAPA CURIEs into the relevant cliques. Read the truly-grown vs.
promotion-only split in section 4 before drawing conclusions about structural change.

Even though EMAPA contributes 8,059 identifiers, only 4,802 land in `AnatomicalEntity.txt`
(section 2). The remainder live in cliques whose dominant Biolink type ends up as Cell,
CellularComponent, or GrossAnatomicalStructure — and `NodeFactory` drops them because EMAPA
is not in those types' `id_prefixes`. The survival columns make this visible per identifier.

#### Auditing a source's xrefs

Section 4 reporting "0 cliques merged" is **not** evidence that a source's xrefs are good. An xref
whose target prefix is absent from the pipeline's other concords merges nothing, and one whose
prefix is absent from the clique type's Biolink `id_prefixes` is dropped by `NodeFactory` at
`write_compendium`. Such xrefs are *inert*, not *correct* — they still bloat the concord, and they
become live the moment another source starts emitting that prefix.

So audit section 3 (and `impact-report/new-xrefs.tsv`) on its own terms. Sample a few rows per
target prefix and ask whether the pair is an equivalence or an "is about" relation. MP's review is
the worked example: 663 xref rows, of which nine of thirteen target namespaces turned out to be
anatomy, processes, citations or Wikipedia URLs (see `docs/sources/MP/mappings.md`).

To decide whether a suspect prefix is inert or load-bearing, check both gates:

```bash
# Gate 1: does the target prefix appear in any OTHER concord of this pipeline?
#         (if not, it can never bridge this source into an existing clique)
cd babel_outputs/intermediate/<pipeline>/concords
for f in $(ls | grep -v '\.yaml$'); do
  printf '%-12s ' "$f"; cut -f3 "$f" | sed 's/:.*//' | sort -u | tr '\n' ' '; echo
done
```

```python
# Gate 2: is the prefix in the clique type's Biolink id_prefixes?
#         (if not, write_compendium drops it and it never reaches a compendium)
from src.util import get_biolink_model_toolkit, get_config
tk = get_biolink_model_toolkit(get_config()["biolink_version"])
print(tk.get_element("phenotypic feature").id_prefixes)
```

If a prefix fails both gates it is inert and can be filtered with no change to compendium output —
which makes the filtering a safe, reviewable cleanup rather than a behavioral change. If it passes
either gate, the xrefs are load-bearing and removing them needs a build-vs-build clique diff.

Note that the `Edge` table of the DuckDB export answers gate 1 for a *finished* build much faster
than scanning concords (`SELECT DISTINCT clique_leader FROM Edge WHERE curie IN (...)`).

### Comparing across builds

When `--mode remote` or `--mode both` is set, a fifth section summarises clique counts
against the remote build. This is a coarse count (totals and cliques-with-source counts);
synthetic mode is the source of truth for the pure-new/expanded/merged bucketing.

### Build-vs-build clique diff (restructured cliques: split / merge / delete)

The source-impact report models what *adding* a source does: its "before" is a full re-glom of the
pipeline's intermediate files with the source excluded, its "after" a re-glom with everything.
`diff_cliques()` then walks only the **after-cliques that contain a source CURIE**, bucketing them
into pure-new / expanded / merged. So it **does not report** before-cliques that split, lose
members, or disappear — not because that is unknowable, but because nothing iterates the before
side. Synthetic mode holds both complete clique states in memory; see
[#895](https://github.com/NCATSTranslator/Babel/issues/895) for the follow-up that surfaces them.

Two things worth knowing about that gap:

- **It cannot be recovered from the concord files.** Both runs read the *same* concords — the
  "before" run simply skips the new source's file — so no xref goes missing between them. When a
  clique does split it is because of a decision made *inside* a run: `glom()` rejects a merge whose
  union would hold two identifiers sharing a `unique_prefixes` prefix, and pipelines like
  diseasephenotype run `split_mutually_exclusive_cliques()` after glom. Adding a source can flip
  either. (`remove_overused_xrefs` is applied per concord file, so a new file cannot push another
  file's xrefs over the overuse threshold.) The clique dicts, not the concords, are the level to
  compare at.
- **A plain source addition rarely splits anything.** Union-find only unions, so absent the two
  non-monotone paths above a source that just contributes ids and concord rows can only grow and
  merge cliques.

When a change *restructures existing* cliques — a new policy like keeping two prefixes disjoint, a
concord-filtering or close-match change, or any source whose addition pulls members back out — use
[`babel-clique-diff`](tools/CliqueDiff.md) instead. It is also the only option for changes that are
not "add a source" at all: with no source to exclude, synthetic mode cannot model them even in
principle. It diffs two finished compendium builds and reports, per changed before-clique, a
`destination_kind` for each group of members: `kept` (still under the same leader), `leader_changed`
(identical membership, only the preferred identifier was reassigned), `regrouped` (members
redistributed to a different leader within the same compendium file — the split case), `moved` (the
CURIE was retyped into a *different* compared compendium file), or `dropped` (gone from every
compared after compendium):

```bash
uv run babel-clique-diff \
    --before <overlap-or-baseline-compendia-dir> --after <new-compendia-dir> \
    --files Disease.txt PhenotypicFeature.txt \
    --before-label "<what the before build is>" --after-label "<what the after build is>" \
    --note "<what this diff isolates>" \
    --out-csv  docs/sources/<SOURCE>/<change>/clique-diff.csv \
    --out-json docs/sources/<SOURCE>/<change>/clique-diff.summary.json
```

Pass `--before-label`/`--after-label`/`--note`: they are recorded in the summary's `about` block so
the committed artifact says which build was which and what it isolates. Remember the summary's
`clique_count.diff` is where *wholly new* cliques (with no before counterpart) show up — they are
never per-clique change rows — so a diff that adds many cliques can still have few rows (see the
reconciliation in `docs/sources/MP/disjointness.md`).

Build both sides from the **same cached intermediates**, changing only the thing under test
(e.g. build at the commit with the change and again with it reverted/disabled), so the diff
provably isolates that one change. The diff doubles as a completeness check: if the only
differences are the intended ones, nothing else regressed.

Commit convention: put the artifacts in a change-named subdirectory —
`docs/sources/<SOURCE>/<change>/` for a source-specific change (e.g. `MP/disjointness/`) or
`docs/pipelines/<pipeline>/<change>/` for a pipeline-wide one — alongside a short prose page
explaining what was compared and summarising added/split/moved/deleted (see
`docs/sources/MP/disjointness.md`). Always commit the tiny `clique-diff.summary.json`; commit
the per-row `clique-diff.csv` when it is reasonably sized (it is the same class of artifact as
the source-impact `new-cliques.csv`), and gitignore it like `modified-cliques.json` only if it
is very large.

**Stranded concord-only identifiers.** A clique-restructuring change can strand an identifier
that appears in a concord but in no ids file (an out-of-date mapping). With no member carrying
a declared Biolink type, the clique cannot be typed; `create_typed_sets` drops it with a
warning rather than aborting the build (see `diseasephenotype.create_typed_sets`). A handful of
these in the `dropped` column is expected; a large number suggests an extraction problem.

## Known limitations

- **Only anatomy has a synthetic-mode hook.** Other pipelines produce empty section 4 unless
  you first extract a `compute_cliques_for_impact_report` helper from that pipeline's
  `build_compendia` and register it in `PIPELINE_CONFIG` (see `anatomy.py` for the template).
- **Synthetic mode needs the full intermediate set.** If only your new source's files are on
  disk, every after-clique is classified as pure-new. Build or download the full pipeline's
  intermediates first.
- **Remote mode is coarse.** It reports total/with-source/current-only counts but cannot
  classify diffs into pure-new/expanded/merged (compendia are published; intermediate
  concord files are not).
- **Split / shrunk / dropped cliques are not reported.** `diff_cliques` only walks after-cliques
  containing a source CURIE, so a before-clique that lost members or was split apart (by
  `unique_prefixes` rejecting a merge, or by a post-glom split like
  `split_mutually_exclusive_cliques`) produces no row. Both clique states are computed, so this is a
  missing pass rather than missing data —
  [#895](https://github.com/NCATSTranslator/Babel/issues/895). Use `babel-clique-diff` meanwhile.
- **Typing happens after the diff.** The synthetic diff is over untyped cliques; section 2's
  compendium-assigned view requires on-disk compendia and is blank without them.
- **Conflation is invisible.** DrugChemical and GeneProtein conflation runs after compendia
  are written; a source that introduces bridging xrefs will appear quieter than its true
  downstream effect.
- **Memory cost doubles for large pipelines.** `glom()` runs twice; anatomy is tractable but
  chemical or gene will need an HPC node or the remote-mode fallback.

## Related reading

- `AGENTS.md` "Adding a new data source" — short, command-focused summary.
- `docs/sources/EMAPA/` — the worked example for an OBO-from-UberGraph source.
- `src/tools/source_impact_report/cli.py` — CLI implementation; `PIPELINE_CONFIG` is the registry.
  See [docs/tools/SourceImpactReport.md](tools/SourceImpactReport.md).
- `src/model/source.py` and `src/model/glom_diff.py` — shared primitives.
- `src/createcompendia/anatomy.py` — template for the compute helper / writer split.
