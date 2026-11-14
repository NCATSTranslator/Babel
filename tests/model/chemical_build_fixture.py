"""Write a miniature finished build (the Parquet layout babel-inchikey-audit reads) for the glom-edge and audit tests.

A build here is ``<root>/duckdb/Concord.parquet`` plus ``<root>/duckdb/parquet/filename=<Type>/{Edge,Node}.parquet``
for every ``config.yaml: chemical_outputs`` type and ``<root>/duckdb/Identifier.parquet``, each with only the
columns the audit reads.
"""

import gzip
import pathlib

import duckdb

from src.datahandlers.unichem import UNICHEM_STRUCT_TSV_HEADER
from src.util import get_config

CONCORD_DIR = "/run/babel_outputs/intermediate/chemicals/concords"


def unichem(prefix: str) -> str:
    """Concord.parquet ``filename`` of the UniChem record->InChIKey file for ``prefix``."""
    return f"{CONCORD_DIR}/UNICHEM/UNICHEM_{prefix}"


def concord(name: str) -> str:
    """Concord.parquet ``filename`` of an untyped-stage chemical concord."""
    return f"{CONCORD_DIR}/{name}"


def _values(rows: list[tuple], ncols: int) -> str:
    """A SELECT yielding ``rows`` as VARCHAR columns c0..c{ncols-1} (typed but empty when there are no rows)."""
    cols = ", ".join(f"c{i}" for i in range(ncols))
    if not rows:
        return "SELECT " + ", ".join(f"NULL::VARCHAR AS c{i}" for i in range(ncols)) + " WHERE false"
    body = ",".join("(" + ",".join("'" + str(v).replace("'", "''") + "'" for v in r) + ")" for r in rows)
    return f"SELECT * FROM (VALUES {body}) AS v({cols})"


def write_build(
    root: pathlib.Path,
    concords: list[tuple[str, str, str]],
    cliques: dict[str, tuple[str, list[str]]],
    labels: dict[str, str] | None = None,
    ids: list[tuple[str, str, str]] | None = None,
) -> pathlib.Path:
    """Write a build under ``root`` and return ``root``.

    :param concords: ``(filename, subj, obj)`` rows of Concord.parquet (predicate is irrelevant to the audit).
    :param cliques: ``leader -> (Biolink type name, members)``; members must include the leader.
    :param labels: ``curie -> label`` for Node.parquet.
    :param ids: ``(ids file name, curie, biolink_type)`` rows of Identifier.parquet.
    """
    duck = root / "duckdb"
    duck.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    rows = [(f, s, "eq", o) for f, s, o in concords]
    con.sql(f"""COPY (SELECT c0 AS filename, c1 AS subj, c2 AS pred, c3 AS obj FROM ({_values(rows, 4)}))
                TO '{duck / "Concord.parquet"}'""")
    labels = labels or {}
    for output in get_config()["chemical_outputs"]:
        t = output.removesuffix(".txt")
        d = duck / "parquet" / f"filename={t}"
        d.mkdir(parents=True, exist_ok=True)
        edges = [(leader, m) for leader, (typ, ms) in cliques.items() if typ == t for m in ms]
        con.sql(f"COPY (SELECT c0 AS clique_leader, c1 AS curie FROM ({_values(edges, 2)})) TO '{d / 'Edge.parquet'}'")
        nodes = [(m, labels.get(m, "")) for _, ms in (v for v in cliques.values() if v[0] == t) for m in ms]
        con.sql(f"COPY (SELECT c0 AS curie, c1 AS label FROM ({_values(nodes, 2)})) TO '{d / 'Node.parquet'}'")
    id_rows = [(f"/run/babel_outputs/intermediate/chemicals/ids/{f}", c, t) for f, c, t in (ids or [])]
    con.sql(f"""COPY (SELECT c0 AS filename, c1 AS curie, c2 AS biolink_type FROM ({_values(id_rows, 3)}))
                TO '{duck / "Identifier.parquet"}'""")
    return root


def write_structure_file(path: pathlib.Path, rows: list[tuple[str, str, str]]) -> pathlib.Path:
    """Write a UniChem ``structure.tsv.gz`` with ``(uci, standard InChI, standard InChIKey)`` rows."""
    with gzip.open(path, "wt") as f:
        f.write(UNICHEM_STRUCT_TSV_HEADER)
        for row in rows:
            f.write("\t".join(row) + "\n")
    return path
