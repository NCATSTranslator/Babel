"""Count, in a finished build, the cliques conflate_synonyms() (src/synonyms/synonymconflation.py)
refuses because two conflation groups claim them, so we know whether that RuntimeError would stop a
real build. See ../README.md for the results.

Reads `<build>/conflation/<Name>.txt` and each compendium's `duckdb/parquet/filename=<Type>/Edge.parquet`
in place over HTTP(S) with DuckDB httpfs, so no local build is needed.

Usage: uv run python check_split_cliques.py <build_url> <conflation_name> <Compendium> [<Compendium> ...]
e.g.   uv run python check_split_cliques.py <build_url> DrugChemical MolecularMixture SmallMolecule ...
"""

import json
import sys
import tempfile
import urllib.request

import duckdb

build, conflation_name, *compendia = sys.argv[1:]

# Step 1 of conflate_synonyms: every listed ID -> the primary of the (last) line naming it.
conf = {}
multi_line_ids = 0
with urllib.request.urlopen(f"{build}/conflation/{conflation_name}.txt") as fh:
    for raw in fh:
        line = json.loads(raw)
        for ident in line:
            if ident in conf and conf[ident] != line[0]:
                multi_line_ids += 1
            conf[ident] = line[0]
print(f"{len(conf):,} conflation IDs; {multi_line_ids:,} named by two lines with different primaries")

with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as tsv:
    tsv.write("ident\tprimary_id\n")
    for ident, primary in conf.items():
        tsv.write(f"{ident}\t{primary}\n")

c = duckdb.connect()
c.execute("INSTALL httpfs; LOAD httpfs; SET threads=8;")
c.execute(f"CREATE TABLE conf AS SELECT * FROM read_csv('{tsv.name}', delim='\t', header=true, quote='')")
edge_union = " UNION ALL ".join(
    f"SELECT '{name}' AS file, clique_leader, curie "
    f"FROM read_parquet('{build}/duckdb/parquet/filename%3D{name}/Edge.parquet')"
    for name in compendia
)
c.execute(
    f"""CREATE TABLE members AS
    WITH edges AS ({edge_union}),
    hit AS (SELECT DISTINCT file, clique_leader FROM edges JOIN conf ON edges.curie = conf.ident)
    SELECT e.file, e.clique_leader, e.curie, conf.primary_id
    FROM edges e JOIN hit USING (file, clique_leader) LEFT JOIN conf ON e.curie = conf.ident"""
)
print("conflated cliques:", c.execute("SELECT count(DISTINCT (file, clique_leader)) FROM members").fetchone()[0])

# (a) One clique whose own listed members belong to two conflation groups.
a = c.execute(
    """SELECT file, clique_leader, list(DISTINCT primary_id) AS groups FROM members
    WHERE primary_id IS NOT NULL GROUP BY ALL HAVING count(DISTINCT primary_id) > 1"""
).fetchall()
print(f"(a) cliques whose members are listed in two groups: {len(a):,}")
for row in a[:10]:
    print("   ", row)

# (b) One CURIE in two conflated cliques that belong to different groups.
b = c.execute(
    """WITH clique_group AS (
        SELECT file, clique_leader, min(primary_id) AS grp FROM members
        WHERE primary_id IS NOT NULL GROUP BY ALL)
    SELECT m.curie, list(DISTINCT m.file || ':' || m.clique_leader) AS cliques, list(DISTINCT g.grp) AS groups
    FROM members m JOIN clique_group g USING (file, clique_leader)
    GROUP BY m.curie HAVING count(DISTINCT g.grp) > 1"""
).fetchall()
print(f"(b) CURIEs in two conflated cliques of different groups: {len(b):,}")
for row in b[:10]:
    print("   ", row)

# Cliques that appear (by leader) in more than one of the compendia passed in.
d = c.execute(
    "SELECT clique_leader, list(DISTINCT file) FROM members GROUP BY ALL HAVING count(DISTINCT file) > 1"
).fetchall()
print(f"conflated clique leaders in more than one compendium: {len(d):,}")
for row in d[:10]:
    print("   ", row)
