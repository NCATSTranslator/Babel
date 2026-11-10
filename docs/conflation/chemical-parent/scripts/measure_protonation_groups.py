"""Measure the ChemicalParent conflation's charge-state groups over a published build's DuckDB Edge tables.

It runs the production grouping, ``chemicalparent.group_cliques_by_parent_key()``, over every chemical clique that
has an ``INCHIKEY:`` member, and reports how many groups it makes, which compendia they span, whether each has a neutral
form to lead it, and how they overlap the build's DrugChemical conflation. That last part matters because NodeNorm
applies each conflation by a single lookup on the queried clique and does not follow one conflation into another:
a charge-state group whose members sit in *different* DrugChemical groups gives different answers depending on
which member was queried.

To keep memory small, SQL first narrows the input to cliques whose InChIKey parent key (the key without its final
protonation block) is shared with another clique; only those can group. The SQL's notion of "shared" counts every
clique, so the candidate set is a superset and the production function makes the actual decision. Totals over all
InChIKey cliques come from SQL.

Inputs: the build's per-compendium ``Edge.parquet`` for every chemical compendium, and its ``conflation/
DrugChemical.txt``. Example (``<build-url>`` is e.g. ``https://stars.renci.org/var/babel/2025dec11``)::

    mkdir -p data/chemicalparent/edge-<build>
    for f in SmallMolecule MolecularMixture ChemicalEntity Drug ChemicalMixture ComplexMolecularMixture \\
             Polypeptide; do
        curl -fL -o data/chemicalparent/edge-<build>/$f.parquet \\
            "<build-url>/duckdb/parquet/filename%3D$f/Edge.parquet"
    done
    curl -fL -o data/chemicalparent/DrugChemical-<build>.txt <build-url>/conflation/DrugChemical.txt
    uv run python docs/conflation/chemical-parent/scripts/measure_protonation_groups.py \\
        --edge-dir data/chemicalparent/edge-<build> --drugchemical data/chemicalparent/DrugChemical-<build>.txt \\
        --build <build> --output docs/conflation/chemical-parent/<build>.md

Food.txt is missing from builds before it became a chemical output; any ``*.parquet`` in ``--edge-dir`` is read.
"""

import argparse
import glob
import json
import os
import sys
import textwrap
from collections import Counter

import duckdb

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from src.createcompendia.chemicalparent import (  # noqa: E402
    NEUTRAL_PROTONATION_FLAG,
    group_cliques_by_parent_key,
)

# CURIEs from issue #1173's charge-state examples (valproic acid/valproate, folic acid/folate(2-),
# doxorubicin/doxorubicin(1+)). Each pair should end up in one group.
ISSUE_1173_EXAMPLE_PAIRS = [
    ("CHEBI:39867", "CHEBI:60654"),
    ("CHEBI:27470", "CHEBI:62501"),
    ("CHEBI:28748", "CHEBI:64816"),
]

# How many example groups to list for each table of examples: enough to eyeball, few enough to read.
EXAMPLE_COUNT = 15


def load_drugchemical(filename):
    """Map each clique leader in a DrugChemical conflation file to the index of its conflation group."""
    group_of = {}
    with open(filename) as f:
        for i, line in enumerate(f):
            for leader in json.loads(line):
                group_of[leader] = i
    return group_of


