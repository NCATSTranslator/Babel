"""Which concord CURIEs with an unknown prefix merged two subjects into one clique in a published build?

``babel-check-concords --prefixes`` lists the prefixes in a build's concords that neither the Biolink Model nor
``src/prefixes.py`` defines. Such a CURIE joins nothing, but ``glom()`` still merges every subject that cites it,
so this script asks of a build's DuckDB export which of those CURIEs actually did. For every unknown-prefix
object cited by two or more subjects in one pipeline's concords, it looks the subjects up in the build's
``Edge`` tables to see whether they all landed in one clique, and then whether anything else in the concords
links them directly or through one shared neighbour. ``glom()`` is transitive, so a longer path can still be
the real cause: check each pair against the concords before blaming the xref.

It reads the export's ``Concord.parquet`` (which keeps every concord row) rather than an ``intermediate/`` tree,
since 2026jul22 published no ``intermediate/``. Only the anatomy, disease, process and protein pipelines are
checked: chemicals' unknown prefixes are UniChem's InChIKey and CAS join keys, and the others write few xrefs.

    uv run python docs/tools/check-concords/unknown_prefix_merges.py \\
        --duckdb-dir data/2026jul22/duckdb --output docs/tools/check-concords/2026jul22.md

``--duckdb-dir`` is a local copy of ``<build>/duckdb/`` (``Concord.parquet`` and ``parquet/*/Edge.parquet``).
Unknown is judged at ``config.yaml: biolink_version``, which may be newer than the build's.
"""

import argparse
import pathlib

import duckdb

from src.model.concords import known_curie_prefixes
from src.util import get_biolink_prefix_map, get_config

PIPELINES = ("anatomy", "disease", "process", "protein")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--duckdb-dir", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()

    known = known_curie_prefixes(get_biolink_prefix_map().prefix_map)
    db = duckdb.connect()
    db.execute("CREATE TABLE known (prefix VARCHAR)")
    db.executemany("INSERT INTO known VALUES (?)", [(p,) for p in sorted(known)])
    concords = (args.duckdb_dir / "Concord.parquet").as_posix()
    edges = (args.duckdb_dir / "parquet" / "*" / "Edge.parquet").as_posix()
    db.execute(
        f"""
        CREATE TABLE unknown_rows AS
        SELECT regexp_extract(filename, 'intermediate/([^/]+)/', 1) AS pipeline,
               regexp_replace(filename, '.*/concords/', '') AS concord,
               subj, obj, split_part(obj, ':', 1) AS prefix
        FROM read_parquet('{concords}')
        WHERE regexp_extract(filename, 'intermediate/([^/]+)/', 1) IN {PIPELINES}
          AND split_part(obj, ':', 1) NOT IN (SELECT prefix FROM known)
        """
    )
    by_prefix = db.sql(
        """SELECT pipeline, concord, prefix, count(*) AS rows FROM unknown_rows GROUP BY ALL
           ORDER BY pipeline, concord, rows DESC, prefix"""
    ).fetchall()
    db.execute(
        f"""
        CREATE TABLE merged AS
        WITH cited AS (
            SELECT pipeline, obj, any_value(prefix) AS prefix, list(DISTINCT subj ORDER BY subj) AS subjects
            FROM unknown_rows GROUP BY pipeline, obj HAVING count(DISTINCT subj) > 1
        )
        SELECT c.pipeline, c.prefix, c.obj, c.subjects, count(e.clique_leader) = len(c.subjects)
                   AND count(DISTINCT e.clique_leader) = 1 AS one_clique, any_value(e.clique_leader) AS leader
        FROM cited c, unnest(c.subjects) AS t(subject)
        LEFT JOIN read_parquet('{edges}') e ON e.curie = t.subject
        GROUP BY c.pipeline, c.prefix, c.obj, c.subjects
        """
    )
    # A merge is put down to the unknown-prefix CURIE alone when no two of its subjects are also
    # neighbours, or share a neighbour, through any other row of the pipeline's concords. Anything
    # longer than that two-step path is beyond this check: hence "probably".
    db.execute(
        f"""
        CREATE TABLE linked_otherwise AS
        WITH subjects AS (SELECT DISTINCT pipeline, obj AS via, unnest(subjects) AS subject FROM merged WHERE one_clique),
        rows AS (
            SELECT regexp_extract(filename, 'intermediate/([^/]+)/', 1) AS pipeline, subj, obj
            FROM read_parquet('{concords}')
            WHERE subj IN (SELECT subject FROM subjects) OR obj IN (SELECT subject FROM subjects)
        ),
        neighbours AS (
            SELECT s.pipeline, s.via, s.subject, CASE WHEN r.subj = s.subject THEN r.obj ELSE r.subj END AS neighbour
            FROM subjects s JOIN rows r ON r.pipeline = s.pipeline AND s.subject IN (r.subj, r.obj)
        )
        SELECT DISTINCT a.pipeline, a.via FROM neighbours a JOIN neighbours b
          ON a.pipeline = b.pipeline AND a.via = b.via AND a.subject < b.subject
         AND (a.neighbour = b.neighbour OR a.neighbour = b.subject)
        WHERE a.neighbour <> a.via
        """
    )
    merges = db.sql(
        """
        SELECT m.pipeline, m.prefix, count(*) AS cited_by_2_plus,
               count(*) FILTER (WHERE one_clique) AS one_clique,
               list(m.obj || ' (' || array_to_string(m.subjects, ', ') || ')' ORDER BY m.obj)
                   FILTER (WHERE one_clique AND l.via IS NULL) AS probably_caused
        FROM merged m LEFT JOIN linked_otherwise l ON l.pipeline = m.pipeline AND l.via = m.obj
        GROUP BY ALL ORDER BY m.pipeline, cited_by_2_plus DESC, m.prefix
        """
    ).fetchall()

    out = [
        f"# Unknown concord prefixes in {args.duckdb_dir.parent.name}",
        "",
        f"Generated by `unknown_prefix_merges.py`, judged at Biolink {get_config()['biolink_version']}.",
        "",
        "## Unknown object prefixes, by concord",
        "",
        "| Pipeline | Concord | Prefix | Rows |",
        "|---|---|---|---|",
        *(f"| {p} | {c} | `{x}` | {n:,} |" for p, c, x, n in by_prefix),
        "",
        "## Unknown-prefix CURIEs cited by two or more subjects",
        "",
        "*In one clique* counts the CURIEs whose citing subjects all landed in one clique of the build.",
        "*Probably caused by it* lists those whose subjects are not also neighbours, and share no",
        "neighbour, through any other concord row: the unknown-prefix xref is then the likely bridge.",
        "",
        "| Pipeline | Prefix | Cited by 2+ subjects | In one clique | Probably caused by it |",
        "|---|---|---|---|---|",
        *(f"| {p} | `{x}` | {n:,} | {k:,} | {'; '.join(m or [])} |" for p, x, n, k, m in merges),
        "",
    ]
    args.output.write_text("\n".join(out))


if __name__ == "__main__":
    main()
