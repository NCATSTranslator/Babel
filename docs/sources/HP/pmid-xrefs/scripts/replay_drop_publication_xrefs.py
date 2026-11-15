#!/usr/bin/env python
"""Measure what dropping one disease concord's publication xrefs (PMID, PMC, doi) does to the cliques.

Nothing is equivalent to a publication except another publication, but a concord row naming one
reaches ``glom()`` as an equivalence all the same. This replays the production
``compute_cliques_for_impact_report()`` over a completed build's disease intermediate files twice --
once as given, once with the publication rows removed from one concord -- and reports:

  1. that concord's publication rows, and how many publications one row names (which
     ``OVERUSE_FILTERED_CONCORDS`` keeps) or 2+ rows name (which it drops, since it counts rows);
  2. which of its publications another disease concord also names: the rows that would merge two
     otherwise-unrelated cliques;
  3. how many cliques the rows changed, ignoring publication members themselves (which
     ``write_compendium()`` drops, since no disease or phenotype class registers the prefixes), and
     how many publications reached ``glom()`` at all, which shows the replay is sensitive. It exits
     non-zero if any clique changed.

Usage, against a directory holding a build's ``disease/concords/`` and ``disease/ids/``::

    uv run python docs/sources/HP/pmid-xrefs/scripts/replay_drop_publication_xrefs.py <intermediate> --concord HP

``docs/sources/EFO/pmid-xrefs/scripts/replay_drop_pmid_xrefs.py`` is the EFO-specific version this
generalises.
"""

import argparse
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

# Allow running this script directly from a checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from src.createcompendia.diseasephenotype import DEFAULT_BAD_XREFS, compute_cliques_for_impact_report  # noqa: E402
from src.prefixes import DOI, PMC, PMID  # noqa: E402
from src.util import Text  # noqa: E402

# Babel's publication prefixes, upper-cased as get_prefix_or_none() returns them, plus PMC's other spelling.
PUBLICATION_PREFIXES = {PMID.upper(), PMC.upper(), DOI.upper(), "PMCID"}


def is_publication(curie):
    return (Text.get_prefix_or_none(curie.strip()) or "") in PUBLICATION_PREFIXES


def read_rows(path):
    with open(path) as inf:
        return [line.rstrip("\r\n").split("\t") for line in inf if line.strip()]


def data_files(directory):
    return sorted(p for p in directory.iterdir() if p.is_file() and not p.name.startswith("metadata"))


def cliques_without_publications(dicts):
    """Each distinct clique as a frozenset of its non-publication members; publication-only cliques vanish."""
    seen = {id(members): members for members in dicts.values()}
    return {
        frozenset(c for c in members if not is_publication(c))
        for members in seen.values()
        if any(not is_publication(c) for c in members)
    }


def replay(concords_dir, ids_dir):
    concords = [str(p) for p in data_files(concords_dir)]
    ids = [str(p) for p in data_files(ids_dir)]
    # An older build lacks some concords today's bad-xrefs files name (2025dec11 has no MP), and the
    # replay refuses a key that names no concord, so pass only the keys this build can use.
    names = {Path(c).name for c in concords}
    badxrefs = {name: path for name, path in DEFAULT_BAD_XREFS.items() if name in names}
    dicts, _types = compute_cliques_for_impact_report(concords, ids, badxrefs=badxrefs)
    return cliques_without_publications(dicts), sum(1 for curie in dicts if is_publication(curie))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("intermediate", type=Path, help="A build's intermediate/ directory (needs disease/).")
    parser.add_argument("--concord", required=True, help="Basename of the disease concord to strip, e.g. HP.")
    args = parser.parse_args(argv)
    concords_dir = args.intermediate / "disease" / "concords"
    ids_dir = args.intermediate / "disease" / "ids"

    rows = read_rows(concords_dir / args.concord)
    publication_rows = [row for row in rows if is_publication(row[0]) or is_publication(row[-1])]
    cites = Counter(row[-1].strip() for row in publication_rows)
    single = sum(1 for n in cites.values() if n == 1)
    print(f"# 1. {args.concord} publication rows")
    print(f"rows\t{len(publication_rows)} of {len(rows)}")
    print(f"subjects\t{len({row[0] for row in publication_rows})}")
    print(f"distinct publications\t{len(cites)}")
    print(f"publications named by one row (survive the overuse filter)\t{single}")
    print(f"publications named by 2+ rows (dropped by the overuse filter, which counts rows)\t{len(cites) - single}")
    for row in sorted(publication_rows):
        print("\t".join(row))

    print(f"\n# 2. {args.concord} publications that another disease concord also names")
    shared = Counter()
    for other in data_files(concords_dir):
        if other.name == args.concord:
            continue
        for row in read_rows(other):
            for curie in (row[0], row[-1]):
                if is_publication(curie) and curie.strip() in cites:
                    shared[(other.name, curie.strip())] += 1
    print(f"shared\t{len(shared)}")
    for (name, curie), n in sorted(shared.items()):
        print(f"{name}\t{curie}\t{n}")

    print(f"\n# 3. Cliques changed by dropping {args.concord}'s publication rows (publication members ignored)")
    before, publications_before = replay(concords_dir, ids_dir)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_concords = Path(tmp) / "concords"
        shutil.copytree(concords_dir, tmp_concords)
        with open(tmp_concords / args.concord, "w") as outf:
            for row in rows:
                if not (is_publication(row[0]) or is_publication(row[-1])):
                    outf.write("\t".join(row) + "\n")
        after, publications_after = replay(tmp_concords, ids_dir)
    only_before, only_after = before - after, after - before
    print(f"publication members of cliques before\t{publications_before}")
    print(f"publication members of cliques after\t{publications_after}")
    print(f"cliques before\t{len(before)}")
    print(f"cliques after\t{len(after)}")
    print(f"only before\t{len(only_before)}")
    print(f"only after\t{len(only_after)}")
    for members in sorted(sorted(c) for c in only_before)[:20]:
        print("before:\t" + " ".join(members))
    for members in sorted(sorted(c) for c in only_after)[:20]:
        print("after:\t" + " ".join(members))
    if only_before or only_after:
        raise SystemExit(f"Dropping {args.concord}'s publication xrefs changed cliques; see the rows above.")


if __name__ == "__main__":
    main()
