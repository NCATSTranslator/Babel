"""Compare the InChIKey UniChem gives each PubChem CID with the one PubChem publishes for it.

Babel takes every PUBCHEM.COMPOUND structure from UniChem (source 22): `write_unichem_concords()`
writes them to `concords/UNICHEM/UNICHEM_PUBCHEM.COMPOUND`. PubChem publishes its own CID -> InChIKey
table, `CID-InChI-Key.gz`, which `rule get_pubchem_structures` downloads and nothing reads. This
script joins the two and classifies every CID by how the keys differ. It is the evidence behind
#1207 (and #1165, sirolimus); see ../README.md.

Usage, from the repository root:

    D=docs/sources/UNICHEM/pubchem-inchikeys
    uv run python $D/scripts/compare_pubchem_inchikeys.py --label 2026jul22 \\
        --unichem-concord <build>/intermediate/chemicals/concords/UNICHEM/UNICHEM_PUBCHEM.COMPOUND \\
        --pubchem-inchikeys babel_downloads/PUBCHEM.COMPOUND/CID-InChI-Key.gz \\
        --examples-csv $D/examples-2026jul22.csv > $D/report-2026jul22.md

--unichem-concord may instead be a build's `duckdb/Concord.parquet`, local or an https:// URL, from
which the UNICHEM_PUBCHEM.COMPOUND rows are read; that avoids fetching the 10 GB concord itself.

Both files are several gigabytes; the join takes DuckDB a few minutes and spills to --workdir. The
PubChem file is whatever was downloaded, so against an older build some differences are PubChem
having changed since, not UniChem being wrong: the report gives the file's date for that reason.
"""

import argparse
import datetime
import os
import sys

import duckdb

# The InChIKey second block of a structure with no stereo, isotope or other minor layers.
NO_STEREO_BLOCK = "UHFFFAOYSA"

