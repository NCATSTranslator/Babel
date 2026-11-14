"""Reconstruct, from a finished build, what the chemical glom() passes did with every concord edge.

``glom()`` refuses a pair only when the merged set would hold two different InChIKeys, and sets only grow while it
runs. So once a build is finished, its cliques and its raw concords (``duckdb/Concord.parquet``) determine the fate
of every chemical concord edge without replaying ``glom()``:

* both endpoints in one final clique: the edge was **applied** (or was a no-op), unless a pre-glom filter removed it;
* endpoints in different cliques: the edge was removed by a pre-glom filter, or **refused** by the InChIKey guard
  (both cliques carry a key; one key per clique means the keys differ).

Two steps outside ``glom()`` have to be modelled for that to hold:

* the pre-glom filters of ``chemicals.build_untyped_compendia()`` and ``chemicals.combine_unichem()``:
  ``remove_overused_xrefs`` (every untyped-stage concord, and the UniChem files of
  ``chemicals.UNICHEM_OVERUSED_XREF_PREFIXES``), from the CUI-follows-MeSH rule onward skipping pairs that name
  a UMLS CUI another pipeline owns, and from ``input_data/chemical_badxrefs.txt`` onward skipping its pairs;
* the post-glom split in ``chemicals.create_typed_sets()`` (Babel #83), which moves the ``MolecularMixture``-typed
  members of a clique whose PubChem CIDs disagree on type into a clique of their own. The split-off clique holds no
  InChIKey, while its CIDs' own UniChem keys stay with the parent, so each one is rejoined to the single keyed
  clique its CIDs' keys sit in. These rejoined groups are the **pre-split sets**: the sets ``glom()`` actually built.

A cross-clique edge that none of this explains means the model above no longer matches the pipeline, and
:func:`classify_chemical_glom_edges` raises rather than returning verdicts nobody can trust. On 2026jul22 every one
of the 132.5M chemical concord edges is explained.

Everything runs in DuckDB. CURIEs and clique leaders are joined as 64-bit hashes so a 256M-member compendium fits
in memory; a collision would merge two members' fates, and on 2026jul22 the 256,445,670 distinct CURIEs have
256,445,670 distinct hashes.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.util import get_logger

logger = get_logger(__name__)

# Verdicts written to glom_edge.verdict.
APPLIED = "applied"
FILTERED_OVERUSED = "filtered: overused xref"
FILTERED_OWNED_ELSEWHERE = "filtered: CUI owned by another pipeline"
FILTERED_BADXREF = "filtered: chemical_badxrefs"
REFUSED_INCHIKEY = "refused: InChIKey guard"
ENDPOINT_ABSENT = "endpoint absent from chemical outputs"
ENDPOINT_AMBIGUOUS = "endpoint in more than one chemical clique"
UNEXPLAINED = "unexplained"

# Path fragment that marks a concord as one of the UniChem record->InChIKey files (combine_unichem's input).
UNICHEM_CONCORD_DIR = "/chemicals/concords/UNICHEM/"


def _sql_list(values: Iterable[str]) -> str:
    """Render strings as a SQL list literal; the values are config and code constants, never user data."""
    return "[" + ",".join("'" + v.replace("'", "''") + "'" for v in values) + "]"


def classify_chemical_glom_edges(
    con,
    concord_parquet: str,
    edge_parquets: list[str],
    chemical_concords: list[str],
    unichem_overused_prefixes: Iterable[str],
    owned_elsewhere: Iterable[str] = (),
    bad_pairs: Iterable[tuple[str, str]] = (),
) -> None:
    """Create table ``glom_edge`` in ``con``: one row per chemical concord edge with its verdict and pre-split sets.

    :param con: A DuckDB connection; the tables ``glom_node``, ``keyed_clique``, ``presplit`` and ``glom_edge`` are
        (re)created in it.
    :param concord_parquet: The build's ``duckdb/Concord.parquet``.
    :param edge_parquets: The build's chemical compendia ``Edge.parquet`` files (one per ``chemical_outputs`` type).
    :param chemical_concords: ``config.yaml: chemical_concords`` -- the untyped-stage concord files glom() reads.
    :param unichem_overused_prefixes: ``chemicals.UNICHEM_OVERUSED_XREF_PREFIXES``.
    :param owned_elsewhere: UMLS CUIs the chemical compendium skips because another pipeline owns them
        (``umls.read_cuis_owned_elsewhere(mesh_ownership, "chemicals")``); empty for builds before that rule.
    :param bad_pairs: The build's ``read_badxrefs(chemicals.CHEMICAL_BAD_XREFS)`` pairs, matched in either direction;
        empty for builds made before the file existed. Passing them for a build that did not apply them relabels
        edges it applied, so only pass what the build used.

    Columns of ``glom_edge``: ``base`` (concord file name), ``is_unichem``, ``subj``, ``obj``, ``s_set``/``o_set``
    (hashed pre-split set of each endpoint, NULL if absent), ``verdict``.

    :raises RuntimeError: if any cross-clique edge is unexplained, or a split-off clique maps to more than one
        parent -- either means this model has drifted from the pipeline.
    """
    con.sql(f"""
        CREATE OR REPLACE TABLE glom_node AS
        SELECT DISTINCT hash(curie) AS h, hash(clique_leader) AS c, curie LIKE 'INCHIKEY:%' AS is_key
        FROM read_parquet({_sql_list(edge_parquets)})
    """)
    con.sql(
        "CREATE OR REPLACE TABLE ambiguous_curie AS SELECT h FROM glom_node GROUP BY h HAVING count(DISTINCT c) > 1"
    )
    con.sql("CREATE OR REPLACE TEMP TABLE owned_elsewhere (curie VARCHAR)")
    owned = sorted(set(owned_elsewhere))
    if owned:
        con.executemany("INSERT INTO owned_elsewhere VALUES (?)", [(c,) for c in owned])
    con.sql("CREATE OR REPLACE TEMP TABLE bad_pair (a VARCHAR, b VARCHAR)")
    bad = sorted({p for s, o in bad_pairs for p in ((s, o), (o, s))})
    if bad:
        con.executemany("INSERT INTO bad_pair VALUES (?, ?)", bad)

    untyped = _sql_list(chemical_concords)
    overused_unichem = _sql_list(f"UNICHEM_{p}" for p in unichem_overused_prefixes)
    con.sql(f"""
        CREATE OR REPLACE TABLE glom_edge_raw AS
        WITH raw AS (
            SELECT regexp_extract(filename, '[^/]+$') AS base,
                   filename LIKE '%{UNICHEM_CONCORD_DIR}%' AS is_unichem, subj, obj
            FROM read_parquet('{concord_parquet}')
            WHERE filename LIKE '%/chemicals/concords/%'
        ), fed AS (
            SELECT *, (subj IN (SELECT curie FROM owned_elsewhere) OR obj IN (SELECT curie FROM owned_elsewhere))
                      AS owned_elsewhere,
                   NOT is_unichem AND (subj, obj) IN (SELECT (a, b) FROM bad_pair) AS badxref
            FROM raw
            WHERE is_unichem OR list_contains({untyped}, base)
        )
        SELECT base, is_unichem, subj, obj, owned_elsewhere, badxref,
               -- remove_overused_xrefs(): drop every row whose object appears in 2+ rows of the same file. The
               -- build counts after skipping owned-elsewhere and bad-xref pairs, so they are left out here too.
               NOT owned_elsewhere AND NOT badxref
                 AND (NOT is_unichem OR list_contains({overused_unichem}, base))
                 AND count(*) FILTER (WHERE NOT owned_elsewhere AND NOT badxref) OVER (PARTITION BY base, obj) >= 2
                 AS overused
        FROM fed
    """)
    unknown_files = con.sql(f"""
        SELECT DISTINCT regexp_extract(filename, '[^/]+$') FROM read_parquet('{concord_parquet}')
        WHERE filename LIKE '%/chemicals/concords/%' AND filename NOT LIKE '%{UNICHEM_CONCORD_DIR}%'
          AND NOT list_contains({untyped}, regexp_extract(filename, '[^/]+$'))
    """).fetchall()
    if unknown_files:
        logger.info("chemical concord files not fed to glom() (not in chemical_concords): %s", unknown_files)

    con.sql("""
        CREATE OR REPLACE TABLE glom_edge_mapped AS
        SELECT r.*, hash(subj) AS hs, hash(obj) AS ho, ns.c AS sc, no.c AS oc
        FROM glom_edge_raw r
        LEFT JOIN glom_node ns ON ns.h = hash(r.subj) AND ns.h NOT IN (SELECT h FROM ambiguous_curie)
        LEFT JOIN glom_node no ON no.h = hash(r.obj) AND no.h NOT IN (SELECT h FROM ambiguous_curie)
    """)
    # A clique carries a key if its output holds an INCHIKEY, or if a member's UniChem key was dropped from every
    # output (Drug and Food do not register the INCHIKEY prefix, so write_compendium() drops it there).
    con.sql("""
        CREATE OR REPLACE TABLE keyed_clique AS
        SELECT DISTINCT c FROM glom_node WHERE is_key
        UNION
        SELECT DISTINCT sc FROM glom_edge_mapped
        WHERE is_unichem AND NOT overused AND sc IS NOT NULL AND oc IS NULL AND obj LIKE 'INCHIKEY:%'
    """)
    # Pre-split sets (Babel #83): a keyless clique whose records' own UniChem keys sit in another, keyed clique.
    con.sql("""
        CREATE OR REPLACE TABLE presplit AS
        SELECT sc AS mix, min(oc) AS parent, count(DISTINCT oc) AS n_parents
        FROM glom_edge_mapped
        WHERE is_unichem AND NOT overused AND sc IS NOT NULL AND oc IS NOT NULL AND sc <> oc
          AND sc NOT IN (SELECT c FROM keyed_clique) AND oc IN (SELECT c FROM keyed_clique)
        GROUP BY sc
    """)
    ambiguous_splits = con.sql("SELECT count(*) FROM presplit WHERE n_parents > 1").fetchone()[0]
    if ambiguous_splits:
        raise RuntimeError(
            f"{ambiguous_splits} keyless chemical cliques hold records whose UniChem keys sit in more than one keyed "
            f"clique, so their pre-split set is ambiguous (see SELECT * FROM presplit WHERE n_parents > 1). The #83 "
            f"split model in src/model/glom_edges.py no longer describes this build."
        )

    con.sql(f"""
        CREATE OR REPLACE TABLE glom_edge AS
        WITH s AS (
            SELECT m.*, coalesce(ps.parent, m.sc) AS s_set, coalesce(po.parent, m.oc) AS o_set,
                   hs IN (SELECT h FROM ambiguous_curie) OR ho IN (SELECT h FROM ambiguous_curie) AS ambiguous
            FROM glom_edge_mapped m
            LEFT JOIN presplit ps ON ps.mix = m.sc
            LEFT JOIN presplit po ON po.mix = m.oc
        )
        SELECT base, is_unichem, subj, obj, s_set, o_set,
          CASE
            WHEN ambiguous THEN '{ENDPOINT_AMBIGUOUS}'
            WHEN owned_elsewhere THEN '{FILTERED_OWNED_ELSEWHERE}'
            WHEN badxref THEN '{FILTERED_BADXREF}'
            WHEN s_set IS NULL OR o_set IS NULL THEN '{ENDPOINT_ABSENT}'
            WHEN overused THEN '{FILTERED_OVERUSED}'
            WHEN s_set = o_set THEN '{APPLIED}'
            WHEN s_set IN (SELECT c FROM keyed_clique) AND o_set IN (SELECT c FROM keyed_clique)
              THEN '{REFUSED_INCHIKEY}'
            ELSE '{UNEXPLAINED}'
          END AS verdict
        FROM s
    """)
    con.sql("DROP TABLE glom_edge_raw")
    con.sql("DROP TABLE glom_edge_mapped")
    for verdict, n in con.sql("SELECT verdict, count(*) FROM glom_edge GROUP BY 1 ORDER BY 1").fetchall():
        logger.info("glom edges %s: %d", verdict, n)
    unexplained = con.sql(f"SELECT count(*) FROM glom_edge WHERE verdict = '{UNEXPLAINED}'").fetchone()[0]
    if unexplained:
        examples = con.sql(f"SELECT base, subj, obj FROM glom_edge WHERE verdict = '{UNEXPLAINED}' LIMIT 5").fetchall()
        raise RuntimeError(
            f"{unexplained} chemical concord edges join different cliques with no filter or InChIKey refusal to "
            f"explain it, e.g. {examples}. The build was made by pipeline code this model does not describe; update "
            f"src/model/glom_edges.py before trusting any verdict it gives."
        )
