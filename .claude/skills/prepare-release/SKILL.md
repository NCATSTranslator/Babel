---
name: prepare-release
description: Prepare config.yaml and the release branch for a new Babel build — recheck every per-release pin at the top of config.yaml (Biolink, UMLS, RxNorm, DrugBank, the pubmed2db export and its data model, the GARD list), regenerate the tables that depend on them (the PubMed DOI repairs), name the build, and run the checks. Use when starting or resuming work on a release branch or release PR (e.g. "Babel v1.19"), before starting a full build, or when asked what needs updating for the next build.
---

# Preparing a Babel build

A full build runs for many hours on the HPC, and every input it downloads is chosen by a value in
`config.yaml`. A pin that has gone stale is the cheapest bug there is to fix before the run and one
of the most expensive to find after it. This skill rechecks every one of them. `/release-notes`
takes over once the build has finished.

The details of each check live in the docs this skill points at, not here, so the two cannot drift
apart. Read each linked section when you reach it.

## 1. Orient

- Confirm you are on the release branch (`babel-v1.19` for "Babel v1.19") and find its release PR
  (`gh pr list --search "Babel v1.19 in:title"`). Read the PR's "Before releasing" list. Never tick
  a box yourself; report what you did and let the user tick it.
- List the release milestone's open issues
  (`gh issue list --milestone "Babel v1.19" --state open`) and the Critical milestone's. Say which
  of them could change what the build downloads or produces: those are worth landing first.

## 2. Name the build

In one commit (`docs/RunningBabel.md`, "Archiving a build's reports", says why they move together):

- `previous_release` → the newest release archived under `releases/` (a directory with `reports/`).
- `release_name` → this build's date-style name. Ask the user rather than guess: it becomes the
  prefix report's `name`, which labels the next release's baseline.

`tests/reports/test_prefix_comparison.py::test_previous_release_pin_is_the_baseline_immediately_before_release_name`
checks the pair. Then set `build.branch` to the release branch, and go through `build.workarounds`:
each entry ends up under "Known issues and caveats" in the release note, so delete the ones that no
longer apply and make sure each one left says what was reused and why.

## 3. Recheck every value in the release block

