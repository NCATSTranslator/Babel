---
name: release-notes
description: Prepare the combined Babel/NodeNorm/NameRes release notes. Use when asked to write, draft or update release notes for a Babel release, or when a build has finished and needs its note in releases/.
---

# Preparing a Babel release note

A Babel release is a build plus the NodeNorm and NameRes versions deployed against it, so the note
in `releases/<build>/README.md` covers all three repositories. The goal is a note a Babel consumer
can skim to answer: what changed, what is new, and what might now look different or broken.

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
    --build-dir <copy of the build's output directory> > releases/<build>/README.md
```

The note lives in the build's own directory, beside that build's archived reports — see
`releases/ARTIFACTS.md`. For recent releases the build name and the release id are the same.

`--build-dir` needs `reports/tables/` from the build; without it the count table and the
notable-changes section come out as TODOs. The user usually has a copy under `data/`. An
already-archived release works too — `releases/<build>/` mirrors the build directory's paths, and
the script falls back to it when `--build-dir` is omitted, so re-drafting an old note needs nothing
but the repository.

Draft while the release is on **Exp**, not Dev. That is the order the release actually happens in —
Exp is publicly reachable, so the note is what tells people they can test the new build before it is
promoted — and it is what the `--nodenorm-status` / `--nameres-status` defaults point at. If either
service still reports the *previous* Babel version, the script emits an HTML warning comment above
the `## Deployed database sizes` table; treat that as "not ready to draft this section yet" rather
than editing the comment out.

## 3. Triage the pull request checklist

Every PR lands as `- [ ]` under `## All changes in this release`, already grouped by repository.
Move what matters up into the section it belongs in, then **delete the checklist section** before
publishing — it is scaffolding, not output. The NodeNorm and NameRes PRs move into the
`## NodeNorm Redis` and `## NameRes Solr` sections directly above them.

Where a Babel PR goes:

| Section | What belongs there |
|---|---|
| `## Bugfixes` | Wrong behaviour a consumer may have relied on, now corrected. See below — this bar is high. |
| `### Updates` | Upstream data version bumps. The script generates these. |
| `### New features and identifier/mapping additions` | New sources, ontologies, compendia, outputs, or user-facing tools. |
| `### Improvements to Babel's output` | Changes to what Babel *produces*: typing, conflation, labels, synonyms, xref filtering. |
| `### Development and infrastructure` | Packaging, CI, formatting, testing, docs, SLURM, refactors. Real work, no output change. |
| `### Minor changes and fixes` | Small bug fixes and maintainer tooling. |
| `### Known issues and caveats` | Still true of *this* build: reused downloads, hand-carried files, shipped bugs. |

`## Bugfixes` is not "PRs labelled bug". It is the narrow set a consumer has to **act** on: *you
used to see X, you now see Y — check whether X affected your downstream analyses, and whether Y is
the behaviour you want.* A fix for something nobody could have noticed is a Minor change. The script
emits this section empty and first; promote into it, or delete the section if this release has none.
Leaving it empty is not an option — "no bugs worth flagging" should be a decision someone made.

House style, from `releases/2026jul22.md`:

- `[MAJOR]` prefixes anything a consumer would notice or should act on.
- Related PRs collapse into one bullet ending in a parenthesised list of `[Babel #473]`-style links
  to each one. Prefer one clear sentence about the change over one bullet per PR.
- One link style throughout: `[Babel #NNN]` / `[NodeNorm #NNN]` / `[NameRes #NNN]`, which is what
  the checklist already emits and what disambiguates three repositories. Not `[PR #NNN]`, not a bare
  URL.
- Sub-bullets carry the rationale and any known follow-up issue.
- Non-PR changes are fine as prose (`Updated RxNorm from X to Y` — the script generates these).
- **Third person**, except in `### Known issues and caveats`, where "I downloaded HMDB in a browser
  and copied it to the HPC" *is* the fact being reported and first person is the honest way to say
  it. Everywhere else the actor is Babel, not whoever cut the release.

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

- `<build-dir>/reports/content/compendia/<Type>.json` — `count_by_prefix` for this build. The
  baseline's is the same file in its own archive, under
  `releases/<previous>/reports/content/compendia/`.
  Comparing per-prefix is what turns "Protein is down 38%" into "UniProtKB is down 103.8M and
  nothing else moved".
- `<build-dir>/reports/<pipeline>_completeness.txt` — `Missing identifiers: 0` rules out a
  dropped-identifier bug. **Not archived** — this one needs the real build directory.
