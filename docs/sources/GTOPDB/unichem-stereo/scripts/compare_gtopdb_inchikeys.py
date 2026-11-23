"""Compare the InChIKey GtoPdb gives each ligand with the one UniChem gives it, in one Babel build.

Babel used to write two structure concords for GtoPdb: `concords/GTOPDB`, from GtoPdb's own
ligands.tsv, and `concords/UNICHEM/UNICHEM_GTOPDB`, from UniChem source 4. This script classifies
every ligand in both by how the two keys differ, and (with the build's DuckDB exports) says where
each ligand whose keys differ sits in the build and where its own key would put it. It is the
evidence for reading GtoPdb structures from GtoPdb only (#1206); see ../README.md.

Usage, from the repository root (a build is a local directory or an https:// URL of one):

    D=docs/sources/GTOPDB/unichem-stereo
    uv run python $D/scripts/compare_gtopdb_inchikeys.py --build <build> --label 2026jul22 \\
        --csv $D/differing-ligands-2026jul22-top-300.csv --csv-limit 300 > $D/report-2026jul22.md

The committed CSV is a ranked sample (see select_csv_rows()); leave out --csv-limit, and write to a
file under data/, for every ligand.

A build written after #1206 has no UNICHEM_GTOPDB concord. To re-check UniChem then, put source "4"
back into unichem.data_sources and GTOPDB back into config.yaml: unichem_datasources locally, and run

    uv run snakemake -c all --scheduler greedy get_chemical_unichem_relationships

The changed source list re-runs rule filter_unichem (it is the rule's params), so the filtered
reference file regains GtoPdb's rows and the concord is rewritten from them.
"""

import argparse
import collections
import csv
import os
import sys
import tempfile
import urllib.parse
import urllib.request

import duckdb

from src.model.intermediates import read_concords
from src.util import get_config

# The InChIKey second block of a structure with no stereo, isotope or other minor layers: the hash of
# an empty string. A key carrying it is what this report calls "stereo-less".
NO_STEREO_BLOCK = "UHFFFAOYSA"


def is_url(location):
    return location.startswith(("http://", "https://"))


def join(build, *parts):
    """Join a build location (directory or URL) and path parts, percent-encoding URL parts."""
    if is_url(build):
        return build.rstrip("/") + "/" + "/".join(urllib.parse.quote(p, safe="") for p in parts)
    return os.path.join(build, *parts)


def read_structure_concord(location, workdir):
    """Read an identifier -> INCHIKEY concord into a dict, fetching it first if it is a URL."""
    path = location
    if is_url(location):
        path = os.path.join(workdir, urllib.parse.quote(location, safe=""))
        urllib.request.urlretrieve(location, path)
    keys = {}
    for subj, _pred, obj in read_concords(path):
        if subj in keys and keys[subj] != obj:
            raise ValueError(f"{subj} has two InChIKeys in {location}: {keys[subj]} and {obj}")
        keys[subj] = obj
    return keys


def classify(own, unichem):
    """Say how GtoPdb's own key differs from UniChem's. Keys look like INCHIKEY:AAAA-BBBB-C."""
    if own == unichem:
        return "Same key"
    own_skeleton, own_rest, own_charge = own.split(":", 1)[1].split("-")
    uc_skeleton, uc_rest, uc_charge = unichem.split(":", 1)[1].split("-")
    if own_skeleton != uc_skeleton:
        return "Different skeleton"
    if own_rest == uc_rest:
        return "Same skeleton and stereo; charge flag only"
    own_flat = own_rest.startswith(NO_STEREO_BLOCK)
    uc_flat = uc_rest.startswith(NO_STEREO_BLOCK)
    if uc_flat and not own_flat:
        return "Same skeleton; UniChem stereo-less, GtoPdb specific"
    if own_flat and not uc_flat:
        return "Same skeleton; GtoPdb stereo-less, UniChem specific"
    return "Same skeleton; two different stereo layers"


def share_stereo_less(keys):
    flat = sum(1 for k in keys.values() if k.split("-")[1].startswith(NO_STEREO_BLOCK))
    return f"{flat:,} of {len(keys):,} ({100 * flat / len(keys):.1f}%)"


def shared_keys(keys):
    """(number of keys given to more than one ligand, number of ligands on such keys)."""
    counts = collections.Counter(keys.values())
    return sum(1 for n in counts.values() if n > 1), sum(n for n in counts.values() if n > 1)


