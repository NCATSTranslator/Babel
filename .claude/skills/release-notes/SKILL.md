---
name: release-notes
description: Prepare the combined Babel/NodeNorm/NameRes release note for a Babel build that is shipping to Translator. Use when asked to write, draft or update release notes for a Babel release, or when a build has finished and needs its note in releases/.
---

# Preparing a Babel release note

A Babel release is a build plus the NodeNorm and NameRes versions deployed against it, so the note
in `releases/<release>.md` covers all three repositories. The goal is a note a Babel consumer can
skim to answer: what changed, what is new, and what might now look different or broken.

`releases/scripts/draft_release_notes.py` does the mechanical half. This skill is the judgement
half.

## 1. Add the release to `releases/releases.yaml` first

Newest entry at the top. The entry *below* it supplies the comparison baselines, so getting this
right is what makes the PR ranges correct.

You need, and must ask the user for rather than guess:

- the build name (also the git tag in this repo) and the Babel version it was cut from;
- the NodeNorm and NameRes versions deployed against this build, **in deployment order**.

The version lists matter. NameRes v1.5.2 was cut in April 2026, *after* v1.6.0/v1.6.1/v1.6.2, as a
maintenance release on the v1.5 line — so "everything since v1.5.2" is neither "everything numbered
above v1.5.2" nor "everything released after it by date". The script diffs with
`gh api .../compare/BASE...HEAD`, which follows the real history; your job is to record which
version was actually deployed. If the previous release's entry has no NodeNorm/NameRes versions, ask
— the older notes predate the practice and nothing in the repo records them after the fact.

## 2. Draft

```bash
uv run python releases/scripts/draft_release_notes.py <release> \
    --build-dir <copy of the build's output directory> > releases/<release>.md
```

`--build-dir` needs `reports/tables/` from the build; without it the count table and the
notable-changes section come out as TODOs. The user usually has a copy under `data/`.

Draft while the release is on **Exp**, not Dev. That is the order the release actually happens in —
Exp is publicly reachable, so the note is what tells people they can test the new build before it is
promoted — and it is what the `--nodenorm-status` / `--nameres-status` defaults point at. If either
service still reports the *previous* Babel version, the script emits an HTML warning comment above
the `## Summary` table; treat that as "not ready to draft this section yet" rather than editing the
comment out.

## 3. Triage the pull request checklist

Every PR lands as `- [ ]` under `## All changes in this release`. Move what matters up into
`## Bugfixes` / `## Updates` / `## New features`, then **delete the checklist section** before
publishing — it is scaffolding, not output.

House style, from `releases/2025sep1.md`:

- `[MAJOR]` prefixes anything a consumer would notice or should act on.
- Related PRs collapse into one bullet with several links:
  `([PR #473](…), [PR #483](…))`. Prefer one clear sentence about the change over one bullet per PR.
- Sub-bullets carry the rationale and any known follow-up issue.
- Non-PR changes are fine as prose (`Updated RxNorm from X to Y` — the script generates these).

The `#### N routine ... changes` sub-sections are dependency bumps, version increments and merge
commits. Summarise them in one line or delete them wholesale, but don't quietly drop a few and keep
the rest: "there were no dependency bumps" and "the dependency bumps are summarised" are different
claims.

## 4. Explain every large change

This is the part that earns the note. Take the `## Areas that changed substantially` list and trace
each large movement back to a PR in the checklist, then rewrite it as prose with the numbers inline.

A change that traces to nothing is the finding. It is either an upstream data change (say so, and
say how you checked) or a bug to file **before** the release ships. Do not hand-wave it.

Where to check:

- `<build-dir>/reports/content/compendia/<Type>.json` — `count_by_prefix` for this build; the same
  numbers for the baseline come out of `releases/prefix_reports/<previous>.json` under
  `by_clique[*].by_file[<Type>]`. Comparing per-prefix is what turns "Protein is down 38%" into
  "UniProtKB is down 103.8M and nothing else moved".
- `<build-dir>/reports/<pipeline>_completeness.txt` — `Missing identifiers: 0` rules out a
  dropped-identifier bug.
- `<build-dir>/logs/error-report-*.md` — rule failures during the run.
- `git log <previous-tag>..<tag> --grep="(#NNN)"` — whether a specific fix actually made the build.
  Check this rather than asserting a known issue is or isn't fixed.

Remember that concords cannot answer clique-membership questions (see `AGENTS.md`, "Debugging"):
answer from the finished build's reports, the DuckDB `Edge` table, or Node Normalization.

## 5. Finish the release bookkeeping

1. Archive the two artifacts under the release name:
   - `<build-dir>/reports/duckdb/prefix_report.json` → `releases/prefix_reports/<release>.json`
   - `<build-dir>/reports/content/compendia_report.json` → `releases/summaries/<release>.json`

   Check the archived prefix report's `name` field matches the release. It is written from
   `release_name` in `config.yaml`, which is easy to leave pointing at a previous build — and it is
   what labels the *next* release's comparison report.
2. Leave `config.yaml`'s two pins alone until the **next** build is planned, then move both in one
   commit: `previous_release` to this release, `release_name` to the new build. They must never be
   equal — a run whose `release_name` matches its `previous_release` diffs its own baseline and
   reports that nothing changed, so `generate_prefix_comparison()` raises rather than write it. A
   unit test enforces the pairing.
3. Add the index line to `releases/README.md` (newest first).
4. Set the previous note's `Next release:` line to point at this one.
5. Fill in the `## Summary` table from the deployed Redis and Solr instances. The script emits the
   row skeleton; the numbers are not available from the build.

## 6. Check

```bash
uv run pytest tests/test_draft_release_notes.py tests/reports/test_prefix_comparison.py -q
uv run rumdl fmt releases/   # the generated PR lines are longer than the 100-column limit
uv run rumdl check releases/
```

The drift test fails if a note exists without a `releases.yaml` entry, and the pin test fails if
`previous_release` is not the newest committed baseline older than `release_name` — which catches
both a stale pin and a pair left equal.
