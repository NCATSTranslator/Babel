#!/usr/bin/env python
"""Measure what dropping EFO's PMID xrefs does to the disease/phenotype cliques.

EFO cites the paper a term was curated from as a class-level ``oboInOwl:hasDbXref``, e.g. EFO 3.95.0
has ``EFO_0007836`` "coenzyme Q10 measurement" ``hasDbXref "PMID:27149984 "``. ``efo.make_concords()``
wrote every hasDbXref target into ``concords/EFO``, and every concord row is fed to ``glom()`` as an
equivalence, so each of those rows asserted that a disease or phenotype *is* a publication.

This replays the production ``compute_cliques_for_impact_report()`` over a completed build's disease
intermediate files twice -- once as built, once with the PMID rows removed from ``concords/EFO``, as
``EFO_EXCLUDED_XREF_PREFIXES`` now does -- and reports:

  1. the EFO concord's xref targets by prefix (what else EFO writes that is not an equivalence);
  2. how many PMIDs one EFO row names, and how many 2+ rows name, which the unscoped
     ``OVERUSE_FILTERED_CONCORDS["EFO"]`` filter already drops;
  3. how many cliques the PMID rows changed, ignoring PMID members themselves (which
     ``write_compendium()`` drops, since no disease or phenotype class registers the prefix). It
     asserts this is zero for the build it was run on;
  4. which PMIDs EFO cites that another disease concord also names -- the rows that *would* merge
     two otherwise-unrelated cliques. Zero today, which is why the defect was latent.

Usage, against a directory holding a build's ``disease/concords/`` and ``disease/ids/``::

    uv run python docs/sources/EFO/pmid-xrefs/scripts/replay_drop_pmid_xrefs.py <intermediate>
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
from src.prefixes import PMID  # noqa: E402
from src.util import Text  # noqa: E402


def read_rows(path):
    with open(path) as inf:
        return [line.rstrip("\r\n").split("\t") for line in inf if line.strip()]


def is_pmid(curie):
    # str.strip(): 2025dec11's EFO concord carries a few PMIDs with a trailing space.
    return (Text.get_prefix_or_none(curie.strip()) or "") == PMID


def cliques_without_pmids(dicts):
    """Each distinct clique as a frozenset of its non-PMID members; PMID-only cliques vanish."""
    seen = {id(members): members for members in dicts.values()}
    return {
        frozenset(c for c in members if not is_pmid(c))
        for members in seen.values()
        if any(not is_pmid(c) for c in members)
    }


def replay(concords_dir, ids_dir):
    concords = sorted(str(p) for p in concords_dir.iterdir() if p.is_file() and not p.name.startswith("metadata"))
    ids = sorted(str(p) for p in ids_dir.iterdir() if p.is_file() and not p.name.startswith("metadata"))
    # An older build lacks some concords today's bad-xrefs files name (2025dec11 has no MP), and the
    # replay refuses a key that names no concord, so pass only the keys this build can use.
    names = {Path(c).name for c in concords}
    badxrefs = {name: path for name, path in DEFAULT_BAD_XREFS.items() if name in names}
    dicts, _types = compute_cliques_for_impact_report(concords, ids, badxrefs=badxrefs)
    return cliques_without_pmids(dicts), sum(1 for curie in dicts if is_pmid(curie))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("intermediate", type=Path, help="A build's intermediate/ directory (needs disease/).")
    args = parser.parse_args(argv)
    concords_dir = args.intermediate / "disease" / "concords"
    ids_dir = args.intermediate / "disease" / "ids"

    efo_rows = read_rows(concords_dir / "EFO")
    print("# 1. EFO concord targets by prefix (predicate, prefix, rows)")
    by_prefix = Counter((pred, (obj.split(":", 1)[0] if ":" in obj else obj)) for _subj, pred, obj in efo_rows)
    for (pred, prefix), n in sorted(by_prefix.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{pred}\t{prefix}\t{n}")

    pmid_cites = Counter(obj.strip() for _subj, _pred, obj in efo_rows if is_pmid(obj))
    print("\n# 2. EFO PMID xrefs")
    print(f"rows\t{sum(pmid_cites.values())}")
    print(f"distinct PMIDs\t{len(pmid_cites)}")
    single = sum(1 for n in pmid_cites.values() if n == 1)
    print(f"PMIDs named by one EFO row (survive the overuse filter)\t{single}")
    print(f"PMIDs named by 2+ EFO rows (dropped by the overuse filter, which counts rows)\t{len(pmid_cites) - single}")

    print("\n# 4. EFO PMIDs that another disease concord also names")
    shared = Counter()
    for other in sorted(p for p in concords_dir.iterdir() if p.is_file() and p.name != "EFO"):
        if other.name.startswith("metadata"):
            continue
        for row in read_rows(other):
            for curie in (row[0], row[-1]):
                if is_pmid(curie) and curie.strip() in pmid_cites:
                    shared[(other.name, curie.strip())] += 1
    print(f"shared\t{len(shared)}")
    for (name, curie), n in sorted(shared.items()):
        print(f"{name}\t{curie}\t{n}")

    print("\n# 3. Cliques changed by dropping EFO's PMID rows (PMID members ignored)")
    before, pmids_before = replay(concords_dir, ids_dir)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_concords = Path(tmp) / "concords"
        shutil.copytree(concords_dir, tmp_concords)
        with open(tmp_concords / "EFO", "w") as outf:
            for row in efo_rows:
                if not is_pmid(row[-1]):
                    outf.write("\t".join(row) + "\n")
        after, pmids_after = replay(tmp_concords, ids_dir)
    only_before, only_after = before - after, after - before
    # Shows the replay is sensitive: the PMIDs really did reach glom() as clique members.
    print(f"PMID members of cliques before\t{pmids_before}")
    print(f"PMID members of cliques after\t{pmids_after}")
    print(f"cliques before\t{len(before)}")
    print(f"cliques after\t{len(after)}")
    print(f"only before\t{len(only_before)}")
    print(f"only after\t{len(only_after)}")
    for members in sorted(sorted(c) for c in only_before)[:20]:
        print("before:\t" + " ".join(members))
    for members in sorted(sorted(c) for c in only_after)[:20]:
        print("after:\t" + " ".join(members))
    if only_before or only_after:
        raise SystemExit("Dropping EFO's PMID xrefs changed cliques; see the rows above.")


if __name__ == "__main__":
    main()
