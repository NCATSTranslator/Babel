"""Audit what is attached to each chemical structure: find records that do not belong with the InChIKey they joined.

A keyed clique's InChIKey is its identity -- a real structure, carried by every record that has that structure. What
can be wrong is what else the xrefs attached to it.

``glom()`` runs the chemical pipeline with ``unique_prefixes=[INCHIKEY]``, so an xref joining two records that both
carry an InChIKey is refused. A record with no structure has no key to protect it: a single bad xref attaches a
biologic, polymer or mixture to an unrelated keyed clique, and because drug databases name the structure-less side
well, the clique often takes its name from it. Ofatumumab is the worked example: one DrugCentral ``identifier`` row,
``DrugCentral:4951 -> PUBCHEM.COMPOUND:8254``, puts the antibody's ChEMBL, DrugBank, GtoPdb, UNII and UMLS records
into the dimethyl-ether clique, which then displays as "Ofatumumab".

The audit works on a finished build (see :mod:`src.model.glom_edges` for why no replay is needed):

1. Per pre-split glom set that carries a key, take the applied non-UniChem xref edges.
2. The **core** is the key plus every member with an applied edge to an InChIKey (its own structure). Every other
   member is **structure-less**; the connected groups of structure-less members are **components**, each attached
   to the core by one or more **boundary edges**.
3. A component is flagged by how many *structure-bearing* sources (UniChem's sources,
   ``src.datahandlers.unichem.data_sources``) list one of its members without a structure: **tier A** for
   ``TIER_A_MIN_SOURCES`` or more, **tier B** for fewer; or **tier T** when no such source is involved but a member's
   declared Biolink type is not a small molecule (``NON_SMALL_MOLECULE_TYPES``). Several drug databases all recording
   something without a structure almost always means a biologic, polymer or mixture. Below tier A the signal is
   mostly noise: UniChem lags ChEBI and drops records under the overused filter, so those records only look
   structure-less.
4. Tier A is triaged by asking whether the core's structure *is* that substance (:func:`triage`): the core's heavy
   atom count (from the UniChem standard InChI) and agreement between the names on either side of the boundary,
   with the core named by its PubChem CIDs (:func:`core_naming_records`).

The verdicts are triage, not judgement. ``likely wrong`` covers both a **misattached** key (an unrelated substance)
and a **component** key (a real part of the substance -- an ADC payload, a polymer's monomer); ``matching key``
means the key looks like the structure of the substance itself (a peptide PubChem draws in full). Names are used
because the structure-less side has nothing else.
"""

from __future__ import annotations

import gzip
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from difflib import SequenceMatcher

from src.categories import CHEMICAL_MIXTURE, COMPLEX_MOLECULAR_MIXTURE, POLYPEPTIDE
from src.datahandlers.unichem import UNICHEM_STRUCT_TSV_HEADER
from src.datahandlers.unichem import data_sources as unichem_data_sources
from src.model.glom_edges import APPLIED, REFUSED_INCHIKEY
from src.prefixes import PUBCHEMCOMPOUND
from src.util import get_logger

logger = get_logger(__name__)

# Sources that normally record a structure: the ones UniChem covers. A member from one of these with no InChIKey of
# its own is "structure-less where a structure was expected".
STRUCTURE_SOURCE_PREFIXES = frozenset(unichem_data_sources.values())

# Declared Biolink types (from the chemical ids files) that say "not a small molecule". MolecularMixture is left out
# on purpose: it is how salts and hydrates are typed, and those legitimately carry a key.
NON_SMALL_MOLECULE_TYPES = (POLYPEPTIDE, COMPLEX_MOLECULAR_MIXTURE, CHEMICAL_MIXTURE)

# Tier A threshold. On 2026jul22 a cutoff of 3 isolates 196 of 4.5M components and holds 39 of the 47 cases in
# miner2049er's bad-InChIKey list; the sources are not independent (DrugCentral, DrugBank and UNII copy each other),
# so this is a heuristic cut, not three independent opinions.
TIER_A_MIN_SOURCES = 3

