"""Replay the UMLS-UNII concord (chemicals.build_umls_unii_relationships) over a published build's cliques.

It rebuilds chemicals' ``ids/UMLS`` with the ownership rules (the build may predate them), runs the production
concord builder against it and the build's ``chemicals/ids/UNII``, and classifies every pair it writes against
the build's finished chemical cliques: already one clique, refused by glom()'s INCHIKEY guard (both cliques
carry a structure), or a merge. The merges are then grouped transitively, so the report can say how large the
resulting cliques are and whether any group strings together cliques with different structures -- the two
ways a new concord over-gloms.

The clique membership comes from the build's ``duckdb/Edge.parquet`` files, not from its concords: glom() is
transitive, so only finished cliques say what an edge joins. Two limits: ``Drug.txt`` and ``Food.txt`` carry
no INCHIKEY CURIEs, so a clique in them counts as having no structure; and a pair is judged against cliques
built without it, so confirm with babel-clique-diff after a build.

Inputs: ``fetch_build_inputs.py`` (in ``../../cui-follows-mesh/scripts``) exports the ids files; the Edge
parquet files are read from a local copy or over https; UMLS and the UNII records are local downloads.

    uv run python docs/sources/UMLS/umls-unii/scripts/replay_umls_unii.py \\
        --ids-dir data/duplicate-curies/ids \\
        --edge-parquet '<build-url>/duckdb/*/Edge.parquet' \\
        --output-dir docs/sources/UMLS/umls-unii --full-csv data/umls-unii/merges.csv

It writes ``<build>.md`` and ``<build>-merges-top-200.csv``, the merging pairs ranked so that the ones most
likely to be wrong come first.
"""

import argparse
import csv
import os
import re
import sys
import tempfile
import textwrap
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "cui-follows-mesh", "scripts")))

import replay_mesh_ownership as mesh_replay  # noqa: E402

from src.createcompendia import chemicals  # noqa: E402
from src.datahandlers import umls  # noqa: E402
from src.datahandlers.unii import read_unii_records  # noqa: E402
from src.prefixes import INCHIKEY  # noqa: E402
from src.util import get_config  # noqa: E402

# Rows of the ranked merge sample committed beside the report; --full-csv writes them all.
MERGES_CSV_ROWS = 200


def load_cliques(edge_parquet, curies):
    """For the cliques holding any of ``curies``: curie -> leader, and leader -> (size, has INCHIKEY, type)."""
    import duckdb

    con = duckdb.connect()
    if edge_parquet.startswith("http"):
        con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("CREATE TEMP TABLE wanted(curie VARCHAR)")
    con.executemany("INSERT INTO wanted VALUES (?)", [(c,) for c in curies])
    con.execute(
        f"""CREATE TEMP TABLE loc AS
            SELECT DISTINCT e.curie, e.clique_leader FROM read_parquet('{edge_parquet}') e
            JOIN wanted w ON w.curie = e.curie WHERE e.conflation = 'None'"""
    )
    leader_of = defaultdict(set)
    for curie, leader in con.execute("SELECT curie, clique_leader FROM loc").fetchall():
        leader_of[curie].add(leader)
    cliques = {}
    for leader, size, keyed, biolink_type in con.execute(
        f"""SELECT clique_leader, count(DISTINCT curie), bool_or(curie LIKE '{INCHIKEY}:%'), any_value(biolink_type)
            FROM read_parquet('{edge_parquet}')
            WHERE conflation = 'None' AND clique_leader IN (SELECT clique_leader FROM loc) GROUP BY 1"""
    ).fetchall():
        cliques[leader] = (size, keyed, biolink_type)
    return leader_of, cliques