def md_table(header, rows):
    """Render a Markdown table."""
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--edge-dir", required=True, help="Directory of chemical compendia Edge parquet files")
    parser.add_argument("--drugchemical", required=True, help="The build's DrugChemical.txt conflation file")
    parser.add_argument("--build", required=True, help="Build name, for the report heading")
    parser.add_argument("--output", required=True, help="Markdown report to write")
    args = parser.parse_args()

    parquets = sorted(glob.glob(os.path.join(args.edge_dir, "*.parquet")))
    if not parquets:
        raise RuntimeError(f"No parquet files in {args.edge_dir}")
    con = duckdb.connect()
    con.execute(
        # Older Edge tables have no curie_prefix or biolink_type column, so match the prefix by string and take
        # each clique's compendium from the file it came from.
        "CREATE TEMP TABLE ik AS SELECT clique_leader, curie, "
        "regexp_extract(filename, '([^/]+)\\.parquet$', 1) AS compendium, substr(curie, 10, 25) AS parent "
        "FROM read_parquet(?, filename = true) WHERE curie LIKE 'INCHIKEY:%'",
        [parquets],
    )

    totals = dict(
        zip(
            ["inchikey_rows", "cliques_with_inchikey", "distinct_parent_keys"],
            con.execute("SELECT count(*), count(DISTINCT clique_leader), count(DISTINCT parent) FROM ik").fetchone(),
        )
    )
    multi_key = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE n_parent > 1) FROM "
        "(SELECT clique_leader, count(DISTINCT parent) AS n_parent FROM ik GROUP BY 1 HAVING count(*) > 1)"
    ).fetchone()
    malformed = con.execute(
        "SELECT count(*) FROM ik WHERE NOT regexp_full_match(curie, 'INCHIKEY:[A-Z]{14}-[A-Z]{8}[SN][A-Z]-[A-Z]')"
    ).fetchone()[0]
    malformed_examples = [
        r[0]
        for r in con.execute(
            "SELECT curie FROM ik WHERE NOT regexp_full_match(curie, 'INCHIKEY:[A-Z]{14}-[A-Z]{8}[SN][A-Z]-[A-Z]') "
            "ORDER BY curie LIMIT 10"
        ).fetchall()
    ]
    if malformed:
        # split_inchikey() raises on these, so they must be excluded for the replay to run; the report says so.
        con.execute("DELETE FROM ik WHERE NOT regexp_full_match(curie, 'INCHIKEY:[A-Z]{14}-[A-Z]{8}[SN][A-Z]-[A-Z]')")

    candidates = con.execute(
        "WITH shared AS (SELECT parent FROM ik GROUP BY parent HAVING count(DISTINCT clique_leader) > 1), "
        "cand AS (SELECT DISTINCT clique_leader FROM ik JOIN shared USING (parent)) "
        "SELECT clique_leader, list(curie ORDER BY curie), any_value(compendium) "
        "FROM ik JOIN cand USING (clique_leader) GROUP BY clique_leader ORDER BY clique_leader"
    ).fetchall()
    compendium_of = {leader: comp for leader, _, comp in candidates}
    groups, counts = group_cliques_by_parent_key((leader, keys) for leader, keys, _ in candidates)

    # Where #1173's example CURIEs landed.
    example_curies = [c for pair in ISSUE_1173_EXAMPLE_PAIRS for c in pair]
    leader_of = dict(
        con.execute(
            "SELECT curie, clique_leader FROM read_parquet(?) WHERE curie IN (SELECT unnest(?))",
            [parquets, example_curies],
        ).fetchall()
    )
    group_of_leader = {leader: parent for parent, members in groups.items() for leader, _ in members}

    drugchemical = load_drugchemical(args.drugchemical)

    sizes = Counter(len(m) for m in groups.values())
    flag_combos = Counter("".join(sorted(f for _, flags in members for f in flags)) for members in groups.values())
    compendium_combos = Counter(
        " + ".join(sorted({compendium_of[leader] for leader, _ in members})) for members in groups.values()
    )
    no_neutral = [p for p, m in groups.items() if not any(NEUTRAL_PROTONATION_FLAG in f for _, f in m)]
    several_neutral = [p for p, m in groups.items() if sum(NEUTRAL_PROTONATION_FLAG in f for _, f in m) > 1]

    dc_overlap = Counter()
    split_by_dc = []
    for parent, members in sorted(groups.items()):
        dc_groups = {drugchemical[leader] for leader, _ in members if leader in drugchemical}
        in_dc = sum(1 for leader, _ in members if leader in drugchemical)
        if in_dc == 0:
            dc_overlap["no member in DrugChemical"] += 1
        elif len(dc_groups) > 1:
            dc_overlap["members in two or more different DrugChemical groups"] += 1
            split_by_dc.append(parent)
        elif in_dc == len(members):
            dc_overlap["every member already in the same DrugChemical group"] += 1
        else:
            dc_overlap["some members in one DrugChemical group, others in none"] += 1

    out = [f"# ChemicalParent charge-state groups in {args.build}", ""]
    out.append(
        textwrap.fill(
            f"Generated by `docs/conflation/chemical-parent/scripts/measure_protonation_groups.py` from the "
            f"{args.build} chemical `Edge.parquet` files ({', '.join(os.path.basename(p) for p in parquets)}) "
            f"and `DrugChemical.txt`. Groups come from the production "
            f"`chemicalparent.group_cliques_by_parent_key()`.",
            width=100,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )
    out += ["", "## InChIKeys in the chemical compendia", ""]
    out.append(
        md_table(
            ["Measure", "Count"],
            [
                ["`INCHIKEY:` identifiers", f"{totals['inchikey_rows']:,}"],
                ["Cliques with at least one InChIKey", f"{totals['cliques_with_inchikey']:,}"],
                ["Distinct parent keys (InChIKey minus protonation block)", f"{totals['distinct_parent_keys']:,}"],
                ["Cliques with several InChIKeys", f"{multi_key[0]:,}"],
                ["... of which with several parent keys (left out)", f"{multi_key[1]:,}"],
                ["Malformed `INCHIKEY:` identifiers (excluded here; the build raises)", f"{malformed:,}"],
            ],
        )
    )
    if malformed_examples:
        out += ["", "Malformed examples: " + ", ".join(f"`{c}`" for c in malformed_examples)]

    out += ["", "## Groups", ""]
    out.append(
        md_table(
            ["Measure", "Count"],
            [
                ["Groups (parent key shared by 2+ cliques)", f"{counts['groups']:,}"],
                ["Cliques in groups", f"{counts['cliques_in_groups']:,}"],
                ["Groups with a neutral (`-N`) member", f"{counts['groups_with_neutral_member']:,}"],
                ["Groups with no neutral member", f"{len(no_neutral):,}"],
                ["Groups with more than one neutral member", f"{len(several_neutral):,}"],
            ],
        )
    )
    out += ["", "### Group sizes", ""]
    out.append(md_table(["Cliques in group", "Groups"], [[k, f"{v:,}"] for k, v in sorted(sizes.items())]))
    out += ["", "### Protonation characters in a group (most common)", ""]
    out.append(
        md_table(["Characters", "Groups"], [[f"`{k}`", f"{v:,}"] for k, v in flag_combos.most_common(EXAMPLE_COUNT)])
    )
    out += ["", "### Compendia a group's members come from (most common)", ""]
    out.append(
        md_table(["Compendia", "Groups"], [[k, f"{v:,}"] for k, v in compendium_combos.most_common(EXAMPLE_COUNT)])
    )

    out += ["", "## Overlap with DrugChemical", ""]
    out.append(md_table(["Charge-state group", "Groups"], [[k, f"{v:,}"] for k, v in dc_overlap.most_common()]))
    if split_by_dc:
        out += ["", "Examples of groups whose members are in different DrugChemical groups:", ""]
        rows = []
        for parent in split_by_dc[:EXAMPLE_COUNT]:
            rows.append(
                [
                    f"`{parent}`",
                    ", ".join(f"`{leader}` (DC {drugchemical.get(leader, '-')})" for leader, _ in groups[parent]),
                ]
            )
        out.append(md_table(["Parent key", "Members"], rows))

    out += ["", "## Issue #1173 examples", ""]
    rows = []
    for a, b in ISSUE_1173_EXAMPLE_PAIRS:
        la, lb = leader_of.get(a), leader_of.get(b)
        ga, gb = group_of_leader.get(la), group_of_leader.get(lb)
        same = ga is not None and ga == gb
        rows.append([f"`{a}` → `{la}`", f"`{b}` → `{lb}`", "yes" if same else f"no ({ga} / {gb})"])
    out.append(md_table(["CURIE → clique", "CURIE → clique", "Same group?"], rows))

    out += ["", "## Example groups", ""]
    rows = [
        [f"`{p}`", ", ".join(f"`{leader}` ({''.join(sorted(f))})" for leader, f in groups[p])]
        for p in sorted(groups)[:EXAMPLE_COUNT]
    ]
    out.append(md_table(["Parent key", "Members (protonation)"], rows))
    out.append("")

    with open(args.output, "w") as f:
        f.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