def clique_moves(build, differing):
    """For each ligand whose keys differ, find its clique in the build and the clique of its own key.

    :param differing: {ligand CURIE: GtoPdb's own INCHIKEY CURIE}.
    :return: {ligand CURIE: (clique leader now, leader of the clique holding its own key, members of
        the clique it is in now)}; a leader is None when the CURIE is in no chemical clique.
    """
    types = [name.removesuffix(".txt") for name in get_config()["chemical_outputs"]]
    edges = [join(build, "duckdb", "parquet", f"filename={t}", "Edge.parquet") for t in types]
    con = duckdb.connect()
    if is_url(build):
        con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("CREATE TABLE ligand (curie VARCHAR, own_key VARCHAR)")
    con.executemany("INSERT INTO ligand VALUES (?, ?)", list(differing.items()))
    con.execute(
        "CREATE TABLE edge AS SELECT clique_leader, curie FROM read_parquet(?) "
        "WHERE curie IN (SELECT curie FROM ligand) OR curie IN (SELECT own_key FROM ligand)",
        [edges],
    )
    # Clique sizes need a second pass over just the cliques the ligands are in now.
    con.execute(
        "CREATE TABLE clique_size AS SELECT clique_leader, count(*) AS members FROM read_parquet(?) "
        "WHERE clique_leader IN (SELECT clique_leader FROM edge WHERE curie IN (SELECT curie FROM ligand)) "
        "GROUP BY clique_leader",
        [edges],
    )
    rows = con.execute(
        """
        SELECT l.curie, now.clique_leader, target.clique_leader, s.members
        FROM ligand l
        LEFT JOIN edge now ON now.curie = l.curie
        LEFT JOIN edge target ON target.curie = l.own_key
        LEFT JOIN clique_size s ON s.clique_leader = now.clique_leader
        ORDER BY l.curie
        """
    ).fetchall()
    return {ligand: (now, target, members) for ligand, now, target, members in rows}


