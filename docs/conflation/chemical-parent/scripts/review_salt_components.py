"""Report how completely the reviewed component list resolves salts and hydrates, and what to review next.

ChemicalParent maps a multi-component record (a salt or hydrate) to its parent when every component but one is
marked ``drop`` in ``input_data/chemical_parent_components.tsv`` (see ``src/createcompendia/inchi_components.py``).
That list is curated by hand, round by round. Each run of this script:

1. takes every multi-component InChI whose InChIKey is in a curated chemical clique (see UNCURATED_PREFIXES);
2. classifies each with the production ``resolve_parent()`` and the current list: *resolved* (one component left),
   *all dropped* (nothing left -- e.g. a bare counterion), or *blocked* (two or more left);
3. ranks the components blocking records that nobody has reviewed yet. A blocker is any remaining component except
   the record's largest (by heavy atoms), which is presumed to be the active part; a component that is the only
   blocker in a record would resolve that record if it were dropped;
4. checks that resolved parents are real: how many parent keys match the parent key of an existing clique;
5. writes the report, and a review sheet of the top unreviewed blockers in the list's own columns with an empty
   ``decision``, ready to fill in and append to the list.

A round is done when the remaining unreviewed blockers are a long tail of rare components; the report's coverage
table is how to judge that.

Inputs: PubChem's ``CID-InChI-Key.gz`` and ``CID-Title.gz`` (``babel_downloads/PUBCHEM.COMPOUND/``), the build's
chemical ``Edge.parquet`` files (see ``measure_protonation_groups.py``), and the component list. The first run
splits every multi-component PubChem InChI with RDKit (an hour or more with the default four processes) and caches that and the
PubChem tables in ``--cache-dir``; later runs take a minute or two. Example::

    uv run python docs/conflation/chemical-parent/scripts/review_salt_components.py \\
        --pubchem-dir babel_downloads/PUBCHEM.COMPOUND --edge-dir data/chemicalparent/edge-2025dec11 \\
        --decisions input_data/chemical_parent_components.tsv --cache-dir data/chemicalparent/salt-cache \\
        --build 2025dec11 --output data/chemicalparent/salt-review.md --sheet data/chemicalparent/salt-sheet.tsv
"""

import argparse
import csv
import glob
import os
import sys
import textwrap

import duckdb

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from src.createcompendia.inchi_components import (  # noqa: E402
    DECISIONS_TSV_HEADER,
    DROP,
    KEEP,
    read_component_decisions,
    resolve_parent,
    write_inchi_components,
)

# Prefixes that don't make a clique "curated". Coverage and the blocker ranking count only cliques with some other
# identifier (ChEMBL, UNII, ChEBI, MeSH, DrugBank, ...): 97% of multi-component records are PubChem-only deposits,
# largely patent-extracted reagent mixtures, whose 3.7M distinct components would never converge as a review list.
# CAS is here too because Babel gets most CAS numbers from PubChem's own synonyms (the PUBCHEM_CAS concord), so a
# CAS number alone adds no outside curation. The list is still applied to every record in the build.
UNCURATED_PREFIXES = {"PUBCHEM.COMPOUND", "INCHIKEY", "CAS"}

# DuckDB limits, so a review run leaves the machine usable.
DUCKDB_MEMORY_LIMIT = "8GB"
DUCKDB_THREADS = 4

# How many unreviewed blockers to list and put on the review sheet per round.
TOP_BLOCKERS = 150

# How many components marked keep to list, to check they block what we expect (metal centres, co-drugs).
TOP_KEEPS = 30


def md_table(header, rows):
    """Render a Markdown table."""
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def fill(text):
    """Wrap a paragraph to the repository's Markdown width."""
    return textwrap.fill(text, width=100, break_long_words=False, break_on_hyphens=False)


