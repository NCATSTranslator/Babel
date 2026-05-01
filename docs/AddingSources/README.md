# Adding new data sources to Babel

Documentation about the *process* of adding a new external data source to Babel —
distinct from per-source documentation, which lives under [`docs/sources/`](../sources/).
This directory is the home for cross-cutting conventions, checklists, and references
that any source-addition PR can cite.

This directory was seeded alongside the [MP integration](../sources/MP/README.md) and
should grow over time. Suggested future companions: a checklist file, a metadata-format
reference, and a CI-checks reference. Until those exist, this README serves as both
landing page and minimum-viable checklist.

## Checklist for source-addition PRs

The following items are recommendations, not a hard gate. Each was motivated by
something that went wrong (or was at risk of going wrong) during the MP integration.
The first one alone catches most of what we would otherwise have to discover during a
full pipeline run.

### 1. Pipeline-DAG smoke test

Before requesting review, run `uv run snakemake --dry-run <target>` for each compendium
target the new source feeds into. The dry-run resolves the rule graph without executing
anything and will fail loudly if a prefix has been added to a config list (`*_ids`,
`*_labelsandsynonyms`, `*_concords`, `generate_dirs_for_labels_and_synonyms_prefixes`)
without a matching rule that produces the expected file. This single check catches the
class of bug that blocked PR #300 for nearly a year.

A natural follow-up is to run the same dry-run in CI for every PR that touches
`config.yaml` or `src/snakefiles/`.

### 2. Treat `metadata.yaml` as the source of truth for counts

Babel's existing convention (see `src/metadata/provenance.py`) is that every concord
rule emits a `metadata-<NAME>.yaml` file alongside the concord, and `disease_compendia`
/ `chemical_compendia` / etc. consume both. The metadata file records:

- top-level concord counts (lines, distinct CURIEs, per-predicate counts, per-prefix-pair
  counts) computed by walking the concord file;
- a `combined_from` block per upstream input, with whatever provenance and filter
  statistics make sense for that input format (rows in, rows dropped at each filter
  stage with reasons, rows written, predicates kept and dropped).

When you add a new source, *do not* hand-write counts into documentation. Numbers in
documentation drift; numbers in `metadata.yaml` are regenerated every time the
pipeline runs. Documentation should describe filters, intent, and provenance; the
metadata file should describe what actually happened.

If your new rule produces something other than a concord (e.g. an enrichment file,
a new identifier list with non-trivial provenance), use `write_metadata` /
`write_combined_metadata` directly to produce the matching YAML.

See [`docs/Metadata.md`](../Metadata.md) for the full schema, the four helper
functions in `src/metadata/provenance.py`, and worked examples (including the
recursive `combined_from` pattern).

### 3. Cross-reference quality report

For sources that contribute concords (i.e. add new equivalence edges), the impact on
Babel cliques is usually the thing reviewers actually want to know. Until we have a
standardised tool for this, the recommended approach is:

- Run the relevant compendium target on a reference state (e.g. `main`).
- Run it again with the new source.
- Compute the diff: cliques added, cliques merged, cliques split, leader changes by
  prefix.

PRs should attach a summary of these numbers to the PR description, ideally with
spot-checked example cliques. The MP PR did this informally (counts of clique
leaders by prefix). The goal is to make this routine and easy.

### 4. Predicate policy for SSSOM-derived concords

When ingesting SSSOM mapping tables, the choice of which `predicate_id` values to
accept is consequential. Some guidance:

- **`skos:exactMatch`** is the conservative default. It maps cleanly onto Babel's
  equivalence semantics.
- **`skos:closeMatch` and `skos:relatedMatch`** are weaker — they say two terms are
  *related* but not necessarily equivalent. Accepting them widens the equivalence net
  (more cliques merged) at the cost of cross-clique blending (terms that are merely
  similar end up sharing identifiers). The MP integration accepts both; see
  [`docs/sources/MP/ValidationFindings.md`](../sources/MP/ValidationFindings.md) for
  the trade-offs that surfaced in practice.
- **`skos:broadMatch` and `skos:narrowMatch`** are *asymmetric* and should not be
  accepted as equivalence. They imply a parent/child relationship, not equivalence,
  and treating them as equivalence will silently merge cliques across category
  boundaries.
- **`owl:equivalentClass`** is symmetric and stronger than `skos:exactMatch`; some
  sources use it instead. Accepting it is reasonable but should be a deliberate
  decision.

If your new source needs a non-default predicate policy, justify the choice in the
PR description and write down the policy as a comment on the snakefile rule.

### 5. Per-source documentation under `docs/sources/`

Every new source should ship with `docs/sources/<SOURCE>/README.md` that includes:

- the source's URL(s) (both the canonical URL the pipeline downloads and a
  commit-pinned permalink at the time of writing, so future readers can diff);
- the maintainer, license, and any relevant identifiers (root term, version, etc.);
- the path identifiers take through Babel (which functions, which UberGraph or other
  service, which Biolink type the entries are assigned);
- the cross-references downloaded and a summary of filters applied;
- pointers to the run-time artefacts where quantitative information lives.

The intent is that PRs touching source URLs or filters update the matching
`docs/sources/<SOURCE>/README.md` in the *same* change. See
[`docs/sources/MP/README.md`](../sources/MP/README.md) for the seed example.

A `ValidationFindings.md` file alongside the README is recommended whenever the
source addition surfaced concrete quality concerns or filter trade-offs that future
maintainers should know about. That file may be deleted later once the issues are
resolved or the standing reports cover the same ground.

## See also

- [`docs/Architecture.md`](../Architecture.md): high-level pipeline architecture.
- [`docs/RunningBabel.md`](../RunningBabel.md): how to run the pipeline locally.
- [`docs/sources/`](../sources/): per-source documentation.
- [`src/metadata/provenance.py`](../../src/metadata/provenance.py): the metadata-emission helpers.