def summarise_moves(moves):
    """Count the outcomes of clique_moves(), and pick examples spread across the ligands that move."""
    outcomes = collections.Counter()
    movers = []
    for ligand, (now, target, members) in moves.items():
        if now is None:
            outcomes["Ligand is in no chemical clique in this build"] += 1
        elif target is None:
            outcomes["Own key is in no clique: the ligand and its key become a new clique"] += 1
        elif target == now:
            outcomes["Own key is already in the ligand's clique"] += 1
        else:
            outcomes["Own key is in another clique: the ligand joins it"] += 1
            movers.append((ligand, now, target))
        # The ligand, its UniChem key and nothing else: without the ligand the clique no longer exists.
        if now is not None and target != now and members == 2:
            outcomes["Of the ligands that leave their clique: it held only the ligand and its UniChem key"] += 1
    step = max(1, len(movers) // 8)
    return outcomes, movers[::step][:8]


# The difference between the two keys that almost every differing ligand shows (5,728 of 5,817 in
# 2026jul22), and so the one select_csv_rows() samples rather than lists in full.
COMMON_DIFFERENCE = "Same skeleton; UniChem stereo-less, GtoPdb specific"


def select_csv_rows(rows, limit=None, with_cliques=True):
    """Order the CSV rows so the ones that would change a reviewer's mind come first, then cap them.

    Every row that is not the ordinary case comes first, in this order: a difference other than
    COMMON_DIFFERENCE (two different stereo layers, a different skeleton), a ligand whose own key is
    in no clique (it would form a new one), and a ligand in no clique now. The ordinary rows -- a
    stereo-less UniChem key, and a ligand that joins the existing clique of its own key -- fill the
    rest of the cap, spread evenly across them in CURIE order rather than taken from the start, so
    the sample isn't just the lowest ligand IDs. Each group is in CURIE order.

    :param rows: CSV rows as lists, in the column order main() writes.
    :param limit: the most rows to return, or None for all of them.
    :param with_cliques: False when the clique columns are empty (--no-cliques), so that they are
        not read as "in no clique".
    """

    def number(row):
        return int(row[0].split(":")[1])

    def group(row):
        _ligand, _own, _unichem, difference, now, target = row
        if difference != COMMON_DIFFERENCE:
            return 0
        if not with_cliques:
            return 3
        if not target:
            return 1
        if not now:
            return 2
        return 3

    rows = sorted(rows, key=lambda row: (group(row), number(row)))
    unusual = [row for row in rows if group(row) < 3]
    ordinary = [row for row in rows if group(row) == 3]
    if limit is None or len(rows) <= limit:
        return rows
    room = max(0, limit - len(unusual))
    step = len(ordinary) / room if room else 0
    return unusual[:limit] + [ordinary[int(i * step)] for i in range(room)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", required=True, help="Build directory or URL (holding intermediate/ and duckdb/).")
    parser.add_argument("--label", required=True, help="Build name to print; the location itself is never printed.")
    parser.add_argument("--no-cliques", action="store_true", help="Skip the clique analysis (no duckdb/ exports).")
    parser.add_argument("--csv", help="Write one row per ligand whose two keys differ to this file.")
    parser.add_argument(
        "--csv-limit", type=int, help="Write at most this many CSV rows, ranked by select_csv_rows() (default: all)."
    )
    args = parser.parse_args()

    concords = ("intermediate", "chemicals", "concords")
    with tempfile.TemporaryDirectory() as workdir:
        own = read_structure_concord(join(args.build, *concords, "GTOPDB"), workdir)
        unichem = read_structure_concord(join(args.build, *concords, "UNICHEM", "UNICHEM_GTOPDB"), workdir)

    out = sys.stdout
    out.write(f"# GtoPdb's InChIKeys vs. UniChem's in {args.label}\n\n")
    out.write("Written by `compare_gtopdb_inchikeys.py`; do not edit by hand.\n\n")
    out.write("| | GtoPdb's `ligands.tsv` | UniChem source 4 |\n|---|---|---|\n")
    out.write(f"| Ligands with an InChIKey | {len(own):,} | {len(unichem):,} |\n")
    out.write(f"| Stereo-less keys | {share_stereo_less(own)} | {share_stereo_less(unichem)} |\n")
    own_shared, unichem_shared = shared_keys(own), shared_keys(unichem)
    out.write(
        f"| Keys given to more than one ligand | {own_shared[0]:,} keys, {own_shared[1]:,} ligands "
        f"| {unichem_shared[0]:,} keys, {unichem_shared[1]:,} ligands |\n"
    )
    out.write(f"| Ligands only this source has a key for | {len(own.keys() - unichem.keys()):,} ")
    out.write(f"| {len(unichem.keys() - own.keys()):,} |\n\n")

    both = sorted(own.keys() & unichem.keys())
    kinds = collections.Counter(classify(own[ligand], unichem[ligand]) for ligand in both)
    out.write(
        f"## The {len(both):,} ligands with a key from both\n\n| GtoPdb's key vs. UniChem's | Ligands |\n|---|---|\n"
    )
    for kind, count in kinds.most_common():
        out.write(f"| {kind} | {count:,} |\n")

    differing = {ligand: own[ligand] for ligand in both if own[ligand] != unichem[ligand]}
    moves = {}
    if not args.no_cliques:
        moves = clique_moves(args.build, differing)
        outcomes, examples = summarise_moves(moves)
        out.write(f"\n## Where the {len(differing):,} ligands whose keys differ would go\n\n")
        out.write("Read from the build's chemical `Edge.parquet` files: the clique each ligand is in, and the\n")
        out.write("clique that holds GtoPdb's own key for it. The examples are spread evenly across the ligands\n")
        out.write("that would join another clique, in CURIE order.\n\n| Outcome | Ligands |\n|---|---|\n")
        for outcome, count in outcomes.most_common():
            out.write(f"| {outcome} | {count:,} |\n")
        out.write("\n| Ligand | Clique in this build | Clique of its own key |\n|---|---|---|\n")
        for ligand, now, target in examples:
            out.write(f"| `{ligand}` | `{now}` | `{target}` |\n")

    if args.csv:
        rows = []
        for ligand in differing:
            now, target, _members = moves.get(ligand, ("", "", None))
            difference = classify(own[ligand], unichem[ligand])
            rows.append([ligand, own[ligand], unichem[ligand], difference, now or "", target or ""])
        with open(args.csv, "w", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["ligand", "gtopdb_key", "unichem_key", "difference", "clique_now", "clique_of_gtopdb_key"])
            writer.writerows(select_csv_rows(rows, args.csv_limit, with_cliques=not args.no_cliques))


if __name__ == "__main__":
    main()