# Triage thresholds, set by reading all 196 tier A components of 2026jul22. Names agreeing at 0.6 or above cleared
# 127, almost all genuinely matching (insulins, GLP-1 analogues, ASOs, polymyxins). A core under 100 heavy atoms
# with disagreeing names was a real problem in nearly every case (ofatumumab -> dimethyl ether: 3 heavy atoms).
# A core under 20 heavy atoms is not cleared by names alone, because polymers whose representative structure is the
# monomer have matching names (PEG -> ethylene glycol, PVA -> ethanol).
NAME_AGREEMENT_MIN = 0.6
LARGE_CORE_HEAVY_ATOMS = 100
SMALL_CORE_HEAVY_ATOMS = 20

MATCHING_KEY = "matching key"
LIKELY_WRONG = "likely wrong"
REVIEW = "review"
NOT_TRIAGED = "not triaged"

# Tokens ignored when comparing names: counterions, pharmacopoeia tags and filler that make different substances
# look alike or the same substance look different.
_NAME_STOPWORDS = frozenset(
    {"sodium", "calcium", "potassium", "acetate", "hydrochloride", "human", "usp", "the", "and", "of", "salt"}
)


@dataclass(frozen=True)
class StructurelessComponent:
    """A connected group of structure-less members of one glom set, and the edges attaching it to the set's core.

    ``boundary`` holds ``(source, subj, obj)`` concord edges with one end in ``members`` and the other in the core.
    """

    set_id: int
    members: frozenset[str]
    boundary: tuple[tuple[str, str, str], ...]


