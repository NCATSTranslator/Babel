#!/usr/bin/env bash
# Prove a release-branch split lost no content: every moved commit's patch-id
# must appear in exactly one theme branch, and every stay-behind commit
# (bucket STAY or FORMAT) must appear in none.
#
# This is the final verification of the split workflow in docs/RunningBabel.md
# ("Releasing a new Babel version"). It uses `git patch-id --stable`, which
# hashes the diff *including context lines*, so a commit that was deliberately
# adapted while resolving a cherry-pick conflict will legitimately differ — those
# are reported as "missing" and must be confirmed by hand (interdiff the applied
# change against the original; only context, not added/removed lines, should
# differ).
#
# Configuration is via environment variables (all optional):
#   RELEASE_BRANCH  the branch being split        (default: current branch)
#   BASE_BRANCH     base the theme branches sit on (default: main)
#   BUCKETS_MAP     hash<TAB>bucket TSV            (default: data/commit-split/buckets.tsv)
#
# The theme branches to check are passed as positional arguments. A branch that
# is stacked on another theme branch (rather than on BASE) is fine — pass it too;
# patch-ids are collected relative to BASE for every branch.
#
# Example:
#   RELEASE_BRANCH=babel-1.18 scripts/commit-split/verify-completeness.sh \
#       split/duckdb-memory-tuning split/download-robustness \
#       split/babel-errors-tool split/unichem-chemicals \
#       split/leftover-umls-types split/drugchemical-concord-validation
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

RELEASE_BRANCH="${RELEASE_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
BASE_BRANCH="${BASE_BRANCH:-main}"
MAP="${BUCKETS_MAP:-data/commit-split/buckets.tsv}"

if [ "$#" -eq 0 ]; then
  echo "usage: [RELEASE_BRANCH=.. BASE_BRANCH=.. BUCKETS_MAP=..] $0 SPLIT_BRANCH..." >&2
  exit 1
fi
if [ ! -f "$MAP" ]; then
  echo "error: buckets map not found: $MAP" >&2
  exit 1
fi
BRANCHES="$*"
echo "release: $RELEASE_BRANCH   base: $BASE_BRANCH"
echo "branches: $BRANCHES"

# Collect patch-ids present across all split branches (relative to base).
UNION=$(mktemp)
for b in $BRANCHES; do
  for c in $(git rev-list --no-merges "$BASE_BRANCH..$b"); do
    git show "$c" | git patch-id --stable
  done
done | awk '{print $1}' | sort -u > "$UNION"
echo "distinct patch-ids across split branches: $(wc -l < "$UNION" | tr -d ' ')"

bucketof() { grep -vE '^\s*#' "$MAP" | awk -v h="$1" 'substr($1,1,8)==substr(h,1,8){print $2}'; }

echo
echo "=== checking each $RELEASE_BRANCH commit ==="
miss_major=0
leaked_stay=0
for c in $(git rev-list --no-merges "$BASE_BRANCH..$RELEASE_BRANCH"); do
  pid=$(git show "$c" | git patch-id --stable | awk '{print $1}')
  bucket=$(bucketof "$c")
  in_union=no
  grep -q "^$pid$" "$UNION" && in_union=yes
  case "$bucket" in
    STAY | FORMAT)
      if [ "$in_union" = yes ]; then
        echo "  LEAK: $bucket commit $(git rev-parse --short "$c") '$(git show -s --pretty=%s "$c" | cut -c1-50)' appears in a split branch"
        leaked_stay=$((leaked_stay + 1))
      fi
      ;;
    *)
      if [ "$in_union" = no ]; then
        echo "  MISSING: $bucket commit $(git rev-parse --short "$c") '$(git show -s --pretty=%s "$c" | cut -c1-50)' NOT found in any split branch"
        miss_major=$((miss_major + 1))
      fi
      ;;
  esac
done
echo
echo "major commits missing from branches: $miss_major   (expected: only conflict-adapted ones; confirm each by interdiff)"
echo "STAY/FORMAT commits leaked into branches: $leaked_stay   (expected: 0)"
rm -f "$UNION"
