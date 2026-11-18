"""Count what the Protein compendium holds besides specific protein sequences, for docs/biolink/ProteinFamily.md.

The protein-family discussion (Babel #1170, #849) turns on how many of the Protein compendium's cliques name a
grouping (a family, a species-neutral gene product, a MeSH descriptor) rather than one sequence, and on what the
sources Babel already ingests say about that level. This script measures both against a published build and
writes a short Markdown report plus the per-row CSVs behind it:

1. Protein cliques by leader prefix and by whether any member is a UniProtKB or ENSEMBL accession (a "sequence"
   identifier), with MeSH descriptors (``MESH:D...``) split from supplementary records (``MESH:C...``).
2. Protein Ontology's per-term ``Category=`` annotation (organism-gene, gene, family, ...), read from UberGraph,
   and where the family-level PR terms sit in the build's Protein cliques (``pr_family_terms.csv``).
3. MeSH's own structure under D12.776 "Proteins": for each descriptor, how many narrower descriptors and how
   many supplementary records map to it (``mesh_d12_776_descriptors_top200.csv``), read by streaming ``mesh.nt``.
4. GeneFamily cliques whose preferred name is also the preferred name of a Protein or chemical clique, the
   direct measure of the "two Claudins" complaint in Feedback #1429 (``genefamily_label_collisions.csv``).
5. A crude plural/"family" label heuristic over the non-UniProtKB-led Protein cliques, with a fixed random
   sample for hand-checking (``label_heuristic_sample.csv``). The heuristic is reported, not trusted.

The build's Parquet exports are read in place over https (``--build-url`` is the published build's root, e.g.
``.../var/babel/<build>``; see "Querying a published build in place" in docs/DataFormats.md). The three remote
scans take about seven minutes in all and are cached as Parquet under ``--cache-dir`` so a re-run that only
changes the report is seconds; ``--skip-remote`` insists on the cache. MeSH comes from a local download
(``uv run snakemake --cores 1 get_mesh``). Example:

    uv run python docs/biolink/protein-family/scripts/count_protein_concept_levels.py \\
        --build-url https://stars.renci.org/var/babel/2026jul22 --build-name 2026jul22 \\
        --output-dir docs/biolink/protein-family --cache-dir data/protein-family
"""

import argparse
import csv
import os
import re
import sys
import textwrap
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from src.datahandlers.mesh import get_mesh_id_from_iri  # noqa: E402
from src.prefixes import DRUGBANK, ENSEMBL, MESH, NCIT, PR, UMLS, UNIPROTKB  # noqa: E402
from src.util import get_config  # noqa: E402

# A member with one of these prefixes means the clique names a specific sequence (protein.py's uniques are
# UniProtKB and PR, but PR also has family- and gene-level terms, so it does not count here).
SEQUENCE_PREFIXES = (UNIPROTKB, ENSEMBL)
# The non-sequence prefixes whose rows the report keeps from the Protein Edge table.
CONCEPT_PREFIXES = (UMLS, MESH, NCIT, DRUGBANK, PR)
PROTEIN_TREE = "D12.776"
UBERGRAPH = "https://ubergraph.apps.renci.org/sparql"
MESH_VOCAB = "<http://id.nlm.nih.gov/mesh/vocab#"
# The PR categories that name a grouping of proteins rather than one gene product or sequence.
PR_FAMILY_CATEGORIES = ("family", "organism-family")
# Worked examples the report always shows, whatever the counts (the four concepts in #1429/#1170/#849).
MESH_EXAMPLES = ("D057167", "D008074", "D006454", "D007328", "D003094", "D007378")

# The label heuristic. Order matters: the first pattern that matches names the class.
PLURAL_PROTEIN_WORDS = (
    "proteins|receptors|enzymes|factors|kinases|antigens|antibodies|globulins|hormones|peptides|toxins|subunits|"
    "chains|isoforms|lipoproteins|hemoglobins|interleukins|cytokines|integrins|channels|transporters|ligands|"
    "inhibitors|ases|ins"
)
HEURISTIC = [
    ("family-word", re.compile(r"\b(famil(y|ies)|superfamily|subfamily)\b")),
    ("plural-protein-word", re.compile(rf"({PLURAL_PROTEIN_WORDS})$")),
    ("ends-in-s", re.compile(r"[a-rt-z]s$")),
]
NOT_PLURAL_ENDINGS = re.compile(r"(ss|us|is|os|ys)$")