def find_structureless_components(
    set_id: int, edges: Iterable[tuple[str, str, str, bool, bool]]
) -> list[StructurelessComponent]:
    """Split one glom set's structure-less members into connected components.

    :param set_id: The set the edges belong to.
    :param edges: Applied xref edges of the set as ``(source, subj, obj, subj_in_core, obj_in_core)``. Edges with
        both ends in the core are ignored.
    :returns: One component per connected group of structure-less members, in no particular order.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        root = parent.setdefault(x, x)
        while root != parent[root]:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    edges = list(edges)
    for _, subj, obj, subj_core, obj_core in edges:
        if not subj_core:
            find(subj)
        if not obj_core:
            find(obj)
        if not subj_core and not obj_core:
            parent[find(subj)] = find(obj)
    members: dict[str, set[str]] = defaultdict(set)
    for x in list(parent):
        members[find(x)].add(x)
    boundary: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for source, subj, obj, subj_core, obj_core in edges:
        if subj_core != obj_core:
            boundary[find(obj if subj_core else subj)].append((source, subj, obj))
    return [
        StructurelessComponent(set_id, frozenset(mem), tuple(sorted(boundary[root]))) for root, mem in members.items()
    ]


def structure_source_count(members: Iterable[str]) -> int:
    """How many distinct structure-bearing sources (``STRUCTURE_SOURCE_PREFIXES``) appear among ``members``."""
    return len({m.split(":", 1)[0] for m in members} & STRUCTURE_SOURCE_PREFIXES)


def tier_of(n_structure_sources: int, has_non_small_type: bool) -> str | None:
    """Tier ``A``, ``B`` or ``T`` for a component (see the module docstring), or None if it is not flagged."""
    if n_structure_sources >= TIER_A_MIN_SOURCES:
        return "A"
    if n_structure_sources > 0:
        return "B"
    if has_non_small_type:
        return "T"
    return None


def heavy_atoms_from_inchi(inchi: str) -> int:
    """Count non-hydrogen atoms in a standard InChI's formula layer, across all components.

    ``InChI=1S/2C2H4O2.Ca/...`` (calcium acetate) is 2 x (2 C + 2 O) + 1 Ca = 9.

    :raises ValueError: if the string has no formula layer.
    """
    layers = inchi.split("/")
    if len(layers) < 2 or not layers[0].startswith("InChI="):
        raise ValueError(f"not a standard InChI: {inchi!r}")
    total = 0
    for part in layers[1].split("."):
        match = re.fullmatch(r"(\d*)(.*)", part)
        multiplier = int(match.group(1)) if match.group(1) else 1
        for element, count in re.findall(r"([A-Z][a-z]?)(\d*)", match.group(2)):
            if element != "H":
                total += multiplier * (int(count) if count else 1)
    return total


def _name_tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) > 2 and t not in _NAME_STOPWORDS}


def name_agreement(labels_a: Iterable[str], labels_b: Iterable[str]) -> float:
    """Best agreement between any label on one side and any label on the other, in [0, 1].

    Each pair scores the larger of its token Jaccard similarity and its character-sequence ratio. This is a triage
    signal for cases where one side has nothing but names; a fuzzy match can pair different substances with similar
    names (asparaginase / asparaginate), which is why :func:`triage` never trusts it alone on a small core.
    """
    labels_a = [a for a in labels_a if a]
    labels_b = [b for b in labels_b if b]
    best = 0.0
    for a in labels_a:
        ta = _name_tokens(a)
        for b in labels_b:
            tb = _name_tokens(b)
            jaccard = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
            best = max(best, jaccard, SequenceMatcher(None, a.lower(), b.lower()).ratio())
    return best


def core_naming_records(core_curies: Iterable[str]) -> list[str]:
    """The core records whose labels say what the core's structure is: its PubChem CIDs, or every core record when
    it has none.

    A core record carrying the structure-less substance's name is a symptom of the error, not evidence against it.
    In 2026jul22 the chymopapain set's core is Tiron (PubChem CID 9002), yet CHEBI:193860 and HMDB:HMDB0029845,
    both with Tiron's structure, are labelled "Chymopapain"; taking the best name match over every core label
    cleared it, and likewise thyrotropin alfa -> TRH, defibrotide and lipegfilgrastim. PubChem titles a CID from its
    structure's depositors, so it is the one label that follows the structure. The cost is that a CID titled by its
    IUPAC name or "CID nnn" fails to match, which sends genuine matches to review or likely wrong -- the safe
    direction for a list of edges to block.
    """
    core_curies = list(core_curies)
    pubchem = [c for c in core_curies if c.startswith(f"{PUBCHEMCOMPOUND}:")]
    return pubchem or core_curies


def triage(name_score: float, core_heavy_atoms: int | None) -> str:
    """Triage a tier A component from name agreement and the size of the core's structure.

    * names agree and the core is not tiny -> ``matching key``;
    * names disagree and the core is small-molecule sized -> ``likely wrong``;
    * otherwise (names agree on a tiny core, names disagree on a large core, or no structure for the key) ->
      ``review``.
    """
    if core_heavy_atoms is None:
        return REVIEW
    names_agree = name_score >= NAME_AGREEMENT_MIN
    if names_agree and core_heavy_atoms >= SMALL_CORE_HEAVY_ATOMS:
        return MATCHING_KEY
    if not names_agree and core_heavy_atoms < LARGE_CORE_HEAVY_ATOMS:
        return LIKELY_WRONG
    return REVIEW


def read_inchis(structure_file: str, inchikeys: Iterable[str]) -> dict[str, str]:
    """Standard InChIs for the given ``INCHIKEY:`` CURIEs, streamed from UniChem's ``structure.tsv.gz``.

    The file is ~12 GB, so it is read once, line by line, keeping only the keys asked for. A key absent from the
    file is absent from the result; callers report it rather than guessing a size.
    """
    wanted = {k.split(":", 1)[1] for k in inchikeys}
    found: dict[str, str] = {}
    with gzip.open(structure_file, "rt") as inf:
        header = inf.readline()
        if header != UNICHEM_STRUCT_TSV_HEADER:
            raise ValueError(f"unexpected header in {structure_file}: {header!r}")
        for line in inf:
            _, inchi, key = line.rstrip("\n").split("\t")
            if key in wanted:
                found[f"INCHIKEY:{key}"] = inchi
                if len(found) == len(wanted):
                    break
    return found


def _iter_sets(rows: Iterator[tuple]) -> Iterator[tuple[int, list[tuple[str, str, str, bool, bool]]]]:
    """Group ``(set_id, source, subj, obj, subj_core, obj_core)`` rows, sorted by set_id, into per-set edge lists."""
    current, edges = None, []
    for set_id, *edge in rows:
        if set_id != current and edges:
            yield current, edges
            edges = []
        current = set_id
        edges.append(tuple(edge))
    if edges:
        yield current, edges


def _fetch_batches(result, size: int = 100_000) -> Iterator[tuple]:
    while batch := result.fetchmany(size):
        yield from batch


def audit_chemical_inchikeys(
    con,
    work_dir: str,
    edge_parquets: list[str],
    node_parquets: list[str],
    identifier_parquet: str,
    structure_file: str,
) -> None:
    """Run steps 1-4 over the ``glom_edge`` table that :func:`src.model.glom_edges.classify_chemical_glom_edges`
    built in ``con``, and create the result tables ``audit_component`` (one row per flagged component) and
    ``audit_boundary`` (one row per boundary edge of a flagged component). ``work_dir`` holds intermediate TSVs.
    """
    con.sql(f"""
        CREATE OR REPLACE TABLE xedge0 AS
        SELECT s_set AS set_id, base, subj, obj FROM glom_edge
        WHERE verdict = '{APPLIED}' AND NOT is_unichem
          AND subj NOT LIKE 'INCHIKEY:%' AND obj NOT LIKE 'INCHIKEY:%'
          AND s_set IN (SELECT c FROM keyed_clique)
    """)
    con.sql(f"""
        CREATE OR REPLACE TABLE structured AS
        WITH ends AS (SELECT subj AS curie FROM xedge0 UNION SELECT obj FROM xedge0)
        SELECT DISTINCT subj AS curie FROM glom_edge
        WHERE verdict = '{APPLIED}' AND obj LIKE 'INCHIKEY:%' AND subj IN (SELECT curie FROM ends)
        UNION
        SELECT DISTINCT obj FROM glom_edge
        WHERE verdict = '{APPLIED}' AND subj LIKE 'INCHIKEY:%' AND obj IN (SELECT curie FROM ends)
    """)
    rows = con.execute("""
        SELECT set_id, base, subj, obj, s1.curie IS NOT NULL, s2.curie IS NOT NULL
        FROM xedge0 x LEFT JOIN structured s1 ON s1.curie = x.subj LEFT JOIN structured s2 ON s2.curie = x.obj
        WHERE s1.curie IS NULL OR s2.curie IS NULL
        ORDER BY set_id
    """)
    member_tsv, boundary_tsv = f"{work_dir}/component_member.tsv", f"{work_dir}/component_boundary.tsv"
    n_components = 0
    with open(member_tsv, "w") as mf, open(boundary_tsv, "w") as bf:
        mf.write("set_id\tcomp\tcurie\n")
        bf.write("set_id\tcomp\tsource\tsubj\tobj\n")
        for set_id, edges in _iter_sets(_fetch_batches(rows)):
            for i, comp in enumerate(find_structureless_components(set_id, edges)):
                n_components += 1
                for m in sorted(comp.members):
                    mf.write(f"{set_id}\t{i}\t{m}\n")
                for source, subj, obj in comp.boundary:
                    bf.write(f"{set_id}\t{i}\t{source}\t{subj}\t{obj}\n")
    logger.info("found %d structure-less components", n_components)
    tsv = "delim='\\t', header=true, quote='', escape='', all_varchar=true"
    con.sql(f"""CREATE OR REPLACE TABLE comp_member AS
        SELECT CAST(set_id AS UBIGINT) set_id, CAST(comp AS INT) comp, curie FROM read_csv('{member_tsv}', {tsv})""")
    con.sql(f"""CREATE OR REPLACE TABLE comp_boundary AS
        SELECT CAST(set_id AS UBIGINT) set_id, CAST(comp AS INT) comp, source, subj, obj
        FROM read_csv('{boundary_tsv}', {tsv})""")

    # Declared types of component members, from the chemical ids files.
    types = "[" + ",".join(f"'{t}'" for t in NON_SMALL_MOLECULE_TYPES) + "]"
    con.sql(f"""
        CREATE OR REPLACE TABLE member_type AS
        SELECT DISTINCT curie, biolink_type FROM read_parquet('{identifier_parquet}')
        WHERE filename LIKE '%/chemicals/ids/%' AND curie IN (SELECT curie FROM comp_member)
    """)
    structure_prefixes = "[" + ",".join(f"'{p}'" for p in sorted(STRUCTURE_SOURCE_PREFIXES)) + "]"
    con.sql(f"""
        CREATE OR REPLACE TABLE comp_flag AS
        SELECT m.set_id, m.comp, count(*) AS n_members,
               count(DISTINCT split_part(m.curie, ':', 1))
                 FILTER (WHERE list_contains({structure_prefixes}, split_part(m.curie, ':', 1))) AS n_structure_sources,
               bool_or(list_contains({types}, t.biolink_type)) AS has_non_small_type,
               list(DISTINCT t.biolink_type) FILTER (WHERE t.biolink_type IS NOT NULL) AS declared_types
        FROM comp_member m LEFT JOIN member_type t USING (curie)
        GROUP BY m.set_id, m.comp
    """)
    # Exactly the components tier_of() flags; the tier itself is assigned below, in Python, by tier_of().
    con.sql("""
        CREATE OR REPLACE TABLE flagged AS
        SELECT * FROM comp_flag WHERE n_structure_sources > 0 OR coalesce(has_non_small_type, false)
    """)

    # The core of each flagged set: records with an applied edge to the set's InChIKey, and the key itself.
    con.sql(f"""
        CREATE OR REPLACE TABLE set_core AS
        SELECT DISTINCT s_set AS set_id, CASE WHEN obj LIKE 'INCHIKEY:%' THEN subj ELSE obj END AS curie,
               CASE WHEN obj LIKE 'INCHIKEY:%' THEN obj ELSE subj END AS inchikey
        FROM glom_edge
        WHERE verdict = '{APPLIED}' AND (obj LIKE 'INCHIKEY:%' OR subj LIKE 'INCHIKEY:%')
          AND s_set IN (SELECT DISTINCT set_id FROM flagged)
    """)
    multi_key = con.sql(
        "SELECT count(*) FROM (SELECT set_id FROM set_core GROUP BY 1 HAVING count(DISTINCT inchikey) > 1)"
    )
    if multi_key.fetchone()[0]:
        raise RuntimeError("a pre-split chemical glom set holds more than one InChIKey; glom()'s guard forbids that")
    con.sql(f"""
        CREATE OR REPLACE TABLE set_leader AS
        SELECT DISTINCT hash(clique_leader) AS set_id, clique_leader FROM read_parquet({_list(edge_parquets)})
        WHERE hash(clique_leader) IN (SELECT DISTINCT set_id FROM flagged)
    """)
    con.sql(f"""
        CREATE OR REPLACE TABLE label AS
        SELECT curie, any_value(label) AS label FROM read_parquet({_list(node_parquets)})
        WHERE curie IN (SELECT curie FROM comp_member JOIN flagged USING (set_id, comp)
                        UNION SELECT curie FROM set_core UNION SELECT clique_leader FROM set_leader)
        GROUP BY curie
    """)
    labels = dict(con.sql("SELECT curie, label FROM label WHERE label IS NOT NULL AND label <> ''").fetchall())
    keys = [k for (k,) in con.sql("SELECT DISTINCT inchikey FROM set_core").fetchall()]
    inchis = read_inchis(structure_file, keys)
    missing = len(set(keys) - set(inchis))
    if missing:
        logger.warning(
            "%d of %d core InChIKeys are not in %s; their components triage as review",
            missing,
            len(keys),
            structure_file,
        )

    core: dict[int, tuple[str, list[str]]] = {}
    for set_id, key, curies in con.sql(
        "SELECT set_id, any_value(inchikey), list(curie) FROM set_core GROUP BY 1"
    ).fetchall():
        core[set_id] = (key, curies)
    members: dict[tuple[int, int], list[str]] = defaultdict(list)
    for set_id, comp, curie in con.sql(
        "SELECT set_id, comp, curie FROM comp_member JOIN flagged USING (set_id, comp)"
    ).fetchall():
        members[(set_id, comp)].append(curie)

    out_tsv = f"{work_dir}/component_triage.tsv"
    with open(out_tsv, "w") as f:
        f.write(
            "set_id\tcomp\ttier\tinchikey\tcore_heavy_atoms\tname_score\tverdict\tstructureless_labels\tcore_labels\n"
        )
        flagged = con.sql("SELECT set_id, comp, n_structure_sources, coalesce(has_non_small_type, false) FROM flagged")
        for set_id, comp, n_sources, non_small in flagged.fetchall():
            tier = tier_of(n_sources, non_small)
            key, core_curies = core.get(set_id, (None, []))
            sl_labels = sorted({labels[m] for m in members[(set_id, comp)] if m in labels})
            core_labels = sorted({labels[c] for c in core_naming_records(core_curies) if c in labels})
            score = name_agreement(sl_labels, core_labels)
            heavy = heavy_atoms_from_inchi(inchis[key]) if key in inchis else None
            verdict = triage(score, heavy) if tier == "A" else NOT_TRIAGED
            clean = [" | ".join(x).replace("\t", " ").replace("\n", " ") for x in (sl_labels, core_labels)]
            f.write(
                f"{set_id}\t{comp}\t{tier}\t{key or ''}\t{'' if heavy is None else heavy}\t{score:.2f}\t{verdict}\t"
                f"{clean[0]}\t{clean[1]}\n"
            )
    con.sql(f"""CREATE OR REPLACE TABLE comp_triage AS
        SELECT CAST(set_id AS UBIGINT) set_id, CAST(comp AS INT) comp, tier, inchikey,
               TRY_CAST(core_heavy_atoms AS INT) core_heavy_atoms, CAST(name_score AS DOUBLE) name_score, verdict,
               structureless_labels, core_labels
        FROM read_csv('{out_tsv}', {tsv})""")

    con.sql("""
        CREATE OR REPLACE TABLE audit_component AS
        SELECT l.clique_leader, ll.label AS clique_leader_label, t.inchikey, t.tier, t.verdict,
               f.n_structure_sources, f.n_members, t.core_heavy_atoms, t.name_score,
               (SELECT string_agg(DISTINCT b.source, ',') FROM comp_boundary b
                 WHERE b.set_id = f.set_id AND b.comp = f.comp) AS boundary_sources,
               (SELECT count(*) FROM comp_boundary b WHERE b.set_id = f.set_id AND b.comp = f.comp) AS n_boundary,
               array_to_string(f.declared_types, ',') AS declared_types,
               (SELECT string_agg(m.curie, ' ' ORDER BY m.curie) FROM comp_member m
                 WHERE m.set_id = f.set_id AND m.comp = f.comp) AS structureless_members,
               t.structureless_labels, t.core_labels, f.set_id, f.comp
        FROM flagged f JOIN comp_triage t USING (set_id, comp)
        LEFT JOIN set_leader l USING (set_id) LEFT JOIN label ll ON ll.curie = l.clique_leader
        ORDER BY t.tier, t.verdict, l.clique_leader
    """)
    con.sql("""
        CREATE OR REPLACE TABLE audit_boundary AS
        SELECT c.clique_leader, c.inchikey, c.tier, c.verdict, b.source, b.subj, ls.label AS subj_label,
               b.obj, lo.label AS obj_label
        FROM audit_component c JOIN comp_boundary b USING (set_id, comp)
        LEFT JOIN label ls ON ls.curie = b.subj LEFT JOIN label lo ON lo.curie = b.obj
        ORDER BY c.tier, c.verdict, b.source, b.subj
    """)


def refused_edges_query() -> str:
    """SQL over ``glom_edge`` listing xrefs the InChIKey guard refused: harmless in the build, but source errors."""
    return f"""
        SELECT base AS source, subj, obj FROM glom_edge
        WHERE verdict = '{REFUSED_INCHIKEY}' AND NOT is_unichem ORDER BY source, subj, obj
    """


def _list(paths: Iterable[str]) -> str:
    return "[" + ",".join(f"'{p}'" for p in paths) + "]"