# How the two keys differ, most alarming last. A key is SKELETON-REST-CHARGE; `u` is UniChem's and `p`
# PubChem's, both without the INCHIKEY: prefix.
KIND_SQL = f"""
    CASE
        WHEN p IS NULL THEN 'CID is not in PubChem''s file'
        WHEN u = p THEN 'Same key'
        WHEN split_part(u, '-', 1) <> split_part(p, '-', 1) THEN 'Different skeleton'
        WHEN split_part(u, '-', 2) = split_part(p, '-', 2) THEN 'Same skeleton and stereo; charge flag only'
        WHEN split_part(u, '-', 2) LIKE '{NO_STEREO_BLOCK}%' THEN 'Same skeleton; UniChem stereo-less, PubChem specific'
        WHEN split_part(p, '-', 2) LIKE '{NO_STEREO_BLOCK}%' THEN 'Same skeleton; PubChem stereo-less, UniChem specific'
        ELSE 'Same skeleton; two different stereo layers'
    END
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--unichem-concord", required=True, help="A build's UNICHEM_PUBCHEM.COMPOUND concord, or its Concord.parquet."
    )
    parser.add_argument("--pubchem-inchikeys", required=True, help="PubChem's CID-InChI-Key.gz.")
    parser.add_argument("--label", required=True, help="Build name to print; file locations are never printed.")
    parser.add_argument("--examples-csv", help="Write up to 200 CIDs of each kind of difference to this file.")
    parser.add_argument("--workdir", default="data/pubchem-inchikeys/duckdb-tmp", help="Where DuckDB may spill.")
    args = parser.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    con = duckdb.connect(os.path.join(args.workdir, "compare.duckdb"))
    con.execute(f"SET temp_directory = '{args.workdir}'")
    con.execute("SET preserve_insertion_order = false")
    if args.unichem_concord.endswith(".parquet"):
        if args.unichem_concord.startswith(("http://", "https://")):
            con.execute("INSTALL httpfs; LOAD httpfs;")
        unichem_rows_sql = "SELECT subj, obj FROM read_parquet(?) WHERE filename LIKE '%/UNICHEM_PUBCHEM.COMPOUND'"
    else:
        unichem_rows_sql = """
            SELECT subj, obj FROM read_csv(?, delim = '\t', header = false, quote = '', escape = '',
                                           columns = {'subj': 'VARCHAR', 'pred': 'VARCHAR', 'obj': 'VARCHAR'})
        """
    # Strip "PUBCHEM.COMPOUND:" (17 characters) and "INCHIKEY:" (9).
    con.execute(
        f"CREATE OR REPLACE TABLE unichem AS SELECT CAST(substr(subj, 18) AS BIGINT) AS cid, substr(obj, 10) AS u "
        f"FROM ({unichem_rows_sql})",
        [args.unichem_concord],
    )
    # PubChem's columns are CID, InChI, InChIKey. The InChI is long and unused here.
    con.execute(
        """
        CREATE OR REPLACE TABLE pubchem AS
        SELECT cid, p
        FROM read_csv(?, delim = '\t', header = false, quote = '', escape = '', max_line_size = 20000000,
                      columns = {'cid': 'BIGINT', 'inchi': 'VARCHAR', 'p': 'VARCHAR'})
        """,
        [args.pubchem_inchikeys],
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE compared AS
        SELECT unichem.cid, u, p, {KIND_SQL} AS kind
        FROM unichem LEFT JOIN pubchem USING (cid)
        """
    )

    out = sys.stdout
    unichem_cids, unichem_rows = con.execute("SELECT count(DISTINCT cid), count(*) FROM unichem").fetchone()
    pubchem_cids = con.execute("SELECT count(*) FROM pubchem").fetchone()[0]
    only_pubchem = con.execute("SELECT count(*) FROM pubchem ANTI JOIN unichem USING (cid)").fetchone()[0]
    file_date = datetime.date.fromtimestamp(os.path.getmtime(args.pubchem_inchikeys)).isoformat()
    out.write(f"# UniChem's InChIKeys for PubChem CIDs vs. PubChem's own, {args.label}\n\n")
    out.write("Written by `scripts/compare_pubchem_inchikeys.py`; do not edit by hand.\n\n")
    out.write(f"- UniChem (source 22) in {args.label}: {unichem_rows:,} rows for {unichem_cids:,} CIDs.\n")
    out.write(f"- PubChem's `CID-InChI-Key.gz`, downloaded {file_date}: {pubchem_cids:,} CIDs,\n")
    out.write(f"  {only_pubchem:,} of them not in UniChem.\n\n")
    out.write("| UniChem's key vs. PubChem's | CIDs | Share |\n|---|---|---|\n")
    total = con.execute("SELECT count(*) FROM compared").fetchone()[0]
    kinds = con.execute("SELECT kind, count(*) FROM compared GROUP BY kind ORDER BY count(*) DESC").fetchall()
    for kind, count in kinds:
        out.write(f"| {kind} | {count:,} | {100 * count / total:.3f}% |\n")

    out.write("\n## Examples\n\nFive CIDs of each kind of difference, spread evenly across the CID range.\n\n")
    out.write("| Kind | CID | UniChem's key | PubChem's key |\n|---|---|---|---|\n")
    spread = """
        SELECT kind, cid, u, p FROM (
            SELECT *, ntile({n}) OVER (PARTITION BY kind ORDER BY cid) AS bucket,
                   row_number() OVER (PARTITION BY kind ORDER BY cid) AS position
            FROM compared WHERE kind <> 'Same key'
        ) QUALIFY row_number() OVER (PARTITION BY kind, bucket ORDER BY position) = 1
        ORDER BY kind, cid
    """
    for kind, cid, u, p in con.execute(spread.format(n=5)).fetchall():
        out.write(f"| {kind} | {cid} | `{u}` | `{p or ''}` |\n")

    if args.examples_csv:
        con.execute(
            f"COPY ({spread.format(n=200)}) TO '{args.examples_csv}' (HEADER, DELIMITER ',')",
        )


if __name__ == "__main__":
    main()
