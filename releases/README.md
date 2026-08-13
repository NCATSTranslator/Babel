# Babel Releases

Each release below has a note, and most also have an archive of that build's summary tables and
provenance metadata under `releases/<build>/` — see [`ARTIFACTS.md`](ARTIFACTS.md) for what those
files are and how to read them.

## General releases

- TODO

## Translator-specific releases

- [2026jul22](2026jul22.md) ([summary tables](2026jul22/reports/tables/))
- [2025sep1](2025sep1.md)
- [Babel 1.11](v1.11.md)
- [2025mar31](2025mar31.md)
- [2025jan23](2025jan23.md)
- [Translator "Hammerhead" November 2024](TranslatorHammerheadNovember2024.md)
- [Translator "Guppy" August 2024](TranslatorGuppyAugust2024.md)
- [Translator "Fugu" July 2024](TranslatorFuguJuly2024.md)
- [May 2024](TranslatorMay2024.md)
- [December 2023](TranslatorDecember2023.md)

## Preparing a release note

[`releases.yaml`](releases.yaml) records which Babel build shipped with which NodeNorm and NameRes
versions. It is the input to [`scripts/draft_release_notes.py`](scripts/draft_release_notes.py),
which drafts the mechanical parts of a new note -- the pull request list across all three
repositories, the upstream version bumps, and the per-compendium count table:

```bash
uv run python releases/scripts/draft_release_notes.py 2026jul22 \
    --build-dir /path/to/a/copy/of/the/build > releases/2026jul22.md
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