def classify_label(label):
    text = (label or "").lower()
    for name, pattern in HEURISTIC:
        if pattern.search(text) and not (name == "ends-in-s" and NOT_PLURAL_ENDINGS.search(text)):
            return name
    return "singular"


def parquet_url(build_url, compendium, table):
    return f"{build_url}/duckdb/parquet/filename%3D{compendium}/{table}.parquet"


def cached(con, name, cache_dir, skip_remote, build_sql):
    """Create table ``name`` from the cache, or by running ``build_sql`` and caching its result."""
    path = os.path.join(cache_dir, f"{name}.parquet")
    if os.path.exists(path):
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{path}')")
        return
    if skip_remote:
        raise RuntimeError(f"--skip-remote given but {path} is missing")
    start = time.time()
    con.execute(f"CREATE TABLE {name} AS {build_sql}")
    con.execute(f"COPY {name} TO '{path}'")
    print(f"  built {name} in {time.time() - start:.0f}s", file=sys.stderr)


def load_build_tables(con, build_url, cache_dir, skip_remote):
    """The Protein compendium's clique summary and concept-prefix edges, the GeneFamily cliques, and label joins."""
    seq = ", ".join(f"'{p}'" for p in SEQUENCE_PREFIXES)
    concept = ", ".join(f"'{p}'" for p in CONCEPT_PREFIXES)
    edge = parquet_url(build_url, "Protein", "Edge")
    # One row per Protein clique: its leader prefix, whether it has a sequence member, and its size.
    cached(
        con,
        "protein_cliques",
        cache_dir,
        skip_remote,
        f"""SELECT clique_leader, any_value(clique_leader_prefix) AS leader_prefix,
                   max(CASE WHEN curie_prefix IN ({seq}) THEN 1 ELSE 0 END) AS has_sequence,
                   count(*) AS size
            FROM read_parquet('{edge}') GROUP BY clique_leader""",
    )
    # The Protein compendium's rows for the non-sequence prefixes.
    cached(
        con,
        "protein_concept_edges",
        cache_dir,
        skip_remote,
        f"SELECT clique_leader, curie, curie_prefix FROM read_parquet('{edge}') WHERE curie_prefix IN ({concept})",
    )
    # Preferred names of the Protein cliques not led by a sequence accession (the heuristic's population).
    not_sequence_led = " AND ".join(f"NOT starts_with(clique_leader, '{p}:')" for p in SEQUENCE_PREFIXES)
    cached(
        con,
        "protein_concept_cliques",
        cache_dir,
        skip_remote,
        f"""SELECT clique_leader, preferred_name, clique_identifier_count
            FROM read_parquet('{parquet_url(build_url, "Protein", "Clique")}')
            WHERE {not_sequence_led}""",
    )
    cached(
        con,
        "genefamily_cliques",
        cache_dir,
        skip_remote,
        f"""SELECT clique_leader, preferred_name, clique_identifier_count
            FROM read_parquet('{parquet_url(build_url, "GeneFamily", "Clique")}')""",
    )
    # Protein and chemical cliques sharing a GeneFamily clique's preferred name (case-insensitive).
    for compendium in ("Protein", "ChemicalEntity", "SmallMolecule"):
        cached(
            con,
            f"collisions_{compendium.lower()}",
            cache_dir,
            skip_remote,
            f"""SELECT '{compendium}' AS compendium, clique_leader, preferred_name, clique_identifier_count
                FROM read_parquet('{parquet_url(build_url, compendium, "Clique")}')
                WHERE lower(preferred_name) IN (SELECT DISTINCT lower(preferred_name) FROM genefamily_cliques)""",
        )