def build_cache(pubchem_dir, cache_dir, processes):
    """Create the cached components TSV and PubChem parquet tables if they are missing."""
    os.makedirs(cache_dir, exist_ok=True)
    components = os.path.join(cache_dir, "inchi_components.tsv")
    if not os.path.exists(components):
        write_inchi_components(os.path.join(pubchem_dir, "CID-InChI-Key.gz"), components + ".partial", processes)
        os.rename(components + ".partial", components)
    con = duckdb.connect(config={"memory_limit": DUCKDB_MEMORY_LIMIT, "threads": DUCKDB_THREADS})
    keys = os.path.join(cache_dir, "pubchem_inchikeys.parquet")
    if not os.path.exists(keys):
        con.execute(
            f"COPY (SELECT column0 AS cid, column2 AS inchikey FROM read_csv(?, delim = '\t', header = false, "
            f"quote = '', escape = '', columns = {{'column0': 'BIGINT', 'column1': 'VARCHAR', 'column2': 'VARCHAR'}})) "
            f"TO '{keys}' (FORMAT parquet)",
            [os.path.join(pubchem_dir, "CID-InChI-Key.gz")],
        )
    titles = os.path.join(cache_dir, "pubchem_titles.parquet")
    if not os.path.exists(titles):
        con.execute(
            f"COPY (SELECT column0 AS cid, column1 AS title FROM read_csv(?, delim = '\t', header = false, "
            f"quote = '', escape = '', columns = {{'column0': 'BIGINT', 'column1': 'VARCHAR'}})) "
            f"TO '{titles}' (FORMAT parquet)",
            [os.path.join(pubchem_dir, "CID-Title.gz")],
        )
    return components, keys, titles


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pubchem-dir", required=True, help="Directory holding CID-InChI-Key.gz and CID-Title.gz")
    parser.add_argument("--edge-dir", required=True, help="Directory of chemical compendia Edge parquet files")
    parser.add_argument("--decisions", required=True, help="The reviewed component list")
    parser.add_argument("--cache-dir", required=True, help="Where to cache the RDKit split and PubChem tables")
    parser.add_argument("--build", required=True, help="Build name, for the report heading")
    parser.add_argument("--output", required=True, help="Markdown report to write")
    parser.add_argument("--sheet", required=True, help="Review sheet (TSV) of the top unreviewed blockers to write")
    parser.add_argument(
        "--processes",
        type=int,
        default=4,
        help="Processes for the RDKit split. Kept low by default so the machine stays usable; raise it on a server.",
    )
    args = parser.parse_args()

    parquets = sorted(glob.glob(os.path.join(args.edge_dir, "*.parquet")))
    if not parquets:
        raise RuntimeError(f"No parquet files in {args.edge_dir}")
    components_tsv, keys_parquet, titles_parquet = build_cache(args.pubchem_dir, args.cache_dir, args.processes)
    decisions = read_component_decisions(args.decisions)

    con = duckdb.connect(config={"memory_limit": DUCKDB_MEMORY_LIMIT, "threads": DUCKDB_THREADS})
    con.execute(
        "CREATE TEMP TABLE all_clique_keys AS SELECT clique_leader, substr(curie, 10) AS inchikey "
        "FROM read_parquet(?) WHERE curie LIKE 'INCHIKEY:%'",
        [parquets],
    )
    con.execute(
        "CREATE TEMP TABLE clique_parents AS SELECT DISTINCT substr(inchikey, 1, 25) AS parent FROM all_clique_keys"
    )
    # Review scope: InChIKeys of curated cliques only (see UNCURATED_PREFIXES).
    con.execute(
        "CREATE TEMP TABLE clique_keys AS SELECT DISTINCT inchikey FROM all_clique_keys WHERE clique_leader IN "
        "(SELECT DISTINCT clique_leader FROM read_parquet(?) WHERE split_part(curie, ':', 1) NOT IN "
        "(SELECT unnest(?)))",
        [parquets, sorted(UNCURATED_PREFIXES)],
    )
    con.execute(
        "CREATE TEMP TABLE comp AS SELECT DISTINCT c.inchikey, c.component_inchikey, c.component_heavy_atoms AS heavy, "
        "c.component_inchi, substr(c.component_inchikey, 1, 25) AS component_parent "
        "FROM read_csv(?, delim = '\t', header = true, quote = '', escape = '', all_varchar = false) c "
        "JOIN clique_keys USING (inchikey)",
        [components_tsv],
    )

    # Classify every record with the production rule.
    records = {}
    for inchikey, keys in con.execute(
        "SELECT inchikey, list(component_inchikey ORDER BY component_inchikey) FROM comp GROUP BY 1"
    ).fetchall():
        records[inchikey] = resolve_parent(keys, decisions)
    con.execute("CREATE TEMP TABLE resolved (inchikey VARCHAR, parent VARCHAR)")
    con.executemany("INSERT INTO resolved VALUES (?, ?)", list(records.items()))

    drops = sorted(k for k, d in decisions.items() if d == DROP)
    keeps = sorted(k for k, d in decisions.items() if d == KEEP)
    con.execute("CREATE TEMP TABLE drops (component_parent VARCHAR)")
    con.executemany("INSERT INTO drops VALUES (?)", [(k,) for k in drops])
    con.execute("CREATE TEMP TABLE reviewed (component_parent VARCHAR)")
    con.executemany("INSERT INTO reviewed VALUES (?)", [(k,) for k in decisions])

    # Remaining components of each blocked record, ranked by size; rank 1 is presumed to be the active part.
    con.execute(
        "CREATE TEMP TABLE remaining AS "
        "SELECT comp.*, row_number() OVER (PARTITION BY comp.inchikey ORDER BY heavy DESC, component_parent) AS rank "
        "FROM (SELECT inchikey, component_parent, max(heavy) AS heavy, any_value(component_inchikey) AS "
        "component_inchikey, any_value(component_inchi) AS component_inchi FROM comp "
        "WHERE component_parent NOT IN (SELECT component_parent FROM drops) GROUP BY 1, 2) comp "
        "JOIN resolved USING (inchikey) WHERE resolved.parent IS NULL"
    )
    con.execute(
        "CREATE TEMP TABLE blockers AS SELECT r.*, "
        "count(*) OVER (PARTITION BY r.inchikey) AS blockers_in_record FROM remaining r "
        "WHERE rank > 1 AND component_parent NOT IN (SELECT component_parent FROM reviewed)"
    )

    total = len(records)
    n_resolved = sum(1 for p in records.values() if p is not None)
    n_all_dropped = con.execute(
        "SELECT count(*) FROM resolved WHERE parent IS NULL AND inchikey NOT IN (SELECT inchikey FROM remaining)"
    ).fetchone()[0]
    n_blocked = total - n_resolved - n_all_dropped
    n_blocked_unreviewed = con.execute("SELECT count(DISTINCT inchikey) FROM blockers").fetchone()[0]
    n_parent_exists = con.execute(
        "SELECT count(*) FROM resolved JOIN clique_parents ON resolved.parent = clique_parents.parent"
    ).fetchone()[0]
    distinct_unreviewed = con.execute("SELECT count(DISTINCT component_parent) FROM blockers").fetchone()[0]

    # The top unreviewed blockers, each with a name and an example record.
    con.execute(
        "CREATE TEMP TABLE names AS SELECT k.inchikey, arg_min(t.title, k.cid) AS title "
        "FROM read_parquet(?) k JOIN read_parquet(?) t USING (cid) "
        "WHERE k.inchikey IN (SELECT component_inchikey FROM blockers UNION SELECT inchikey FROM blockers "
        "UNION SELECT component_inchikey FROM comp WHERE component_parent IN (SELECT component_parent FROM reviewed)) "
        "GROUP BY 1",
        [keys_parquet, titles_parquet],
    )
    top = con.execute(
        "SELECT b.component_parent, count(DISTINCT b.inchikey) AS records, "
        "count(DISTINCT b.inchikey) FILTER (WHERE blockers_in_record = 1) AS sole, "
        "arg_min(b.component_inchikey, length(b.component_inchikey)) AS key, "
        "arg_min(b.component_inchi, length(b.component_inchi)) AS inchi, "
        "arg_min(b.inchikey, b.inchikey) AS example "
        "FROM blockers b GROUP BY 1 ORDER BY records DESC, b.component_parent LIMIT ?",
        [TOP_BLOCKERS],
    ).fetchall()
    name_of = dict(con.execute("SELECT inchikey, title FROM names").fetchall())
    shown_records = sum(row[1] for row in top)

    keep_rows = con.execute(
        "SELECT component_parent, count(DISTINCT inchikey) FROM remaining WHERE rank > 1 "
        "AND component_parent IN (SELECT component_parent FROM reviewed) GROUP BY 1 ORDER BY 2 DESC LIMIT ?",
        [TOP_KEEPS],
    ).fetchall()

    out = [f"# Salt and hydrate component review, {args.build}", ""]
    out.append(
        fill(
            f"Generated by `docs/conflation/chemical-parent/scripts/review_salt_components.py` from PubChem's "
            f"`CID-InChI-Key.gz`, the {args.build} chemical `Edge.parquet` files and `{args.decisions}` "
            f"({len(drops):,} components marked drop, {len(keeps):,} marked keep)."
        )
    )
    out += ["", "## Coverage", ""]
    out.append(
        md_table(
            ["Multi-component InChIs in curated chemical cliques", "Count", "Share"],
            [
                ["All", f"{total:,}", "100%"],
                ["Resolved to one parent", f"{n_resolved:,}", f"{n_resolved / total:.1%}"],
                [
                    "... whose parent key is an existing clique's",
                    f"{n_parent_exists:,}",
                    f"{n_parent_exists / total:.1%}",
                ],
                ["Every component dropped", f"{n_all_dropped:,}", f"{n_all_dropped / total:.1%}"],
                ["Blocked (two or more components left)", f"{n_blocked:,}", f"{n_blocked / total:.1%}"],
                [
                    "... with an unreviewed blocker",
                    f"{n_blocked_unreviewed:,}",
                    f"{n_blocked_unreviewed / total:.1%}",
                ],
            ],
        )
    )
    out += [
        "",
        fill(
            f"{distinct_unreviewed:,} distinct unreviewed components block records. The {len(top)} listed below "
            f"appear in {shown_records:,} blocked records (a record with two blockers counts under both)."
        ),
    ]
    out += ["", "## Top unreviewed blockers", ""]
    out.append(
        fill(
            "Records: blocked records the component appears in as a non-largest component. Sole: records where it "
            "is the only unreviewed blocker, which would resolve if it were dropped."
        )
    )
    out += [""]
    out.append(
        md_table(
            ["Component parent key", "Name", "InChI", "Records", "Sole", "Example record"],
            [
                [
                    f"`{parent}`",
                    name_of.get(key, ""),
                    f"`{inchi}`" if len(inchi) <= 60 else f"`{inchi[:57]}...`",
                    f"{records_n:,}",
                    f"{sole:,}",
                    f"`{example}` {name_of.get(example, '')}",
                ]
                for parent, records_n, sole, key, inchi, example in top
            ],
        )
    )
    out += ["", "## Reviewed components still blocking records", ""]
    out.append(fill("Components already on the list (normally keep) that remain a non-largest component."))
    out += [""]
    out.append(
        md_table(
            ["Component parent key", "Decision", "Records"], [[f"`{k}`", decisions[k], f"{n:,}"] for k, n in keep_rows]
        )
    )
    out.append("")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        f.write("\n".join(out))
    with open(args.sheet, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(DECISIONS_TSV_HEADER + ["records", "sole", "example_record"])
        for parent, records_n, sole, key, inchi, example in top:
            writer.writerow(
                [
                    parent,
                    "",
                    "",
                    name_of.get(key, ""),
                    inchi,
                    "",
                    records_n,
                    sole,
                    f"{example} {name_of.get(example, '')}",
                ]
            )
    print("\n".join(out[:30]))


if __name__ == "__main__":
    main()
