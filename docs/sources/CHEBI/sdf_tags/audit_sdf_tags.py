"""
Audit the ChEBI SDF's data-item tags against the keys make_chebi_relations() asks for.

ChEBI renames SDF tags between releases without notice. Because chebi_sdf_entry_to_dict()
matches tags by exact (normalized) string and simply omits anything it doesn't recognize, a
rename is silent: the ingest keeps running and quietly produces nothing for that field. That
is how babel-1.18 shipped an empty ChEBI secondary-ID property file (issue: CHEBI:520984 and
every other secondary ID stopped normalizing).

This script regenerates the evidence for that finding. It tabulates every tag actually present
in the SDF, normalizes each one with the parser's own normalize_sdf_tag(), and reports which of
the keys we ask for are matched and which are missing. It imports both that function and
CHEBI_SDF_KEYS rather than restating them, so the audit cannot drift from what the build does.

Usage:
    uv run python docs/sources/CHEBI/sdf_tags/audit_sdf_tags.py <path-to-ChEBI_complete.sdf>

Writes a Markdown report to stdout.
"""

import sys
from collections import Counter, defaultdict

from src.createcompendia.chemicals import CHEBI_SDF_KEYS
from src.sdfreader import normalize_sdf_tag


def count_tags(sdf_filename):
    """
    Count how many SDF entries carry each tag, keyed by the tag's normalized form.

    Normalization is many-to-one -- it folds case, strips spaces, and maps `formulae` onto
    `formula` -- so several raw tags can share a key. Every raw form seen for a key is collected
    rather than the last one overwriting the rest, otherwise the report names a tag the count
    doesn't correspond to.

    :return: (Counter of normalized_key -> count, dict of normalized_key -> sorted list of raw tags)
    """
    counts = Counter()
    raw_forms = defaultdict(set)
    with open(sdf_filename) as inf:
        for line in inf:
            if not line.startswith("> <"):
                continue
            raw = line.strip()
            key = normalize_sdf_tag(raw)
            counts[key] += 1
            raw_forms[key].add(raw)
    return counts, {key: sorted(forms) for key, forms in raw_forms.items()}


def format_raw_forms(forms):
    """Render the raw tag(s) that normalize to one key as a Markdown table cell."""
    return ", ".join(f"`{form}`" for form in forms)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <path-to-ChEBI_complete.sdf>")
    sdf_filename = sys.argv[1]

    counts, raw_forms = count_tags(sdf_filename)

    print(f"# ChEBI SDF tag audit\n\nSource file: `{sdf_filename}`\n")

    print("## Keys requested by make_chebi_relations()\n")
    print("| Requested key | Present? | Tag in SDF | Entries |")
    print("| --- | --- | --- | --- |")
    missing = []
    for key in sorted(CHEBI_SDF_KEYS):
        if key in counts:
            print(f"| `{key}` | yes | {format_raw_forms(raw_forms[key])} | {counts[key]} |")
        else:
            missing.append(key)
            print(f"| `{key}` | **NO** | — | 0 |")

    print("\n## All tags present in the SDF\n")
    print("| Tag | Normalized key | Entries | Requested? |")
    print("| --- | --- | --- | --- |")
    for key, count in counts.most_common():
        requested = "yes" if key in CHEBI_SDF_KEYS else ""
        print(f"| {format_raw_forms(raw_forms[key])} | `{key}` | {count} | {requested} |")

    if missing:
        print(f"\n**{len(missing)} requested key(s) absent from this SDF: {', '.join(sorted(missing))}**")
        return 1
    print(f"\nAll {len(CHEBI_SDF_KEYS)} requested keys are present in this SDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