The block at the top of `config.yaml`, under "Versions that need to be updated on every release",
holds every value that goes stale between builds, and only those: a pipeline's stable settings live
in its own mapping further down (#1192). **The block is the checklist.** For each key in it, find
its subsection below. If a key has none, work out how to check it, check it, and add a subsection
here in the same branch: the next release depends on it.

The pages these versions are read from decide what gets pinned. If one refuses a scripted fetch, try
once more, then ask for it to be saved from a browser and read that copy: never a proxy's rendering
or an archived snapshot, which may be out of date. Say where each version was read from.

### `biolink_version`

The newest Biolink Model release: `gh release list --repo biolink/biolink-model --limit 5`. It may
be a git SHA when a build needs an unreleased fix (see AGENTS.md, "Biolink Model Usage"). Before
moving it, compare the registered prefixes of every class Babel writes, because `write_compendium()`
silently drops a CURIE whose prefix isn't registered for its clique's class:

```bash
uv run python -c "
from src import categories
from src.util import get_biolink_model_toolkit
old, new = (get_biolink_model_toolkit(v) for v in ('OLD', 'NEW'))
for cls in sorted({v for v in vars(categories).values() if isinstance(v, str) and v.startswith('biolink:')}):
    a, b = (set(tk.get_element(cls).id_prefixes or []) if tk.get_element(cls) else None for tk in (old, new))
    if a != b: print(cls, 'removed', sorted((a or set()) - (b or set())), 'added', sorted((b or set()) - (a or set())))"
```

A removed prefix that a pipeline writes is a blocker. Raise it, don't pin around it.

### `umls_version` and `rxnorm_version`

The newest UMLS Metathesaurus release (`2026AA`, `2026AB`: NLM's UMLS Knowledge Sources page) and
the newest RxNorm full monthly release (`MMDDYYYY`: NLM's RxNorm files page). Both downloads need
`UMLS_API_KEY`.

**An AB release needs one more check**: which MeSH year it carries. If it carries next year's MeSH
before NLM publishes that year's RDF, the MeSH/UMLS skew check fails the build early. #1162 holds
the procedure; if `config.yaml` has a `mesh_year`, move it with `umls_version`
(`docs/sources/MeSH/umls-mesh-skew/` measures the skew).

### `drugbank_version`

DrugBank downloads have been disabled
([cthoyt/drugbank-downloader#23](https://github.com/cthoyt/drugbank-downloader/issues/23)), so
builds reuse the last download, recorded in `build.workarounds`. Check the issue. While it's open,
keep the version and the workaround. Once it's fixed, move to the newest version and delete the
workaround.

### `pubmed2db_version`, `pubmed2db_validation_report`, `pubmed2db_data_model_version`

Follow `docs/sources/PubMed/README.md`, "Pinning an export", in this order:

1. `uv run pytest tests/createcompendia/test_publications_export.py --network`.
   `test_pinned_export_is_the_newest` fails if a newer export exists. If so, move
   `pubmed2db_version` to it and look up its validation report path, which can't be derived from
   the version.
2. Check the new export's layout against "The export contract Babel relies on". The data model
   version doesn't cover the layout, which has changed before.
3. Read its `metadata.json`. If `data_model_version` moved, read pubmed2db's changelog entry
   ("pubmed2db's data model version"), then move `pubmed2db_data_model_version`. A new major version
   needs code changes first: the unit test tying the pin to `PUBMED2DB_DATA_MODEL_MAJOR` will fail
   until they're made.
4. Re-run the network tests, which now check the new pin against the live export.
5. Download the export (`uv run snakemake -c all download_pubmed2db`, or preload it per
   `docs/RunningBabel.md`, "Preloading PubMed downloads").
6. **Regenerate the DOI repairs table**, "Keeping the table current":
   `uv run python docs/sources/PubMed/dois/characterize_dois.py`. Commit
   `input_data/pubmed_doi_repairs.yaml`, `counts.json` and `malformed_dois.csv` together. Compare
   the new counts with the old ones: a shape whose count jumps, or whose repair rate falls, is worth
   a look before the build trusts the table. If doi.org or Crossref didn't answer for every lookup,
   the script refuses to write the table; re-run it. Read any "Crossref veto" line it prints: the
   title test that vetoes a repair has been tuned on one export only.
7. `uv run pytest tests/pipeline/test_publications.py --pipeline --network --no-cov` parses the
   whole export (a few minutes), and fails if the repaired and skipped counts differ from
   `counts.json` or if a repair would take a DOI from another PMID.

### `gard_download_url`

`uv run pytest tests/datahandlers/test_gard.py::test_gard_download_url_is_current --network` fails
if the link has gone from the GARD About page and warns if a newer list is there. Repoint it and
update the "Currently:" note in its comment (`docs/sources/GARD/README.md`, "Download").

## 4. Check before the build

```bash
uv run pytest -m unit -q
uv run pytest --network -q tests/createcompendia/test_publications_export.py tests/datahandlers/test_gard.py
uv run snakemake -n --scheduler greedy   # the whole DAG resolves with the new pins
```

Fix anything that fails before the build starts.

## 5. Commit, push, report

- Commit each pin on its own, so its message is the release-note line ("Update UMLS to 2026AB").
  Those are the commits that stay on a release branch (`docs/RunningBabel.md`, "Which commits stay
  on the release branch"). Regenerated tables go in the commit of the pin that caused them.
- Push, and confirm the push against the remote.
- Report, a line per pin: old value, new value, where it was read from, and what checked it. Then
  list what's still open on the release PR and the milestone. Starting the HPC run is the user's
  call: don't start it.
