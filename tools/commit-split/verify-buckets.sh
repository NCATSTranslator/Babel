#!/usr/bin/env bash
# Verify a commit->bucket mapping covers every commit in BASE..RELEASE exactly
# once, and emit an audit TSV (hash, date, bucket, subject) for review.
#
# This is step 1 of the release-branch split workflow documented in
# docs/RunningBabel.md ("Releasing a new Babel version"): it proves the
# classification is complete and unambiguous before any theme branch is built.
#
# Configuration is via environment variables (all optional):
#   RELEASE_BRANCH  the branch holding the date-interleaved mix of fixes
#                   (default: the current branch)
#   BASE_BRANCH     the branch the release will merge into (default: main)
#   BUCKETS_MAP     hash<TAB>bucket TSV; '#'/blank lines ignored
#                   (default: data/commit-split/buckets.tsv)
#
# Side outputs (.assigned, .actual, classification.tsv) are written next to the
# map file, which normally lives in the gitignored data/ scratch dir.
#
# Example:
#   RELEASE_BRANCH=babel-1.18 tools/commit-split/verify-buckets.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

RELEASE_BRANCH="${RELEASE_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
BASE_BRANCH="${BASE_BRANCH:-main}"
MAP="${BUCKETS_MAP:-data/commit-split/buckets.tsv}"

if [ ! -f "$MAP" ]; then
  echo "error: buckets map not found: $MAP" >&2
  echo "Create a hash<TAB>bucket TSV first (see docs/RunningBabel.md)." >&2
  exit 1
fi
DIR="$(dirname "$MAP")"
RANGE="$BASE_BRANCH..$RELEASE_BRANCH"
echo "range: $RANGE   map: $MAP"

# Assigned short hashes (strip comments/blank lines), normalized to 8 chars.
grep -vE '^\s*#' "$MAP" | grep -vE '^\s*$' | awk '{print substr($1,1,8)}' | sort > "$DIR/.assigned"

# Actual commits in range, as 8-char short hashes.
git rev-list --no-merges "$RANGE" | cut -c1-8 | sort > "$DIR/.actual"

echo "assigned: $(wc -l < "$DIR/.assigned" | tr -d ' ')   actual: $(wc -l < "$DIR/.actual" | tr -d ' ')"

echo "=== in range but UNASSIGNED ==="
comm -23 "$DIR/.actual" "$DIR/.assigned" | while read -r h; do
  printf '  %s  %s\n' "$h" "$(git show -s --pretty=%s "$h")"
done

echo "=== assigned but NOT in range (typo?) ==="
comm -13 "$DIR/.actual" "$DIR/.assigned"

echo "=== duplicate assignments ==="
grep -vE '^\s*#' "$MAP" | grep -vE '^\s*$' | awk '{print substr($1,1,8)}' | sort | uniq -d

# Emit the audit TSV in chronological order.
OUT="$DIR/classification.tsv"
printf 'hash\tdate\tbucket\tsubject\n' > "$OUT"
git rev-list --reverse --no-merges "$RANGE" | while read -r full; do
  short=$(echo "$full" | cut -c1-8)
  bucket=$(grep -vE '^\s*#' "$MAP" | awk -v h="$short" 'substr($1,1,8)==h {print $2}')
  printf '%s\t%s\t%s\t%s\n' "$short" "$(git show -s --pretty=%ad --date=short "$full")" "${bucket:-?}" "$(git show -s --pretty=%s "$full")" >> "$OUT"
done
echo "=== wrote $OUT ==="
echo "=== bucket counts ==="
tail -n +2 "$OUT" | cut -f3 | sort | uniq -c | sort -rn
