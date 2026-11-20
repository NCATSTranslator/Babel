"""Print the clique-level figures quoted in docs/sources/UBERON/umls-joins/README.md for two anatomy builds.

Reads the four anatomy compendia of a baseline and a comparison build and reports: how many UMLS CUIs share
a clique with an UBERON term, how many comparison cliques merge 2, 3, ... baseline cliques, how many
baseline cliques with a UMLS CUI but no UBERON term changed compendium, which CURIEs no anatomy compendium
ships any more, and which UMLS CUIs moved from one UBERON term's clique to another's. babel-clique-diff
gives the per-compendium counts; this answers the questions specific to joining UBERON to UMLS.

With --release-duckdb (the local `duckdb/` directory of a published build), it also checks that no CURIE
the comparison build newly ships in anatomy already sits in one of that build's non-anatomy compendia: two
compendia must never share an identifier.

Usage (from the repository root):

    uv run python docs/sources/UBERON/umls-joins/scripts/compare_builds.py \\
        --before <baseline compendia dir> --after <comparison compendia dir>
"""

import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.prefixes import FMA, UBERON, UMLS

COMPENDIA = ["AnatomicalEntity.txt", "GrossAnatomicalStructure.txt", "Cell.txt", "CellularComponent.txt"]


def read_build(directory):
    """Return ({CURIE: clique index}, [(compendium, [CURIE, ...]), ...]) for one build's anatomy compendia."""
    clique_of, cliques = {}, []
    for name in COMPENDIA:
        with open(Path(directory) / name) as inf:
            for line in inf:
                ids = [x["i"] for x in json.loads(line)["identifiers"]]
                for i in ids:
                    clique_of[i] = len(cliques)
                cliques.append((name, ids))
    return clique_of, cliques


def uberon_of(ids):
    return [i for i in ids if i.startswith(f"{UBERON}:")]


def umls_in_uberon_cliques(cliques):
    return sum(sum(1 for i in ids if i.startswith(f"{UMLS}:")) for _, ids in cliques if uberon_of(ids))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--before", required=True, help="Baseline compendia directory")
    parser.add_argument("--after", required=True, help="Comparison compendia directory")
    parser.add_argument(
        "--release-duckdb", help="A published build's duckdb/ directory, for the cross-compendium check"
    )
    args = parser.parse_args()

    before_of, before = read_build(args.before)
    after_of, after = read_build(args.after)

    print(f"UMLS CUIs in UBERON cliques: {umls_in_uberon_cliques(before)} -> {umls_in_uberon_cliques(after)}")

    sources = defaultdict(set)
    for curie, b in before_of.items():
        if curie in after_of:
            sources[after_of[curie]].add(b)
    merges = Counter(len(bs) for bs in sources.values() if len(bs) > 1)
    print("comparison cliques by number of baseline cliques merged:", dict(sorted(merges.items())))

    moves = Counter()
    for compendium, ids in before:
        if uberon_of(ids) or not any(i.startswith(f"{UMLS}:") for i in ids):
            continue
        destinations = {after[after_of[i]][0] for i in ids if i in after_of}
        for destination in destinations - {compendium}:
            moves[(compendium, destination)] += 1
    print("Baseline cliques with a UMLS CUI but no UBERON term that changed compendium:")
    for (src, dst), n in moves.most_common():
        print(f"  {src} -> {dst}: {n}")

    gross_fma = {
        i for name, ids in after if name == "GrossAnatomicalStructure.txt" for i in ids if i.startswith(f"{FMA}:")
    }
    print(
        f"FMA CURIEs in GrossAnatomicalStructure.txt, which only anatomy_extra_prefixes_by_biolink_class keeps: "
        f"{len(gross_fma)}, of which the baseline ships {len(gross_fma & set(before_of))}"
    )

    dropped = sorted(set(before_of) - set(after_of))
    print(f"CURIEs no anatomy compendium ships any more: {len(dropped)} {dropped}")

    moved = []
    for curie, b in before_of.items():
        if not curie.startswith(f"{UMLS}:") or curie not in after_of:
            continue
        old, new = uberon_of(before[b][1]), uberon_of(after[after_of[curie]][1])
        if old and new and old != new:
            moved.append((curie, old, new))
    print(f"UMLS CUIs that moved from one UBERON term's clique to another's: {len(moved)}")
    for curie, old, new in sorted(moved):
        print(f"  {curie}: {','.join(old)} -> {','.join(new)}")

    if args.release_duckdb:
        new = set(after_of) - set(before_of)
        print(f"CURIEs newly shipped in anatomy: {len(new)}", Counter(c.split(":", 1)[0] for c in new).most_common())
        for name, curies in (("newly shipped", new), ("baseline", set(before_of)), ("comparison", set(after_of))):
            shared = shared_with_other_compendia(args.release_duckdb, curies)
            prefixes = Counter(c.split(":", 1)[0] for _, c in shared).most_common()
            print(f"{name} anatomy CURIEs also in a non-anatomy compendium of the release: {len(shared)} {prefixes}")


def shared_with_other_compendia(release_duckdb, curies):
    """Return sorted [(compendium, CURIE)] for the CURIEs in a published build's non-anatomy compendia."""
    import duckdb

    anatomy = {name.removesuffix(".txt") for name in COMPENDIA}
    edges = [
        path
        for path in sorted(glob.glob(f"{release_duckdb}/parquet/filename=*/Edge.parquet"))
        if Path(path).parent.name.removeprefix("filename=") not in anatomy
    ]
    con = duckdb.connect()
    con.execute("CREATE TABLE wanted (curie VARCHAR)")
    con.executemany("INSERT INTO wanted VALUES (?)", [(c,) for c in curies])
    query = f"SELECT filename, curie FROM read_parquet({edges}, hive_partitioning=true) JOIN wanted USING (curie)"
    return sorted(con.sql(query).fetchall())


if __name__ == "__main__":
    main()