def normalized(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def spread(rows, n):
    """n rows spread across the list rather than its first n."""
    step = max(1, len(rows) // n)
    return rows[::step][:n]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cfg = get_config()
    ap.add_argument("--umls-dir", default=os.path.join(cfg["download_directory"], "UMLS"))
    ap.add_argument(
        "--unii-records", default=os.path.join(cfg["download_directory"], "UNII", "Latest_UNII_Records.txt")
    )
    ap.add_argument("--ids-dir", required=True, help="Directory with <pipeline>/{MESH,UMLS,DRUGBANK,UNII} ids files")
    ap.add_argument("--edge-parquet", required=True, help="Glob or URL of the build's chemical Edge.parquet files")
    ap.add_argument("--build", default="2026jul22")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--full-csv", help="Also write every merging pair here (about 2 MB; not committed)")
    args = ap.parse_args()

    mrconso = os.path.join(args.umls_dir, "MRCONSO.RRF")
    mesh_pipelines = cfg["umls_mesh_owning_pipelines"]
    with tempfile.TemporaryDirectory() as tmpdir:
        non_mesh = [mesh_replay.run_writer(p, args.umls_dir, tmpdir, None) for p in ["gene", "process"]]
        ownership = os.path.join(tmpdir, "ownership.tsv")
        # The same call rule umls_mesh_ownership makes.
        umls.write_mesh_ownership(
            mrconso,
            {p: os.path.join(args.ids_dir, p, "MESH") for p in mesh_pipelines},
            ownership,
            blocklist_files_by_pipeline={"disease": os.path.join(cfg["input_directory"], "badumls")},
            non_mesh_umls_ids_files=non_mesh,
            drugbank_ids_files_by_pipeline={
                p: os.path.join(args.ids_dir, p, "DRUGBANK") for p in cfg["umls_drugbank_owning_pipelines"]
            },
        )
        umls_ids = mesh_replay.run_writer("chemicals", args.umls_dir, tmpdir, ownership)
        concord = os.path.join(tmpdir, "UMLS_UNII")
        # The same call rule get_chemical_umls_unii_relationships makes.
        outcome = chemicals.build_umls_unii_relationships(
            mrconso,
            args.unii_records,
            umls_ids,
            os.path.join(args.ids_dir, "chemicals", "UNII"),
            concord,
            os.path.join(tmpdir, "metadata.yaml"),
        )
        with open(concord) as inf:
            pairs = [tuple(line.rstrip("\n").split("\teq\t")) for line in inf]

    unii_name = {f"UNII:{row['UNII']}": row["DISPLAY_NAME"] for row in read_unii_records(args.unii_records)}
    unii_kind = {f"UNII:{row['UNII']}": row["SUBSTANCE_TYPE"] for row in read_unii_records(args.unii_records)}
    cui_name = {}
    wanted = {cui for cui, _ in pairs}
    with open(mrconso) as inf:
        for line in inf:
            x = line.split("|")
            # The concept's preferred English name: TS=P, STT=PF, ISPREF=Y.
            if x[1] == "ENG" and x[2] == "P" and x[4] == "PF" and x[6] == "Y" and f"UMLS:{x[0]}" in wanted:
                cui_name.setdefault(f"UMLS:{x[0]}", x[14])

    leader_of, cliques = load_cliques(args.edge_parquet, [c for pair in pairs for c in pair])

    def clique_of(curie):
        """The curie's clique leader, or the curie itself standing for a new single-member clique."""
        leaders = leader_of.get(curie)
        if not leaders:
            cliques.setdefault(curie, (1, False, "(not in the build's chemical compendia)"))
            return curie
        return sorted(leaders)[0]

    verdicts = Counter()
    merges = []
    for cui, unii in pairs:
        a, b = clique_of(cui), clique_of(unii)
        if a == b:
            verdicts["already in one clique"] += 1
        elif cliques[a][1] and cliques[b][1]:
            verdicts["refused: both cliques have a structure"] += 1
        else:
            if cui not in leader_of:
                verdicts["merge: CUI newly in chemicals joins the UNII's clique"] += 1
            elif unii not in leader_of:
                verdicts["merge: UNII in no chemical clique joins the CUI's clique"] += 1
            else:
                verdicts["merge: joins two existing cliques"] += 1
            merges.append((cui, unii, a, b))

    # Group the merges transitively.
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, _, a, b in merges:
        parent[find(a)] = find(b)
    groups = defaultdict(set)
    group_edges = defaultdict(list)
    for cui, unii, a, b in merges:
        groups[find(a)] |= {a, b}
        group_edges[find(a)].append((cui, unii))

    def group_size(members):
        return sum(cliques[m][0] for m in members)

    def group_keyed(members):
        return sum(1 for m in members if cliques[m][1])

    lines = [f"# Replaying the UMLS-UNII concord over the {args.build} build", ""]
    lines.append(
        "Generated by `docs/sources/UMLS/umls-unii/scripts/replay_umls_unii.py` (see its docstring). UMLS from "
        f"`babel_downloads/UMLS`, UNII records from `babel_downloads/UNII`; ids files and cliques from the {args.build} "
        "build, with chemicals' `ids/UMLS` rebuilt under the MeSH and DrugBank ownership rules."
    )
    lines += ["", "## What the concord builder keeps", "", "| candidate CUI-UNII pairs | count |", "|---|---:|"]
    for reason, n in sorted(outcome.items(), key=lambda kv: (kv[0] != "written", -kv[1])):
        lines.append(f"| {reason} | {n:,} |")
    lines += ["", "## What the written pairs do to the build's cliques", "", "| effect | pairs |", "|---|---:|"]
    for verdict, n in sorted(verdicts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {verdict} | {n:,} |")

    by_cliques = Counter(len(m) for m in groups.values())
    by_keyed = Counter(group_keyed(m) for m in groups.values())
    lines += [
        "",
        "## How far the merges reach",
        "",
        f"The {len(merges):,} merging pairs form {len(groups):,} groups of cliques that end up as one clique.",
        "",
        "| cliques joined | groups |",
        "|---:|---:|",
    ]
    lines += [f"| {k} | {n:,} |" for k, n in sorted(by_cliques.items())]
    lines += ["", "| cliques with a structure in the group | groups |", "|---:|---:|"]
    lines += [f"| {k} | {n:,} |" for k, n in sorted(by_keyed.items())]
    lines += [
        "",
        "A group with two or more structures cannot become one clique: glom() refuses whichever pair would put "
        "a second INCHIKEY into a clique, so which side the structureless member joins depends on concord order.",
        "",
        "The ten largest resulting cliques:",
        "",
        "| identifiers | cliques joined | with a structure | pairs (CUI = UNII) |",
        "|---:|---:|---:|---|",
    ]
    for root, members in sorted(groups.items(), key=lambda kv: -group_size(kv[1]))[:10]:
        shown = "; ".join(
            f'{cui} "{cui_name.get(cui, "")}" = {unii} "{unii_name.get(unii, "")}"'
            for cui, unii in group_edges[root][:3]
        )
        lines.append(f"| {group_size(members):,} | {len(members)} | {group_keyed(members)} | {shown} |")

    same_name = [m for m in merges if normalized(cui_name.get(m[0])) == normalized(unii_name.get(m[1]))]
    different = [m for m in merges if m not in set(same_name)]
    lines += [
        "",
        "## Do the merged pairs name the same thing?",
        "",
        f"{len(same_name):,} of the {len(merges):,} merging pairs have the same name once case and punctuation are "
        f"removed. Ten of the other {len(different):,}, spread across the list:",
        "",
        "| CUI | UMLS name | UNII | FDA name |",
        "|---|---|---|---|",
    ]
    for cui, unii, _, _ in spread(sorted(different), 10):
        lines.append(f"| {cui} | {cui_name.get(cui, '')} | {unii} | {unii_name.get(unii, '')} |")
    kinds = Counter(unii_kind.get(unii) or "(none)" for _, unii, _, _ in merges)
    lines += ["", "FDA substance type of the merging UNIIs:", "", "| substance type | pairs |", "|---|---:|"]
    lines += [f"| {kind} | {n:,} |" for kind, n in kinds.most_common()]

    def wrap(line):
        if not line or line.startswith(("|", "#")):
            return line
        return textwrap.fill(line, width=100, break_long_words=False, break_on_hyphens=False)

    os.makedirs(args.output_dir, exist_ok=True)
    report = os.path.join(args.output_dir, f"{args.build}.md")
    with open(report, "w") as outf:
        outf.write("\n".join(wrap(line) for line in lines).rstrip("\n") + "\n")

    # The merging pairs most worth a reviewer's eye, ranked before the cut: groups holding two structures, then
    # groups of three or more cliques, then pairs whose names differ, each by the size of the resulting clique.
    header = (
        ["group", "cliques_joined", "cliques_with_structure", "identifiers", "names_match", "cui", "umls_name"]
        + ["unii", "fda_name", "fda_substance_type", "cui_clique", "cui_clique_type", "unii_clique"]
        + ["unii_clique_type"]
    )
    ranked = sorted(groups, key=lambda r: (-group_keyed(groups[r]), -len(groups[r]), -group_size(groups[r]), r))
    rank = {root: i + 1 for i, root in enumerate(ranked)}
    rows = []
    for cui, unii, a, b in merges:
        members = groups[find(a)]
        match = normalized(cui_name.get(cui)) == normalized(unii_name.get(unii))
        rows.append(
            [rank[find(a)], len(members), group_keyed(members), group_size(members), match, cui, cui_name.get(cui, "")]
            + [unii, unii_name.get(unii, ""), unii_kind.get(unii, ""), a, cliques[a][2], b, cliques[b][2]]
        )
    rows.sort(key=lambda r: (r[2] < 2, r[1] < 3, r[4], -r[3], r[0], r[5]))
    merges_csv = os.path.join(args.output_dir, f"{args.build}-merges-top-{MERGES_CSV_ROWS}.csv")
    outputs = [(merges_csv, rows[:MERGES_CSV_ROWS])]
    if args.full_csv:
        outputs.append((args.full_csv, rows))
    for path, selected in outputs:
        with open(path, "w", newline="") as outf:
            writer = csv.writer(outf)
            writer.writerow(header)
            writer.writerows(selected)
    print(f"Wrote {report} and {merges_csv}")  # noqa: T201


if __name__ == "__main__":
    main()
