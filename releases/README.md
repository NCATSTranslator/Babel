# Babel Releases

Each release has a directory named after its **build**, holding the note as `README.md` and — for
most releases — an archive of that build's summary tables and provenance metadata. See
[`ARTIFACTS.md`](ARTIFACTS.md) for what the archived files are and how to read them.

For the Translator-named releases the build name is not the release name (`TranslatorFuguJuly2024`
was built as `2024jul13`); the note's own title still names the release.

## General releases

- 2025dec11: TODO

## Translator-specific releases

- [2026jul22](2026jul22/README.md) ([summary tables](2026jul22/reports/tables/))
- [2025sep1](2025sep1/README.md)
- [Babel 1.11](2025sep1/v1.11.md) — tagged but never deployed, so it has no build of its own; its
  changes first shipped in 2025sep1, and the note is filed there.
- [2025mar31](2025mar31/README.md)
- [2025jan23](2025jan23/README.md)
- [Translator "Hammerhead" November 2024](2024oct24/README.md)
- [Translator "Guppy" August 2024](2024aug18/README.md)
- [Translator "Fugu" July 2024](2024jul13/README.md)
- [May 2024](2024mar24/README.md)
- [December 2023](2023nov5/README.md)

## Preparing a release note

[`releases.yaml`](releases.yaml) records which Babel build shipped with which NodeNorm and NameRes
versions. It is the input to [`scripts/draft_release_notes.py`](scripts/draft_release_notes.py),
which drafts the mechanical parts of a new note -- the pull request list across all three
repositories, the upstream version bumps, and the per-compendium count table:

```bash
uv run python releases/scripts/draft_release_notes.py 2026jul22 \
    --build-dir /path/to/a/copy/of/the/build > releases/2026jul22/README.md
```

Add the new release to `releases.yaml` first; the entry below it supplies the comparison baselines,
so the pull request ranges are derived rather than remembered. Then triage: every PR comes out as an
unchecked checklist item, to be promoted into the section it belongs in or deleted. `## Bugfixes`
leads the note and is deliberately empty: it is for behaviour a consumer may have relied on that was
wrong before and is right now, so they can check whether it affected their analyses.

Archive the build's reports under the release name in the same pass, which is also what commits the
baseline the *next* release will be compared against:

```bash
uv run python releases/scripts/archive_build.py 2026jul22 --build-dir /path/to/a/copy/of/the/build
```

The remaining steps -- bumping `release_name` and `previous_release` in `config.yaml`, adding the
index line above, and setting the previous note's `Next release:` link -- are listed in
[`docs/RunningBabel.md`](../docs/RunningBabel.md#archiving-a-builds-reports).
Claude Code users can run `/release-notes`, which walks the whole process.
