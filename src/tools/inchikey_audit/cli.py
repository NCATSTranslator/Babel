"""``babel-inchikey-audit`` -- audit what a finished build attached to each chemical structure.

Argument parsing and file writing only: :func:`src.model.glom_edges.classify_chemical_glom_edges` reconstructs what
glom() did with every chemical concord edge, and :func:`src.model.inchikey_audit.audit_chemical_inchikeys` finds,
tiers and triages the structure-less components attached to keyed cliques.

Invocation::

    uv run babel-inchikey-audit --build data/inchikey-clique-audit/<build> --lookup-build <build URL> \\
        --structure-file babel_downloads/UNICHEM/structure.tsv.gz --out data/inchikey-clique-audit/out

``--build`` must hold ``duckdb/Concord.parquet`` and the chemical compendia's
``duckdb/parquet/filename=<Type>/Edge.parquet``, which are scanned in full, so keep them local.
``--lookup-build`` (default: ``--build``) supplies ``Node.parquet`` labels and ``Identifier.parquet`` types, which
are only filtered, so a remote build URL works. Pass ``--mesh-ownership`` (``intermediate/umls/mesh_ownership.tsv``)
for builds made after the CUI-follows-MeSH rule, and ``--badxrefs`` (the build's
``intermediate/chemicals/partials/applied_badxrefs.txt``) for builds made after ``input_data/chemical_badxrefs.txt``
existed; leave both out for 2026jul22 and earlier. ``--badxrefs`` refuses the repo's ``input_data`` file, which may
list pairs added after the build: those would relabel edges the build applied and hide them from the audit. Leaving
out a filter the build did apply fails loudly, as unexplained edges.

Writes, under ``--out``:

* ``components.tsv`` -- one row per flagged structure-less component: tier, triage verdict, key, sizes, labels;
* ``boundary_edges.tsv`` -- the concord edges attaching each flagged component to its key; the ``likely misattached``
  rows are the candidate pairs to block;
* ``refused_edges.tsv`` -- xrefs the InChIKey guard refused (harmless in the build; worth reporting upstream);
* ``summary.tsv`` -- counts of glom edge verdicts and of components by tier and verdict.
"""

import argparse
import pathlib
import sys

from src.createcompendia.chemicals import UNICHEM_OVERUSED_XREF_PREFIXES, read_applied_badxrefs
from src.datahandlers.umls import read_cuis_owned_elsewhere
from src.duckdb_setup import setup_duckdb
from src.model.glom_edges import classify_chemical_glom_edges
from src.model.inchikey_audit import audit_chemical_inchikeys, refused_edges_query
from src.util import get_config, get_logger, sql_str

logger = get_logger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", required=True, help="Build root holding duckdb/Concord.parquet and Edge files.")
    parser.add_argument("--lookup-build", help="Build root (or URL) for Node/Identifier parquet; default --build.")
    parser.add_argument(
        "--structure-file",
        default="babel_downloads/UNICHEM/structure.tsv.gz",
        help="UniChem structure.tsv.gz, for the core structures' InChIs (default: the pipeline's download).",
    )
    parser.add_argument("--mesh-ownership", help="intermediate/umls/mesh_ownership.tsv, for builds that applied it.")
    parser.add_argument(
        "--badxrefs", help="The build's intermediate/chemicals/partials/applied_badxrefs.txt, for builds that have one."
    )
    parser.add_argument("--out", required=True, help="Output directory.")
    parser.add_argument("--work-dir", help="Scratch directory for DuckDB and intermediates (default: <out>/work).")
    parser.add_argument("--memory-limit", default="18GB", help="DuckDB memory limit (default: 18GB).")
    parser.add_argument("--threads", type=int, default=6, help="DuckDB threads (default: 6).")
    args = parser.parse_args(argv)

    config = get_config()
    build = args.build.rstrip("/")
    lookup = (args.lookup_build or args.build).rstrip("/")
    types = [o.removesuffix(".txt") for o in config["chemical_outputs"]]
    edge_parquets = {t: f"{build}/duckdb/parquet/filename={t}/Edge.parquet" for t in types}
    node_parquets = [f"{lookup}/duckdb/parquet/filename={t}/Node.parquet" for t in types]
    out = pathlib.Path(args.out)
    work = pathlib.Path(args.work_dir) if args.work_dir else out / "work"
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)  # --work-dir may sit outside --out

    # The pipeline's DuckDB setup: config.yaml's duckdb_config defaults, a per-run spill directory under --work-dir,
    # and the connect-time settings and memory-headroom log lines.
    con = setup_duckdb(
        str(work / "audit.duckdb"),
        {
            "memory_limit": args.memory_limit,
            "threads": args.threads,
            "preserve_insertion_order": False,
            "temp_directory": str(work / "spill"),
        },
    )
    if lookup.startswith("http"):
        con.sql("INSTALL httpfs; LOAD httpfs")

    owned = read_cuis_owned_elsewhere(args.mesh_ownership, "chemicals") if args.mesh_ownership else frozenset()
    bad_pairs = read_applied_badxrefs(args.badxrefs) if args.badxrefs else ()
    classify_chemical_glom_edges(
        con,
        f"{build}/duckdb/Concord.parquet",
        edge_parquets,
        config["chemical_concords"],
        UNICHEM_OVERUSED_XREF_PREFIXES,
        owned,
        bad_pairs,
    )
    audit_chemical_inchikeys(con, str(work), node_parquets, f"{lookup}/duckdb/Identifier.parquet", args.structure_file)

    tsv = "(HEADER, DELIMITER '\\t')"
    con.sql(f"COPY (SELECT * EXCLUDE (set_id, comp) FROM audit_component) TO {sql_str(out / 'components.tsv')} {tsv}")
    con.sql(f"COPY audit_boundary TO {sql_str(out / 'boundary_edges.tsv')} {tsv}")
    con.sql(f"COPY ({refused_edges_query()}) TO {sql_str(out / 'refused_edges.tsv')} {tsv}")
    con.sql(f"""COPY (
        SELECT 'glom edge' AS kind, verdict AS category, count(*) AS n FROM glom_edge GROUP BY ALL
        UNION ALL
        SELECT 'component tier ' || tier, verdict, count(*) FROM audit_component GROUP BY ALL
        ORDER BY 1, 2
    ) TO {sql_str(out / "summary.tsv")} {tsv}""")
    for row in con.sql(f"SELECT * FROM read_csv({sql_str(out / 'summary.tsv')}, delim='\\t')").fetchall():
        logger.info("%s", row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