- `<build-dir>/logs/error-report-*.md` — rule failures during the run. Also not archived.
- `git log <previous-tag>..<tag> --grep="(#NNN)"` — whether a specific fix actually made the build.
  Check this rather than asserting a known issue is or isn't fixed.

Remember that concords cannot answer clique-membership questions (see `AGENTS.md`, "Debugging"):
answer from the finished build's reports, the DuckDB `Edge` table, or Node Normalization.

## 5. Finish the release bookkeeping

1. Archive the build's reports into `releases/<build>/` — the summary tables, the per-compendium
   content reports, the provenance metadata, and the prefix report that becomes the next release's
   baseline (~420 KB; see `releases/ARTIFACTS.md`):

   ```bash
   uv run python releases/scripts/archive_build.py <build> --build-dir <build-dir>
   ```

   Use the **build** name, not the release id — for the older Translator-named releases they differ.
   The script checks that the prefix report's `name` field matches, and fails if it does not: that
   field is written from `release_name` in `config.yaml`, which is easy to leave pointing at a
   previous build, and it is what labels the *next* release's comparison report. If it fires, work
   out which release the value names before correcting it — do not just overwrite it.
2. Leave `config.yaml`'s two pins alone until the **next** build is planned, then move both in one
   commit: `previous_release` to this release, `release_name` to the new build. They must never be
   equal — a run whose `release_name` matches its `previous_release` diffs its own baseline and
   reports that nothing changed, so `generate_prefix_comparison()` raises rather than write it. A
   unit test enforces the pairing.
3. Add the index line to `releases/README.md` (newest first).
4. Set the previous note's `Next release:` line to point at this one.
5. Fill in the `## Deployed database sizes` table from the deployed Redis and Solr instances. The
   script emits the row skeleton; the numbers are not available from the build.

## 6. Check

```bash
uv run pytest tests/test_draft_release_notes.py tests/reports/test_prefix_comparison.py -q
uv run rumdl fmt releases/   # the generated PR lines are longer than the 100-column limit
uv run rumdl check releases/
```

The drift test fails if a note exists without a `releases.yaml` entry, and the pin test fails if
`previous_release` is not the newest committed baseline older than `release_name` — which catches
both a stale pin and a pair left equal.

## 7. Final review

**Do this only once triage is finished.** These are checks on the assembled note, and running them
while sorting PRs would be guidance about mistakes that haven't happened yet.

Report findings, don't silently apply them: several turn on judgement only the author has. Collect
the cut candidates into a temporary `## Suggested deletions` section at the end of the note, each
with a one-line note saying where it came from and why it's a candidate, so the decision is a
reading pass rather than a re-derivation.

1. **Unlinked bullets.** Find every bullet with no `[Babel #NNN]` link and try to supply one — the
   `## All changes in this release` checklist is still in the working copy and usually has it, since
   both were generated from the same PR range. If the PR turns out to be cited in an *earlier* note,
   the bullet is describing a change that already shipped: move it to `## Suggested deletions`.
2. **Already-shipped PRs.** Check every cited PR against the earlier notes, not just the unlinked
   ones:

   ```bash
   for pr in $(grep -oE 'pull/[0-9]+' releases/<build>/README.md | cut -d/ -f2 | sort -u); do
     hits=$(grep -l "pull/$pr\b" releases/*/*.md | grep -v "<build>" | tr '\n' ' ')
     [ -n "$hits" ] && echo "#$pr also in: $hits"
   done
   ```

   A hit is not automatically a deletion — an old PR is legitimately cited as *context* for new work
   ("the design in #506 gave bad results, so #626 replaced it"). Distinguish the two by reading how
   the bullet uses it, and say which is which. Note that `v1.11` never deployed, so a PR appearing
   only there may never have reached a shipped note.
3. **Duplication across sections.** The same change often appears as a headline under
   `## Areas that changed substantially` and as a paragraph in the per-repository notes below it.
   That is deliberate — the two serve
   different readers. Verify the two agree on the numbers and the PR links, and that they are far
   enough apart not to read as a stutter. Flag it if one says something the other contradicts.
4. **Unexplained movers.** The script emits an unchecked item per compendium that moved ≥25%. Every
   box should end up ticked, explained above, or carrying a filed issue link. Do not delete an
   unticked one.
5. **Overstated claims.** Check what a bullet asserts against what its PR actually did. `#482` was
   written up as "updated `*Factory` methods to use SQLite" when it converted `TaxonFactory` alone
   and explicitly deferred the rest. Prefer the specific name — a note is searchable history, and
   someone grepping `TaxonFactory` years later should land here.
6. **Voice and link style.** One voice, one link form (see the house style above).
