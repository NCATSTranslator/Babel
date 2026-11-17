"""Reconstruct, from a finished build, what the chemical glom() passes did with every concord edge.

``glom()`` refuses a pair only when the merged set would hold two different InChIKeys, and sets only grow while it
runs. So once a build is finished, its cliques and its raw concords (``duckdb/Concord.parquet``) determine the fate
of every chemical concord edge without replaying ``glom()``:

* both endpoints in one final clique: the edge was **applied** (or was a no-op), unless a pre-glom filter removed it;
* endpoints in different cliques: the edge was removed by a pre-glom filter, or **refused** by the InChIKey guard
  (both cliques carry a key; one key per clique means the keys differ).

Three steps outside ``glom()`` have to be modelled for that to hold:

* the pre-glom filters of ``chemicals.build_untyped_compendia()`` and ``chemicals.combine_unichem()``:
  ``remove_overused_xrefs`` (every untyped-stage concord, and the UniChem files of
  ``chemicals.UNICHEM_OVERUSED_XREF_PREFIXES``), from the CUI-follows-MeSH rule onward skipping pairs that name
  a UMLS CUI another pipeline owns, and from ``input_data/chemical_badxrefs.txt`` onward skipping its pairs;
* the post-glom split in ``chemicals.create_typed_sets()`` (Babel #83), which moves the ``MolecularMixture``-typed
  members of a clique whose PubChem CIDs disagree on type into a clique of their own. The split-off clique holds no
  InChIKey, while its CIDs' own UniChem keys stay with the parent, so each one is rejoined to the single keyed
  clique its CIDs' keys sit in. These rejoined groups are the **pre-split sets**: the sets ``glom()`` actually built.
* ``write_compendium()`` dropping the InChIKey from the output types whose Biolink class does not register the
  ``INCHIKEY`` prefix (``KEY_DROPPING_TYPES``: Drug and Food). Such a clique did hold its key when ``glom()`` ran, so
  a UniChem record->key edge whose record sits in one of these cliques and whose key is in no output was applied:
  it is reported as applied, with the key counted in the record's set. Outside these types a key missing from every
  output means something else (``glom()`` refused the pair and the key never reached a typed clique), so the
  inference is not made there.

A cross-clique edge that none of this explains means the model above no longer matches the pipeline, and
:func:`classify_chemical_glom_edges` raises rather than returning verdicts nobody can trust. On 2026jul22 every one
of the 132.5M chemical concord edges is explained.

Everything runs in DuckDB. CURIEs and clique leaders are joined as 64-bit hashes so a 256M-member compendium fits
in memory; a collision would merge two members' fates, and on 2026jul22 the 256,445,670 distinct CURIEs have
256,445,670 distinct hashes. The chemical ``Edge.parquet`` files are scanned once, into ``glom_node`` (one row per
CURIE) and ``glom_clique`` (one row per clique, with its leader and output type), which the audit reuses rather than
scanning them again.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.categories import DRUG, FOOD
from src.util import get_logger, sql_list, sql_str

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

# Chemical output types (``chemical_outputs`` names) whose Biolink class does not register the INCHIKEY prefix, so
# write_compendium() drops a clique's key on the way out. The model infers those dropped keys (see the module
# docstring), and checks this list against the build: a type here that still holds an InChIKey raises.
KEY_DROPPING_TYPES = frozenset(t.removeprefix("biolink:") for t in (DRUG, FOOD))


def classify_chemical_glom_edges(
    con,
    concord_parquet: str,
    edge_parquets: Mapping[str, str],
    chemical_concords: list[str],
    unichem_overused_prefixes: Iterable[str],
    owned_elsewhere: Iterable[str] = (),
    bad_pairs: Iterable[tuple[str, str]] = (),
) -> None:
    """Create table ``glom_edge`` in ``con``: one row per chemical concord edge with its verdict and pre-split sets.

    :param con: A DuckDB connection; the tables ``glom_node``, ``glom_clique``, ``keyed_clique``, ``presplit`` and
        ``glom_edge`` are (re)created in it.
    :param concord_parquet: The build's ``duckdb/Concord.parquet``.
    :param edge_parquets: Output type (a ``chemical_outputs`` name without ``.txt``) -> that compendium's
        ``Edge.parquet``, for every chemical output type.
    :param chemical_concords: ``config.yaml: chemical_concords`` -- the untyped-stage concord files glom() reads.
    :param unichem_overused_prefixes: ``chemicals.UNICHEM_OVERUSED_XREF_PREFIXES``.
    :param owned_elsewhere: UMLS CUIs the chemical compendium skips because another pipeline owns them
        (``umls.read_cuis_owned_elsewhere(mesh_ownership, "chemicals")``); empty for builds before that rule.
    :param bad_pairs: The bad xref pairs the build applied (``chemicals.read_applied_badxrefs()`` of its
        ``partials/applied_badxrefs.txt``), matched in either direction; empty for builds made before the file existed.

    Columns of ``glom_edge``: ``base`` (concord file name), ``is_unichem``, ``subj``, ``obj``, ``s_set``/``o_set``
    (hashed pre-split set of each endpoint, NULL if absent), ``key_dropped`` (a UniChem record->key edge whose key
    write_compendium() dropped; see ``KEY_DROPPING_TYPES``), ``verdict``. ``glom_clique`` has ``c`` (hashed leader),
    ``leader``, ``typ`` and ``has_key``.

    :raises RuntimeError: if any cross-clique edge is unexplained, a split-off clique maps to more than one parent,
        or a ``KEY_DROPPING_TYPES`` output holds an InChIKey -- each means this model has drifted from the pipeline.
    """
    # One scan of the Edge files. The leader column is NULL except on the leader's own row, so it costs little.
    scans = " UNION ALL ".join(
        f"""SELECT hash(curie) AS h, hash(clique_leader) AS c, curie LIKE 'INCHIKEY:%' AS is_key,
                   CASE WHEN curie = clique_leader THEN curie END AS leader, {sql_str(typ)} AS typ
            FROM read_parquet({sql_str(path)})"""
        for typ, path in edge_parquets.items()
    )
    con.sql(f"CREATE OR REPLACE TEMP TABLE member_row AS {scans}")
    con.sql("""
        CREATE OR REPLACE TABLE glom_clique AS
        SELECT c, any_value(leader) AS leader, any_value(typ) AS typ, bool_or(is_key) AS has_key
        FROM member_row GROUP BY c
    """)
    # A CURIE in more than one clique has no single fate; it is flagged here once instead of re-tested per join.
    con.sql("""
        CREATE OR REPLACE TABLE glom_node AS
        SELECT h, CASE WHEN count(DISTINCT c) = 1 THEN any_value(c) END AS c, count(DISTINCT c) > 1 AS ambiguous
        FROM member_row GROUP BY h
    """)
    con.sql("DROP TABLE member_row")
    key_dropping = sql_list(sorted(KEY_DROPPING_TYPES))
    keyed_droppers = con.sql(
        f"SELECT typ, count(*) FROM glom_clique WHERE has_key AND list_contains({key_dropping}, typ) GROUP BY typ"
    ).fetchall()
    if keyed_droppers:
        raise RuntimeError(
            f"chemical outputs {keyed_droppers} hold InChIKeys, but src/model/glom_edges.py lists them in "
            f"KEY_DROPPING_TYPES as types write_compendium() drops keys from. Update KEY_DROPPING_TYPES to the Biolink "
            f"classes that do not register INCHIKEY."
        )

    con.sql("CREATE OR REPLACE TEMP TABLE owned_elsewhere (curie VARCHAR)")
    owned = sorted(set(owned_elsewhere))
    if owned:
        con.executemany("INSERT INTO owned_elsewhere VALUES (?)", [(c,) for c in owned])
    con.sql("CREATE OR REPLACE TEMP TABLE bad_pair (a VARCHAR, b VARCHAR)")
    bad = sorted({p for s, o in bad_pairs for p in ((s, o), (o, s))})
    if bad:
        con.executemany("INSERT INTO bad_pair VALUES (?, ?)", bad)

    untyped = sql_list(chemical_concords)
    overused_unichem = sql_list(f"UNICHEM_{p}" for p in unichem_overused_prefixes)
    concords = sql_str(concord_parquet)
    unichem_dir = sql_str(f"%{UNICHEM_CONCORD_DIR}%")
    con.sql(f"""
        CREATE OR REPLACE TABLE glom_edge_raw AS
        WITH raw AS (
            SELECT regexp_extract(filename, '[^/]+$') AS base, filename LIKE {unichem_dir} AS is_unichem, subj, obj
            FROM read_parquet({concords})
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
        SELECT DISTINCT regexp_extract(filename, '[^/]+$') FROM read_parquet({concords})
        WHERE filename LIKE '%/chemicals/concords/%' AND filename NOT LIKE {unichem_dir}
          AND NOT list_contains({untyped}, regexp_extract(filename, '[^/]+$'))
    """).fetchall()
    if unknown_files:
        logger.info("chemical concord files not fed to glom() (not in chemical_concords): %s", unknown_files)

    con.sql(f"""
        CREATE OR REPLACE TABLE glom_edge_mapped AS
        SELECT r.*, ns.c AS sc, no.c AS oc,
               coalesce(ns.ambiguous, false) OR coalesce(no.ambiguous, false) AS ambiguous,
               -- A record->key edge into a Drug/Food clique whose key is in no output: write_compendium() dropped
               -- the key, so glom() applied the edge (see KEY_DROPPING_TYPES).
               r.is_unichem AND NOT r.overused AND no.h IS NULL AND r.obj LIKE 'INCHIKEY:%'
                 AND coalesce(list_contains({key_dropping}, k.typ), false) AS key_dropped
        FROM glom_edge_raw r
        LEFT JOIN glom_node ns ON ns.h = hash(r.subj)
        LEFT JOIN glom_node no ON no.h = hash(r.obj)
        LEFT JOIN glom_clique k ON k.c = ns.c
    """)
    con.sql("""
        CREATE OR REPLACE TABLE keyed_clique AS
        SELECT c FROM glom_clique WHERE has_key
        UNION
        SELECT DISTINCT sc FROM glom_edge_mapped WHERE key_dropped
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

    # The filters are listed in the order build_untyped_compendia() applies them: a bad-xref pair is matched before
    # the owned-elsewhere skip, so a pair that is both counts as a bad xref there and here.
    con.sql(f"""
        CREATE OR REPLACE TABLE glom_edge AS
        WITH s AS (
            SELECT m.*, coalesce(ps.parent, m.sc) AS s_set0, coalesce(po.parent, m.oc) AS o_set0
            FROM glom_edge_mapped m
            LEFT JOIN presplit ps ON ps.mix = m.sc
            LEFT JOIN presplit po ON po.mix = m.oc
        ), t AS (
            SELECT *, s_set0 AS s_set, CASE WHEN key_dropped THEN s_set0 ELSE o_set0 END AS o_set FROM s
        )
        SELECT base, is_unichem, subj, obj, s_set, o_set, key_dropped,
          CASE
            WHEN ambiguous THEN '{ENDPOINT_AMBIGUOUS}'
            WHEN badxref THEN '{FILTERED_BADXREF}'
            WHEN owned_elsewhere THEN '{FILTERED_OWNED_ELSEWHERE}'
            WHEN s_set IS NULL OR o_set IS NULL THEN '{ENDPOINT_ABSENT}'
            WHEN overused THEN '{FILTERED_OVERUSED}'
            WHEN s_set = o_set THEN '{APPLIED}'
            WHEN s_set IN (SELECT c FROM keyed_clique) AND o_set IN (SELECT c FROM keyed_clique)
              THEN '{REFUSED_INCHIKEY}'
            ELSE '{UNEXPLAINED}'
          END AS verdict
        FROM t
    """)
    con.sql("DROP TABLE glom_edge_raw")
    con.sql("DROP TABLE glom_edge_mapped")
    for verdict, n in con.sql("SELECT verdict, count(*) FROM glom_edge GROUP BY 1 ORDER BY 1").fetchall():
        logger.info("glom edges %s: %d", verdict, n)
    n_dropped = con.sql("SELECT count(*) FROM glom_edge WHERE key_dropped").fetchone()[0]
    logger.info("glom edges applied to a key write_compendium() dropped (Drug/Food): %d", n_dropped)
    unexplained = con.sql(f"SELECT count(*) FROM glom_edge WHERE verdict = '{UNEXPLAINED}'").fetchone()[0]
    if unexplained:
        examples = con.sql(f"SELECT base, subj, obj FROM glom_edge WHERE verdict = '{UNEXPLAINED}' LIMIT 5").fetchall()
        raise RuntimeError(
            f"{unexplained} chemical concord edges join different cliques with no filter or InChIKey refusal to "
            f"explain it, e.g. {examples}. The build was made by pipeline code this model does not describe; update "
            f"src/model/glom_edges.py before trusting any verdict it gives."
        )
