# Commit-split verification tools

Helper scripts for the release-branch split workflow described in
[`docs/RunningBabel.md`](../../docs/RunningBabel.md) ("Releasing a new Babel
version"). A production run accumulates a date-interleaved mix of trivial tweaks
and substantial changes directly on the release branch (for example
`babel-1.17`); before merge, the substantial changes are peeled out into
themed PRs off `main`. These scripts make that split auditable.

They do not decide the classification for you — that judgement is yours, and you
record it in a `hash<TAB>bucket` TSV (the "buckets map"). The scripts verify the
classification is complete and that the resulting branches lost nothing.

## The buckets map

A TSV mapping each commit in `BASE..RELEASE` to a bucket. Lines starting with
`#` and blank lines are ignored. Bucket names are free-form, with two reserved:

- `STAY` — a commit that stays on the release branch (one-line-describable).
- `FORMAT` — a pure reformat commit re-applied per branch rather than
  cherry-picked.

Everything else is a theme bucket (one PR each). Keep the map in the gitignored
`data/` scratch dir; a header comment listing what each bucket means is helpful.
The map is inherently per-release (it lists that release's commit hashes), so
it is not reused between releases — only these scripts are.

## verify-buckets.sh

Checks the map covers every commit in `BASE..RELEASE` exactly once (no
unassigned, no out-of-range typo, no duplicate) and writes a chronological
`classification.tsv` audit file plus per-bucket counts. Run this first.

```bash
RELEASE_BRANCH=babel-1.18 scripts/commit-split/verify-buckets.sh
```

## verify-completeness.sh

After the theme branches are built, proves no content was lost: every moved
commit's `git patch-id --stable` appears in exactly one branch, and every
`STAY`/`FORMAT` commit appears in none. Pass the theme branches as arguments
(including any branch stacked on another theme branch).

```bash
RELEASE_BRANCH=babel-1.18 scripts/commit-split/verify-completeness.sh \
    split/duckdb-memory-tuning split/download-robustness \
    split/babel-errors-tool split/unichem-chemicals \
    split/leftover-umls-types split/drugchemical-concord-validation
```

`patch-id --stable` hashes the diff *including context lines*, so a commit you
deliberately adapted while resolving a cherry-pick conflict will legitimately
report as "missing". Confirm each by interdiffing the applied change against the
original — only context lines, never added/removed lines, should differ.

## Configuration

Both scripts read the same optional environment variables:

- `RELEASE_BRANCH` — the branch being split (default: current branch).
- `BASE_BRANCH` — base the theme branches sit on (default: `main`).
- `BUCKETS_MAP` — path to the buckets TSV (default:
  `data/commit-split/buckets.tsv`).