def sparql(query):
    url = UBERGRAPH + "?" + urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(url, headers={"Accept": "text/tab-separated-values"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        lines = resp.read().decode().splitlines()
    rows = []
    for line in lines[1:]:
        rows.append([re.sub(r'^"(.*)"(\^\^<[^>]*>|@[a-z]+)?$', r"\1", cell) for cell in line.split("\t")])
    return rows


def fetch_pr_categories():
    """PR's ``Category=<x>.`` comment per term, as (counts by category, [(curie, label, category)] for families)."""
    prefix = "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
    pr_filter = 'FILTER(STRSTARTS(STR(?t), "http://purl.obolibrary.org/obo/PR_"))'
    # An obsolete term's comment reads "Category (was) gene. ..."; a few terms carry a free-text comment instead.
    counts = sparql(
        prefix + "SELECT ?cat (COUNT(DISTINCT ?t) AS ?n) WHERE { ?t rdfs:comment ?c . " + pr_filter + " "
        'FILTER(STRSTARTS(STR(?c), "Category")) '
        'BIND(REPLACE(STR(?c), "^Category=([a-zA-Z-]+)\\\\..*$", "$1") AS ?cat) } GROUP BY ?cat ORDER BY ?cat'
    )
    categories = {cat: int(n) for cat, n in counts if not cat.startswith("Category (was)")}
    retired = sum(int(n) for cat, n in counts if cat.startswith("Category (was)"))
    families = []
    for category in PR_FAMILY_CATEGORIES:
        rows = sparql(
            prefix + "SELECT ?t ?l WHERE { ?t rdfs:label ?l ; rdfs:comment ?c . " + pr_filter + " "
            f'FILTER(STRSTARTS(STR(?c), "Category={category}.")) }} ORDER BY ?t'
        )
        families.extend((f"{PR}:{iri.strip('<>').rsplit('PR_', 1)[1]}", label, category) for iri, label in rows)
    return categories, retired, families


def read_mesh(mesh_nt):
    """Stream mesh.nt once: labels, tree numbers and SCR mappings, without loading it into a triple store."""
    labels, trees, parent_tree, mapped = {}, defaultdict(list), {}, defaultdict(set)
    tree_owner = {}
    with open(mesh_nt) as inf:
        for line in inf:
            subject, predicate, rest = line.split(" ", 2)
            if predicate == "<http://www.w3.org/2000/01/rdf-schema#label>":
                if subject.startswith("<http://id.nlm.nih.gov/mesh/D") or subject.startswith(
                    "<http://id.nlm.nih.gov/mesh/C"
                ):
                    labels[get_mesh_id_from_iri(subject.strip("<>"))] = rest.split('"')[1]
            elif not predicate.startswith(MESH_VOCAB):
                continue
            elif predicate == MESH_VOCAB + "treeNumber>":
                descriptor = get_mesh_id_from_iri(subject.strip("<>"))
                tree = rest.split(">")[0].rsplit("/", 1)[1]
                trees[descriptor].append(tree)
                tree_owner[tree] = descriptor
            elif predicate == MESH_VOCAB + "parentTreeNumber>":
                parent_tree[subject.rsplit("/", 1)[1].rstrip(">")] = rest.split(">")[0].rsplit("/", 1)[1]
            elif predicate in (MESH_VOCAB + "mappedTo>", MESH_VOCAB + "preferredMappedTo>"):
                scr = get_mesh_id_from_iri(subject.strip("<>"))
                # A mapping target may be a descriptor-qualifier pair (D000117Q000031); keep the descriptor.
                target = rest.split(">")[0].rsplit("/", 1)[1].split("Q")[0]
                if scr.startswith("C"):
                    mapped[target].add(scr)
    children = Counter()
    for tree, parent in parent_tree.items():
        if tree in tree_owner and parent in tree_owner:
            children[tree_owner[parent]] += 1
    return labels, trees, children, mapped


def mesh_descriptor_rows(con, mesh_nt):
    labels, trees, children, mapped = read_mesh(mesh_nt)
    in_protein = {}
    for curie, leader, has_sequence in con.execute(
        """SELECT e.curie, e.clique_leader, c.has_sequence FROM protein_concept_edges e
           JOIN protein_cliques c USING (clique_leader) WHERE e.curie_prefix = ?""",
        [MESH],
    ).fetchall():
        in_protein[curie.split(":", 1)[1]] = (leader, has_sequence)
    rows = []
    for descriptor, tree_numbers in sorted(trees.items()):
        protein_trees = sorted(t for t in tree_numbers if t.startswith(PROTEIN_TREE))
        if not protein_trees:
            continue
        leader, has_sequence = in_protein.get(descriptor, ("", ""))
        rows.append(
            {
                "descriptor": f"{MESH}:{descriptor}",
                "label": labels.get(descriptor, ""),
                "protein_tree_numbers": ";".join(protein_trees),
                "other_tree_numbers": ";".join(sorted(t for t in tree_numbers if not t.startswith(PROTEIN_TREE))),
                "narrower_descriptors": children.get(descriptor, 0),
                "mapped_scrs": len(mapped.get(descriptor, ())),
                "protein_clique_leader": leader,
                "clique_has_sequence": has_sequence,
            }
        )
    return rows, labels


def genefamily_kind(curie):
    if curie.startswith("HGNC.FAMILY:"):
        return "HGNC.FAMILY"
    return "PANTHER subfamily" if ":SF" in curie else "PANTHER family"


def bucket(n):
    return "0" if n == 0 else "1" if n == 1 else "2+"


def fmt(n):
    return f"{n:,}"


def write_csv(path, rows, fields):
    with open(path, "w", newline="") as outf:
        writer = csv.DictWriter(outf, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-url", required=True, help="A published build's root, e.g. .../var/babel/<build>")
    ap.add_argument("--build-name", required=True, help="Names the report, e.g. 2026jul22")
    ap.add_argument("--output-dir", required=True, help="Where <build-name>.md and the CSVs go")
    ap.add_argument("--cache-dir", required=True, help="Where the remote scans are cached as Parquet")
    ap.add_argument("--mesh-nt", default=os.path.join(get_config()["download_directory"], "MESH", "mesh.nt"))
    ap.add_argument("--skip-remote", action="store_true", help="Fail rather than scan the build over https")
    ap.add_argument("--sample-size", type=int, default=200)
    args = ap.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.cache_dir, exist_ok=True)

    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    load_build_tables(con, args.build_url, args.cache_dir, args.skip_remote)
    out = []
    w = out.append

    w(f"# What the Protein compendium holds besides sequences: the {args.build_name} build\n")
    w(
        "Generated by `docs/biolink/protein-family/scripts/count_protein_concept_levels.py` (see its docstring) "
        f"from the {args.build_name} build's Parquet exports, Protein Ontology categories in UberGraph, and a "
        "local MeSH download. Read with [`../ProteinFamily.md`](../ProteinFamily.md).\n"
    )

    # 1. Cliques by leader prefix and sequence membership.
    w("## 1. Protein cliques by leader prefix and by whether a member names a sequence\n")
    w(
        f'A clique "has a sequence" when some member is a {" or ".join(SEQUENCE_PREFIXES)} accession. Every other '
        "clique is a concept that Babel types `biolink:Protein` without a sequence behind it: a UMLS CUI, a MeSH "
        "descriptor or supplementary record, an NCIt concept, or a Protein Ontology term above the organism level.\n"
    )
    w("| leader prefix | cliques | with a sequence | without | without, as % of prefix |")
    w("|---|---:|---:|---:|---:|")
    total = Counter()
    for prefix, n, with_seq in con.execute(
        "SELECT leader_prefix, count(*), sum(has_sequence) FROM protein_cliques GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall():
        without = n - with_seq
        total["n"] += n
        total["with"] += with_seq
        w(f"| {prefix} | {fmt(n)} | {fmt(with_seq)} | {fmt(without)} | {100 * without / n:.1f}% |")
    w(f"| **all** | {fmt(total['n'])} | {fmt(total['with'])} | {fmt(total['n'] - total['with'])} | |")
    w("")
    w("Identifiers of the non-sequence prefixes, by whether their clique has a sequence:\n")
    w("| prefix | kind | in a clique with a sequence | in a clique without |")
    w("|---|---|---:|---:|")
    for prefix, kind, with_seq, without in con.execute(
        f"""SELECT e.curie_prefix,
                   CASE WHEN e.curie_prefix = '{MESH}' AND substr(e.curie, {len(MESH) + 2}, 1) = 'D' THEN 'descriptor'
                        WHEN e.curie_prefix = '{MESH}' THEN 'supplementary record' ELSE '' END AS kind,
                   sum(c.has_sequence), sum(1 - c.has_sequence)
            FROM protein_concept_edges e JOIN protein_cliques c USING (clique_leader)
            GROUP BY 1, 2 ORDER BY 1, 2"""
    ).fetchall():
        w(f"| {prefix} | {kind} | {fmt(with_seq)} | {fmt(without)} |")
    w("")

    # 2. PR categories.
    w("## 2. Protein Ontology categories, and where the family-level terms sit\n")
    categories, retired, families = fetch_pr_categories()
    w(
        "Every PR term carries `Category=<level>.` in its `rdfs:comment` (UberGraph). Babel ingests every subclass of "
        "`PR:000000001` as `biolink:Protein` and does not read the category.\n"
    )
    w("| category | terms |")
    w("|---|---:|")
    for category, n in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0])):
        w(f"| {category} | {fmt(n)} |")
    w(f"| (obsolete, `Category (was) ...`) | {fmt(retired)} |")
    w("")
    family_curies = {curie for curie, _, _ in families}
    placement = {}
    for curie, leader, leader_prefix, has_sequence, size in con.execute(
        """SELECT e.curie, c.clique_leader, c.leader_prefix, c.has_sequence, c.size
           FROM protein_concept_edges e JOIN protein_cliques c USING (clique_leader) WHERE e.curie_prefix = ?""",
        [PR],
    ).fetchall():
        if curie in family_curies:
            placement[curie] = (leader, leader_prefix, has_sequence, size)
    family_rows = []
    for curie, label, category in sorted(families):
        leader, leader_prefix, has_sequence, size = placement.get(curie, ("", "", "", 0))
        family_rows.append(
            {
                "curie": curie,
                "label": label,
                "pr_category": category,
                "protein_clique_leader": leader,
                "clique_has_sequence": has_sequence,
                "clique_size": size,
            }
        )
    write_csv(os.path.join(args.output_dir, "pr_family_terms.csv"), family_rows, list(family_rows[0]))
    summary = Counter()
    for row in family_rows:
        if not row["protein_clique_leader"]:
            summary["not in the Protein compendium"] += 1
        elif row["clique_has_sequence"]:
            summary["in a clique with a sequence"] += 1
        elif row["clique_size"] == 1:
            summary["a singleton clique"] += 1
        else:
            summary["in a clique with other non-sequence identifiers"] += 1
    w(
        f"The {fmt(len(family_rows))} `{'` and `'.join(PR_FAMILY_CATEGORIES)}` terms "
        f"(`pr_family_terms.csv`) in the {args.build_name} Protein compendium:\n"
    )
    w("| placement | terms |")
    w("|---|---:|")
    for key, n in sorted(summary.items()):
        w(f"| {key} | {fmt(n)} |")
    w("")
    w("Examples (every tenth family term, by CURIE order):\n")
    w("| term | label | clique leader | clique size |")
    w("|---|---|---|---:|")
    for row in family_rows[:: max(1, len(family_rows) // 8)][:8]:
        w(f"| {row['curie']} | {row['label']} | {row['protein_clique_leader']} | {row['clique_size']} |")
    w("")

    # 3. MeSH D12.776.
    w(f'## 3. MeSH descriptors under {PROTEIN_TREE} "Proteins": how many narrower terms and records each has\n')
    mesh_rows, mesh_labels = mesh_descriptor_rows(con, args.mesh_nt)
    write_csv(os.path.join(args.cache_dir, "mesh_d12_776_descriptors_full.csv"), mesh_rows, list(mesh_rows[0]))
    # The descriptors with the most mapped records are the clearest groupings, so they lead the committed slice.
    ranked = sorted(mesh_rows, key=lambda r: (-r["mapped_scrs"], -r["narrower_descriptors"], r["descriptor"]))
    write_csv(os.path.join(args.output_dir, "mesh_d12_776_descriptors_top200.csv"), ranked[:200], list(mesh_rows[0]))
    w(
        f"MeSH gives each descriptor a tree position and maps supplementary records (`MESH:C...`, mostly specific "
        f'proteins such as "Hbb protein, mouse") onto descriptors. Of the {fmt(len(mesh_rows))} descriptors with a '
        f"tree number under {PROTEIN_TREE} (`mesh_d12_776_descriptors_top200.csv` is the 200 with the most mapped "
        "records; the full table is regenerated into `--cache-dir`), counted by narrower descriptors and by mapped "
        "supplementary records:\n"
    )
    grid = Counter((bucket(r["narrower_descriptors"]), bucket(r["mapped_scrs"])) for r in mesh_rows)
    w("| narrower descriptors \\ mapped records | 0 | 1 | 2+ |")
    w("|---|---:|---:|---:|")
    for nd in ("0", "1", "2+"):
        w(f"| {nd} | " + " | ".join(fmt(grid[(nd, ms)]) for ms in ("0", "1", "2+")) + " |")
    w("")
    in_build = Counter()
    for r in mesh_rows:
        if not r["protein_clique_leader"]:
            in_build["not in the Protein compendium"] += 1
        elif r["clique_has_sequence"]:
            in_build["in a Protein clique with a sequence"] += 1
        else:
            in_build["in a Protein clique without a sequence"] += 1
    w("| in the build | descriptors |")
    w("|---|---:|")
    for key, n in sorted(in_build.items()):
        w(f"| {key} | {fmt(n)} |")
    w("")
    w("The worked examples from the discussion:\n")
    w("| descriptor | label | tree numbers | narrower | mapped records | Protein clique |")
    w("|---|---|---|---:|---:|---|")
    by_descriptor = {r["descriptor"]: r for r in mesh_rows}
    for d in MESH_EXAMPLES:
        r = by_descriptor.get(f"{MESH}:{d}")
        if r is None:
            w(f"| {MESH}:{d} | {mesh_labels.get(d, '')} | (not under {PROTEIN_TREE}) | | | |")
            continue
        trees = ";".join(t for t in (r["protein_tree_numbers"], r["other_tree_numbers"]) if t)
        w(
            f"| {r['descriptor']} | {r['label']} | {trees} | {r['narrower_descriptors']} | {r['mapped_scrs']} | "
            f"{r['protein_clique_leader']} |"
        )
    w("")

    # 4. GeneFamily label collisions.
    w("## 4. GeneFamily cliques that share a preferred name with a Protein or chemical clique\n")
    collisions = con.execute(
        """SELECT g.clique_leader, g.preferred_name, c.compendium, c.clique_leader, c.clique_identifier_count
           FROM genefamily_cliques g
           JOIN (SELECT * FROM collisions_protein UNION ALL SELECT * FROM collisions_chemicalentity
                 UNION ALL SELECT * FROM collisions_smallmolecule) c
             ON lower(g.preferred_name) = lower(c.preferred_name)
           ORDER BY starts_with(g.clique_leader, 'HGNC.FAMILY:') DESC, c.clique_identifier_count DESC,
                    g.clique_leader, c.compendium, c.clique_leader"""
    ).fetchall()
    n_genefamily = con.execute("SELECT count(*) FROM genefamily_cliques").fetchone()[0]
    collision_rows = [
        {
            "genefamily_clique": g,
            "genefamily_kind": genefamily_kind(g),
            "preferred_name": name,
            "other_compendium": comp,
            "other_clique_leader": leader,
            "other_clique_size": size,
        }
        for g, name, comp, leader, size in collisions
    ]
    write_csv(
        os.path.join(args.cache_dir, "genefamily_label_collisions_full.csv"), collision_rows, list(collision_rows[0])
    )
    write_csv(
        os.path.join(args.output_dir, "genefamily_label_collisions_top100.csv"),
        collision_rows[:100],
        list(collision_rows[0]),
    )
    per_kind = defaultdict(Counter)
    for r in collision_rows:
        per_kind[r["genefamily_kind"]][r["other_compendium"]] += 1
    families_hit = len({r["genefamily_clique"] for r in collision_rows})
    kinds_total = Counter(
        genefamily_kind(g) for (g,) in con.execute("SELECT clique_leader FROM genefamily_cliques").fetchall()
    )
    w(
        f"Of the {fmt(n_genefamily)} GeneFamily cliques (HGNC.FAMILY and PANTHER.FAMILY, never merged with each "
        f"other), {fmt(families_hit)} have a preferred name that, ignoring case, is also the preferred name of a "
        f"clique in Protein, ChemicalEntity or SmallMolecule: {fmt(len(collision_rows))} such pairs in all "
        "(`genefamily_label_collisions_top100.csv` lists the HGNC families first, then the largest partner "
        "cliques; the full list is regenerated into `--cache-dir`). A PANTHER subfamily is usually named after one "
        'gene product ("HEAT SHOCK PROTEIN BETA-2"), so most of its collisions are with the PR gene-level term of '
        "the same name, not with a family concept.\n"
    )
    compendia = ["Protein", "ChemicalEntity", "SmallMolecule"]
    w("| GeneFamily identifier | cliques | " + " | ".join(f"pairs with {c}" for c in compendia) + " |")
    w("|---|---:|" + "---:|" * len(compendia))
    for kind in ("HGNC.FAMILY", "PANTHER family", "PANTHER subfamily"):
        w(f"| {kind} | {fmt(kinds_total[kind])} | " + " | ".join(fmt(per_kind[kind][c]) for c in compendia) + " |")
    w("")
    w("Examples (spread across the ranked list):\n")
    w("| GeneFamily clique | name | partner | partner clique | partner size |")
    w("|---|---|---|---|---:|")
    for r in collision_rows[:: max(1, len(collision_rows) // 8)][:8]:
        w(
            f"| {r['genefamily_clique']} | {r['preferred_name']} | {r['other_compendium']} | "
            f"{r['other_clique_leader']} | {r['other_clique_size']} |"
        )
    w("")

    # 5. Label heuristic.
    w("## 5. A crude label heuristic over the Protein cliques not led by a sequence accession\n")
    w(
        "UMLS T116 has no family signal, so the only cheap guess at which UMLS-led cliques are groupings is their "
        "label: a word like *family*, a plural protein word, or a trailing *s*. This is reported as a size estimate "
        "and nothing more; `label_heuristic_sample.csv` is a fixed random sample for checking its precision by hand, "
        "which has not been done.\n"
    )
    con.create_function("classify_label", classify_label, ["VARCHAR"], "VARCHAR")
    con.execute(
        """CREATE TABLE heuristic AS
           SELECT clique_leader, split_part(clique_leader, ':', 1) AS leader_prefix, preferred_name,
                  classify_label(preferred_name) AS class FROM protein_concept_cliques"""
    )
    classes = ["family-word", "plural-protein-word", "ends-in-s", "singular"]
    w("| leader prefix | " + " | ".join(classes) + " |")
    w("|---|" + "---:|" * len(classes))
    counts = defaultdict(Counter)
    for prefix, cls, n in con.execute("SELECT leader_prefix, class, count(*) FROM heuristic GROUP BY 1, 2").fetchall():
        counts[prefix][cls] = n
    for prefix in sorted(counts, key=lambda p: -sum(counts[p].values())):
        w(f"| {prefix} | " + " | ".join(fmt(counts[prefix][c]) for c in classes) + " |")
    w("")
    sample = con.execute(
        f"""SELECT clique_leader, preferred_name, class FROM heuristic
            WHERE leader_prefix IN ('{UMLS}', '{MESH}')
            ORDER BY hash(clique_leader || '#1170') LIMIT {args.sample_size}"""
    ).fetchall()
    sample_rows = [
        {"clique_leader": c, "preferred_name": n, "heuristic_class": k, "is_a_grouping": ""} for c, n, k in sample
    ]
    write_csv(os.path.join(args.output_dir, "label_heuristic_sample.csv"), sample_rows, list(sample_rows[0]))
    w("Examples from the sample, one per class:\n")
    w("| clique leader | preferred name | class |")
    w("|---|---|---|")
    seen = set()
    for c, n, k in sample:
        if k not in seen:
            seen.add(k)
            w(f"| {c} | {n} | {k} |")
    w("")

    # Prose paragraphs wrap at the Markdown line length (rumdl MD013); tables and headings are exempt from it.
    wrapped = [
        line if line.startswith(("|", "#")) else textwrap.fill(line, width=100) + ("\n" if line.endswith("\n") else "")
        for line in out
    ]
    with open(os.path.join(args.output_dir, f"{args.build_name}.md"), "w") as outf:
        outf.write("\n".join(wrapped).rstrip("\n") + "\n")


if __name__ == "__main__":
    main()
