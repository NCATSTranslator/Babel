"""Measure which SAPBERT training pairs only the GeneProtein-conflated record of a finished build can produce.

The SAPBERT exporter (src/exporters/sapbert.py) pairs up the names of one synonym record. Gene.txt and
Protein.txt hold a gene's names and each protein's names in separate records; GeneProteinConflated.txt
merges a gene with the proteins it encodes, so its record alone can pair a gene name with a protein name,
or a name of one protein with a name of a sibling protein of the same gene. This script describes that
extra set of pairs for a whole build, so we can decide whether a SAPBERT model should train on them. See
../README.md for the question and ../2026jul22.md for the results.

It works on the *population* of names, not on a 50-pair sample: the exporter draws its 50 pairs per record
at random, so two exports of one build differ, and a sampled file cannot be compared pair by pair.

Inputs, read from a local copy of a build's Parquet exports (docs/DataFormats.md):
  duckdb/parquet/filename=GeneProtein/Conflation.parquet
  duckdb/parquet/filename=Gene/Synonyms.parquet, filename=Gene/Edge.parquet
  duckdb/parquet/filename=Protein/Synonyms.parquet   (19 GB for 2026jul22)

It relies on every conflation ID leading its own clique, which ../../split-cliques/README.md checked for
2026jul22, and reports how many conflation IDs have no synonym record so a build where that fails shows.

--filtered-pairs takes a `CURIE||name1||name2` file (a conflated SAPBERT export with the Gene.txt and
Protein.txt pairs removed) and adds a section saying what kind of pair each row is.

Example (two to three minutes and 12 GB of scratch on a 32 GB laptop):

    uv run python docs/conflation/geneprotein-sapbert-pairs/scripts/analyze_cross_pairs.py \\
        --build-dir data/2026jul22 --workdir data/geneprotein-sapbert-pairs \\
        --filtered-pairs data/gene-protein-conflation-from-hong-2026jul22-2026aug17/GeneProteinConflated.txt \\
        --output docs/conflation/geneprotein-sapbert-pairs/2026jul22.md
"""

import argparse
import os
import shlex
import sys
import textwrap

import duckdb

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from src.util import get_biolink_prefix_map  # noqa: E402

# A UniProtKB label as src/datahandlers/uniprotkb.py:readlabels() writes it, lower-cased by the SAPBERT
# exporter: "<entry name> <protein name> (sprot|trembl)", e.g.
# "a0a9y1qqf1_human breast cancer type 1 susceptibility protein (trembl)". The entry name is the
# accession-or-mnemonic, an underscore and the species mnemonic. Group 1 is the protein name alone.
ENTRY_LABEL_PATTERN = r"^[a-z0-9]+_[a-z0-9]+ (.*) \((?:sprot|trembl)\)$"

# Gene-clique prefixes that mark a model-organism database, from config.yaml's gene_ids. A clique with
# an HGNC id is counted as human instead. Everything else is "other", which is mostly NCBIGene records
# of organisms with no curated gene database.
MODEL_ORGANISM_PREFIXES = ("MGI", "RGD", "ZFIN", "FB", "WormBase", "SGD")

# The groups shown as worked examples: BRCA1, TP53 and INS.
EXAMPLE_GENES = ("NCBIGene:672", "NCBIGene:7157", "NCBIGene:3630")

# Thresholds for "how many conflation groups use this name".
SHARED_BY_THRESHOLDS = (2, 10, 100, 1000)


def parquet_path(build_dir, type_name, table):
    """Path of one Parquet export inside a local build directory."""
    return os.path.join(build_dir, "duckdb", "parquet", f"filename={type_name}", f"{table}.parquet")


def normalized(column):
    """SQL for a name as the SAPBERT exporter writes it: lower-cased, stripped, `||` runs collapsed."""
    return f"regexp_replace(trim({column}), '\\|\\|+', '|', 'g')"


def build_name_tables(db, build_dir):
    """Create member, gene_name, protein_name, group_name, grp and name_use from the build's exports."""
    conflation = parquet_path(build_dir, "GeneProtein", "Conflation")
    db.execute(
        f"""CREATE OR REPLACE TABLE member AS
        SELECT conflation_leader AS leader, curie, curie_prefix AS prefix FROM read_parquet('{conflation}')"""
    )
    # One row per (group, name) on the gene side, and per (group, protein, name) on the protein side:
    # which protein a name belongs to decides whether a protein-protein pair is already in Protein.txt.
    db.execute(
        f"""CREATE OR REPLACE TABLE gene_name AS
        SELECT DISTINCT m.leader, {normalized("s.label_lc")} AS name
        FROM read_parquet('{parquet_path(build_dir, "Gene", "Synonyms")}') s
        JOIN member m ON s.clique_leader = m.curie
        WHERE m.prefix = 'NCBIGene' AND trim(s.label_lc) <> ''"""
    )
    db.execute(
        f"""CREATE OR REPLACE TABLE protein_name AS
        SELECT DISTINCT m.leader, m.curie AS protein, {normalized("s.label_lc")} AS name
        FROM read_parquet('{parquet_path(build_dir, "Protein", "Synonyms")}') s
        JOIN member m ON s.clique_leader = m.curie
        WHERE m.prefix = 'UniProtKB' AND trim(s.label_lc) <> ''"""
    )
    db.execute(
        f"""CREATE OR REPLACE TABLE group_name AS
        WITH p AS (SELECT leader, name, count(*) AS proteins FROM protein_name GROUP BY ALL)
        SELECT leader, name, g.name IS NOT NULL AS in_gene, coalesce(p.proteins, 0) AS proteins,
            CASE WHEN name LIKE '% (trembl)' AND regexp_matches(name, '{ENTRY_LABEL_PATTERN}') THEN 'trembl'
                 WHEN name LIKE '% (sprot)' AND regexp_matches(name, '{ENTRY_LABEL_PATTERN}') THEN 'sprot'
                 ELSE 'name' END AS kind
        FROM gene_name g FULL OUTER JOIN p USING (leader, name)"""
    )
    # An entry label is "new" only in its entry-name prefix when the protein name inside it is already
    # one of the gene's own names.
    db.execute(
        f"""CREATE OR REPLACE TABLE entry_label AS
        SELECT e.leader, e.name, e.kind, g.name IS NOT NULL AS inner_name_is_gene_name
        FROM (SELECT leader, name, kind, regexp_extract(name, '{ENTRY_LABEL_PATTERN}', 1) AS inner_name
              FROM group_name WHERE proteins > 0 AND NOT in_gene AND kind <> 'name') e
        LEFT JOIN gene_name g ON g.leader = e.leader AND g.name = e.inner_name"""
    )
    model_prefixes = ", ".join(f"'{prefix}'" for prefix in MODEL_ORGANISM_PREFIXES)
    db.execute(
        f"""CREATE OR REPLACE TABLE bucket AS
        SELECT clique_leader AS leader,
            CASE WHEN bool_or(curie_prefix = 'HGNC') THEN 'human'
                 WHEN bool_or(curie_prefix IN ({model_prefixes})) THEN 'model organism'
                 ELSE 'other' END AS bucket
        FROM read_parquet('{parquet_path(build_dir, "Gene", "Edge")}')
        WHERE clique_leader IN (SELECT leader FROM member) GROUP BY 1"""
    )
    # Per protein: how many of its names the gene does not have, split into entry labels and real names.
    db.execute(
        """CREATE OR REPLACE TABLE protein_stat AS
        SELECT p.leader, p.protein,
            count(*) FILTER (NOT n.in_gene) AS only_names,
            count(*) FILTER (NOT n.in_gene AND n.kind <> 'name') AS only_labels
        FROM protein_name p JOIN group_name n USING (leader, name) GROUP BY ALL"""
    )
    db.execute(
        """CREATE OR REPLACE TABLE grp AS
        WITH names AS (
            SELECT leader,
                count(*) FILTER (in_gene) AS gene_names,
                count(*) FILTER (in_gene AND proteins = 0) AS gene_only,
                count(*) FILTER (in_gene AND proteins > 0) AS shared,
                count(*) FILTER (proteins > 0) AS protein_names,
                count(*) FILTER (proteins > 0 AND NOT in_gene) AS protein_only,
                count(*) FILTER (proteins > 0 AND NOT in_gene AND kind = 'trembl') AS only_trembl,
                count(*) FILTER (proteins > 0 AND NOT in_gene AND kind = 'sprot') AS only_sprot,
                count(*) FILTER (proteins > 0 AND NOT in_gene AND kind = 'name') AS only_real
            FROM group_name GROUP BY leader),
        members AS (
            SELECT leader, count(*) FILTER (prefix = 'NCBIGene') AS genes,
                count(*) FILTER (prefix = 'UniProtKB') AS proteins
            FROM member GROUP BY leader),
        within AS (
            SELECT leader, sum(only_names * (only_names - 1) / 2)::BIGINT AS same_protein_pairs,
                sum(only_labels * (only_labels - 1) / 2)::BIGINT AS same_protein_label_pairs
            FROM protein_stat GROUP BY leader)
        SELECT m.leader, coalesce(b.bucket, 'other') AS bucket, m.genes, m.proteins,
            coalesce(n.gene_names, 0) AS gene_names, coalesce(n.gene_only, 0) AS gene_only,
            coalesce(n.shared, 0) AS shared, coalesce(n.protein_names, 0) AS protein_names,
            coalesce(n.protein_only, 0) AS protein_only, coalesce(n.only_trembl, 0) AS only_trembl,
            coalesce(n.only_sprot, 0) AS only_sprot, coalesce(n.only_real, 0) AS only_real,
            -- Pairs of protein-only names from two different proteins of the gene. A name two sibling
            -- proteins share is counted once in protein_only and once per protein in `within`, so this
            -- is a slight undercount for such groups; greatest() keeps it from going negative.
            greatest(coalesce(n.protein_only * (n.protein_only - 1) / 2, 0)
                     - coalesce(w.same_protein_pairs, 0), 0)::BIGINT AS sibling_pairs,
            greatest(coalesce((n.only_trembl + n.only_sprot) * (n.only_trembl + n.only_sprot - 1) / 2, 0)
                     - coalesce(w.same_protein_label_pairs, 0), 0)::BIGINT AS sibling_label_pairs
        FROM members m LEFT JOIN names n USING (leader) LEFT JOIN bucket b USING (leader)
        LEFT JOIN within w USING (leader)"""
    )
    db.execute(
        """CREATE OR REPLACE TABLE name_use AS
        SELECT name, count(*) AS groups, bool_or(in_gene) AS a_gene_name, bool_or(proteins > 0) AS a_protein_name
        FROM group_name GROUP BY name"""
    )


def md_table(header, rows, right_from=1):
    """A Markdown table; columns from `right_from` on are right-aligned and integers get thousands separators."""

    def cell(value):
        if isinstance(value, bool) or value is None:
            return str(value)
        if isinstance(value, int):
            return f"{value:,}"
        if isinstance(value, float):
            return f"{value:.1f}%"
        return str(value).replace("|", "\\|")

    lines = ["| " + " | ".join(header) + " |"]
    lines.append("|" + "|".join("---" if i < right_from else "---:" for i in range(len(header))) + "|")
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def para(text):
    """Wrap one paragraph of report prose at the repository's Markdown line length."""
    return textwrap.fill(" ".join(text.split()), width=100)


BUCKET_ORDER = "CASE bucket WHEN 'human' THEN 0 WHEN 'model organism' THEN 1 WHEN 'other' THEN 2 ELSE 3 END"


def by_bucket(db, columns):
    """Run an aggregate over grp per organism bucket, with an "all" row last."""
    return db.execute(
        f"""SELECT coalesce(bucket, 'all') AS bucket, {columns} FROM grp
        GROUP BY ROLLUP (bucket) ORDER BY {BUCKET_ORDER.replace("bucket", "coalesce(bucket, 'all')")}"""
    ).fetchall()


def report_population(db, build_dir):
    """The report sections that describe the build's whole population of names."""
    out = []
    missing = db.execute(
        """SELECT count(*) FILTER (prefix = 'NCBIGene' AND curie NOT IN (SELECT leader FROM gene_name)),
               count(*) FILTER (prefix = 'UniProtKB' AND curie NOT IN (SELECT protein FROM protein_name)),
               count(*) FILTER (prefix NOT IN ('NCBIGene', 'UniProtKB')),
               count(*) FILTER (prefix = 'NCBIGene' AND curie <> leader)
        FROM member"""
    ).fetchone()
    out.append("## Conflation groups\n")
    out.append(
        para(
            """A group is one gene and the proteins UniProtKB maps to it. "Human" means the gene's clique
            has an HGNC id; "model organism" means it has an id from one of
            """
            + ", ".join(MODEL_ORGANISM_PREFIXES)
            + """. Names are lower-cased and stripped, as the exporter writes them."""
        )
    )
    out.append("")
    out.append(
        md_table(
            ["Genes", "Groups", "Proteins", "Groups with 2+ proteins", "Gene names", "Protein names"],
            by_bucket(
                db,
                "count(*), sum(proteins)::BIGINT, count(*) FILTER (proteins > 1), sum(gene_names)::BIGINT, "
                "sum(protein_names)::BIGINT",
            ),
        )
    )
    out.append("")
    out.append(
        para(
            f"""Conflation IDs with no synonym record: {missing[0]:,} genes and {missing[1]:,} proteins.
            IDs with a prefix other than NCBIGene or UniProtKB: {missing[2]:,}. Genes that do not lead
            their group: {missing[3]:,}."""
        )
    )

    out.append("\n## What the protein side's names are\n")
    out.append(
        para(
            """A UniProtKB record's label is an entry label that Babel builds from the FASTA header:
            the entry name, the protein name and `(sprot)` or `(trembl)`. Protein synonyms come only
            from PR and UMLS (`config.yaml: protein_synonyms`), so a TrEMBL protein's entry label is
            its only name. Counts are of (group, name) rows the gene does not already have."""
        )
    )
    out.append("")
    out.append(
        md_table(
            ["Genes", "TrEMBL entry labels", "Swiss-Prot entry labels", "Other protein names", "Groups with one"],
            by_bucket(
                db,
                "sum(only_trembl)::BIGINT, sum(only_sprot)::BIGINT, sum(only_real)::BIGINT, count(*) FILTER (only_real > 0)",
            ),
        )
    )
    out.append("")
    out.append(
        para(
            """"Groups with one" counts the groups with at least one protein name that is neither an
            entry label nor already a name of the gene. Only in those groups does a gene-protein pair
            tie a gene name to a protein name that could appear in text."""
        )
    )
    out.append("")
    out.append(
        para(
            """Is the protein name inside an entry label already one of the gene's names? Where it is,
            the label adds only its entry-name prefix."""
        )
    )
    out.append("")
    out.append(
        md_table(
            ["Entry label", "Labels", "Inner name is a gene name", "Share"],
            db.execute(
                """SELECT kind, count(*), count(*) FILTER (inner_name_is_gene_name),
                    100.0 * count(*) FILTER (inner_name_is_gene_name) / count(*)
                FROM entry_label GROUP BY kind ORDER BY kind DESC"""
            ).fetchall(),
        )
    )

    out.append("\n## Names a gene shares with its own proteins\n")
    out.append(
        para(
            """One string has one embedding, whichever record it was trained under. So a name that a
            gene and its protein share already ties the gene's other names and the protein's other
            names together when Gene.txt and Protein.txt are trained separately. A gene-protein pair
            adds a tie of its own only in a group with a protein-only name and no shared name. "Other"
            protein names are those that are not entry labels."""
        )
    )
    out.append("")
    out.append(
        md_table(
            [
                "Genes",
                "Groups",
                "Sharing a name with the gene",
                "With a protein-only other name",
                "Of those, sharing no name",
            ],
            by_bucket(
                db,
                "count(*), count(*) FILTER (shared > 0), "
                "count(*) FILTER (only_real > 0), count(*) FILTER (only_real > 0 AND shared = 0)",
            ),
        )
    )
    out.append("")
    out.append(
        para(
            """The same, counting names: the gene's own names, the names shared with a protein, and the
            other protein names the gene does not have."""
        )
    )
    out.append("")
    out.append(
        md_table(
            ["Genes", "Gene names", "Shared with a protein", "Protein-only other names", "In groups sharing no name"],
            by_bucket(
                db,
                "sum(gene_names)::BIGINT, sum(shared)::BIGINT, sum(only_real)::BIGINT, "
                "sum(only_real) FILTER (shared = 0)::BIGINT",
            ),
        )
    )

    out.append("\n## Pairs only the conflated record can produce\n")
    out.append(
        para(
            """The whole population of pairs, before the exporter's cap of 50 per record. A gene-protein
            pair is a name only the gene has with a name only a protein has. A sibling pair is two
            protein-only names from two different proteins of one gene; that count is slightly low for
            groups whose sibling proteins share a name."""
        )
    )
    out.append("")
    out.append(
        md_table(
            [
                "Genes",
                "Gene × TrEMBL label",
                "Gene × Swiss-Prot label",
                "Gene × other protein name",
                "Sibling labels",
                "Other sibling pairs",
            ],
            by_bucket(
                db,
                "sum(gene_only * only_trembl)::BIGINT, sum(gene_only * only_sprot)::BIGINT, "
                "sum(gene_only * only_real)::BIGINT, sum(sibling_label_pairs)::BIGINT, "
                "sum(sibling_pairs - sibling_label_pairs)::BIGINT",
            ),
        )
    )

    out.append("\n## Names used by many groups\n")
    out.append(
        para(
            """A SAPBERT training name is labelled with its record's CURIE, so a name many groups use is
            a positive for each of them. Counted over the names of conflated groups only."""
        )
    )
    out.append("")
    thresholds = ", ".join(f"count(*) FILTER (groups >= {n})" for n in SHARED_BY_THRESHOLDS)
    rows = db.execute(
        f"""SELECT 'gene name' AS side, count(*), {thresholds} FROM name_use WHERE a_gene_name
        UNION ALL SELECT 'protein name', count(*), {thresholds} FROM name_use WHERE a_protein_name
        UNION ALL SELECT 'any', count(*), {thresholds} FROM name_use"""
    ).fetchall()
    out.append(md_table(["Kind of name", "Distinct names"] + [f"In {n:,}+ groups" for n in SHARED_BY_THRESHOLDS], rows))
    out.append("")
    out.append(
        md_table(
            ["Name", "Groups"],
            db.execute("SELECT name, groups FROM name_use ORDER BY groups DESC, name LIMIT 15").fetchall(),
        )
    )

    out.append("\n## Examples\n")
    example_curies = ", ".join(f"'{gene}'" for gene in EXAMPLE_GENES)
    preferred_names = dict(
        db.execute(
            f"""SELECT DISTINCT clique_leader, preferred_name
            FROM read_parquet('{parquet_path(build_dir, "Gene", "Synonyms")}')
            WHERE clique_leader IN ({example_curies})"""
        ).fetchall()
    )
    curie_converter = get_biolink_prefix_map()
    for gene in EXAMPLE_GENES:
        stats = db.execute(
            "SELECT proteins, gene_names, shared, only_trembl, only_sprot, only_real FROM grp WHERE leader = ?", [gene]
        ).fetchone()
        if stats is None:
            continue
        names = {
            label: [
                row[0]
                for row in db.execute(
                    f"SELECT name FROM group_name WHERE leader = ? AND {where} ORDER BY name LIMIT 6", [gene]
                ).fetchall()
            ]
            for label, where in (
                ("shared", "in_gene AND proteins > 0"),
                ("protein-only", "NOT in_gene AND kind = 'name'"),
                ("gene-only", "in_gene AND proteins = 0"),
            )
        }
        out.append(
            para(
                f"""[`{gene}`]({curie_converter.expand(gene)}) "{preferred_names.get(gene, "")}":
                {stats[0]:,} proteins and {stats[1]:,} gene names, {stats[2]:,} of them shared
                with a protein. Protein-only names by kind: TrEMBL entry label {stats[3]:,}, Swiss-Prot
                entry label {stats[4]:,}, other {stats[5]:,}."""
            )
        )
        out.append("")
        out.append(
            md_table(
                ["Names", "First six, alphabetically"],
                [(label, "; ".join(values)) for label, values in names.items()],
                right_from=2,
            )
        )
        out.append("")
    return out


def report_filtered_pairs(db, pairs_file):
    """The report section that classifies each row of a `CURIE||name1||name2` file."""
    # Read whole lines (no real delimiter or quote), then split. pandas' to_csv quoted the few rows that
    # contain a double quote, doubling the quotes inside; undo that so their names can be looked up.
    db.execute(
        f"""CREATE OR REPLACE TABLE pair AS
        WITH raw AS (
            SELECT CASE WHEN line LIKE '"%"' THEN replace(line[2:-2], '""', '"') ELSE line END AS line,
                line LIKE '"%"' AS was_quoted
            FROM read_csv('{pairs_file}', delim='\x01', header=false, columns={{'line': 'VARCHAR'}},
                          quote='', escape='', max_line_size=10000000))
        SELECT row_number() OVER () AS id, split_part(line, '||', 1) AS leader,
            split_part(line, '||', 2) AS name1, split_part(line, '||', 3) AS name2, was_quoted,
            len(string_split(line, '||')) AS fields
        FROM raw"""
    )
    db.execute(
        """CREATE OR REPLACE TABLE pair_kind AS
        WITH same_protein AS (
            SELECT DISTINCT p.id FROM pair p
            JOIN protein_name a ON a.leader = p.leader AND a.name = p.name1
            JOIN protein_name b ON b.leader = p.leader AND b.name = p.name2 AND b.protein = a.protein)
        SELECT p.id, p.leader, p.name1, p.name2,
            CASE WHEN p.leader NOT IN (SELECT leader FROM grp) THEN 'record is not conflated'
                 WHEN n1.leader IS NULL OR n2.leader IS NULL THEN 'a name not found in the build'
                 WHEN n1.in_gene AND n2.in_gene THEN 'both names are gene names'
                 WHEN s.id IS NOT NULL THEN 'both names are names of one protein'
                 WHEN n1.in_gene OR n2.in_gene THEN 'gene name with protein name'
                 ELSE 'names of two sibling proteins' END AS pair_kind,
            CASE WHEN n1.in_gene THEN n2.kind WHEN n2.in_gene THEN n1.kind END AS protein_side_kind,
            (n1.kind <> 'name')::INT + (n2.kind <> 'name')::INT AS entry_labels
        FROM pair p
        LEFT JOIN group_name n1 ON n1.leader = p.leader AND n1.name = p.name1
        LEFT JOIN group_name n2 ON n2.leader = p.leader AND n2.name = p.name2
        LEFT JOIN same_protein s ON s.id = p.id"""
    )
    out = [f"## The filtered pair file `{os.path.basename(pairs_file)}`\n"]
    totals = db.execute(
        "SELECT count(*), count(DISTINCT leader), count(*) FILTER (was_quoted), count(*) FILTER (fields <> 3) FROM pair"
    ).fetchone()
    out.append(
        para(
            f"""{totals[0]:,} rows over {totals[1]:,} CURIEs. {totals[2]:,} rows were wrapped in CSV
            quotes, and {totals[3]:,} do not have three `||`-separated fields. The first two kinds
            below are pairs only the conflated record can produce. The next two are already possible
            in Gene.txt or Protein.txt, and are in this file because each export draws its own random
            50 pairs per record."""
        )
    )
    out.append("")
    kind_order = [
        "gene name with protein name",
        "names of two sibling proteins",
        "both names are gene names",
        "both names are names of one protein",
        "record is not conflated",
        "a name not found in the build",
    ]
    order_sql = "CASE pair_kind " + " ".join(f"WHEN '{kind}' THEN {i}" for i, kind in enumerate(kind_order)) + " END"
    out.append(
        md_table(
            ["Kind of pair", "Rows", "Share", "With an entry label", "CURIEs"],
            db.execute(
                f"""SELECT pair_kind, count(*), 100.0 * count(*) / sum(count(*)) OVER (),
                    count(*) FILTER (entry_labels > 0), count(DISTINCT leader)
                FROM pair_kind GROUP BY pair_kind ORDER BY {order_sql}"""
            ).fetchall(),
        )
    )
    out.append("")
    out.append(para("""The gene-protein rows, by what the protein-side name is:"""))
    out.append("")
    out.append(
        md_table(
            ["Protein-side name", "Rows", "Share", "CURIEs"],
            db.execute(
                """SELECT CASE protein_side_kind WHEN 'trembl' THEN 'TrEMBL entry label'
                        WHEN 'sprot' THEN 'Swiss-Prot entry label' ELSE 'other protein name' END,
                    count(*), 100.0 * count(*) / sum(count(*)) OVER (), count(DISTINCT leader)
                FROM pair_kind WHERE pair_kind = 'gene name with protein name' GROUP BY 1 ORDER BY 2 DESC"""
            ).fetchall(),
        )
    )
    out.append("")
    out.append(
        para(
            """How many rows hold a name that many CURIEs in this file use (the most widely used of the
            row's two names):"""
        )
    )
    out.append("")
    db.execute(
        """CREATE OR REPLACE TABLE file_name_use AS
        SELECT name, count(DISTINCT leader) AS curies
        FROM (SELECT leader, name1 AS name FROM pair UNION ALL SELECT leader, name2 FROM pair) GROUP BY name"""
    )
    thresholds = ", ".join(f"count(*) FILTER (greatest(a.curies, b.curies) >= {n})" for n in SHARED_BY_THRESHOLDS)
    row = db.execute(
        f"""SELECT count(*), {thresholds} FROM pair p
        JOIN file_name_use a ON a.name = p.name1 JOIN file_name_use b ON b.name = p.name2"""
    ).fetchone()
    out.append(
        md_table(
            ["Rows"] + [f"Name in {n:,}+ CURIEs" for n in SHARED_BY_THRESHOLDS],
            [row, ("",) + tuple(100.0 * count / row[0] for count in row[1:])],
            right_from=0,
        )
    )
    out.append("")
    out.append(para("""A fixed sample of the gene-protein rows whose protein-side name is not an entry label:"""))
    out.append("")
    out.append(
        md_table(
            ["CURIE", "Name 1", "Name 2"],
            db.execute(
                """SELECT leader, name1, name2 FROM pair_kind
                WHERE pair_kind = 'gene name with protein name' AND protein_side_kind = 'name'
                ORDER BY hash(leader || name1 || name2) LIMIT 20"""
            ).fetchall(),
            right_from=3,
        )
    )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--build-dir", required=True, help="Local build directory holding duckdb/parquet/.")
    parser.add_argument("--workdir", required=True, help="Scratch directory for the DuckDB file; put it under data/.")
    parser.add_argument("--output", required=True, help="Markdown report to write.")
    parser.add_argument("--build-name", help="Name for the report title; defaults to the build directory's name.")
    parser.add_argument("--filtered-pairs", help="Optional CURIE||name1||name2 file to classify.")
    parser.add_argument("--memory-limit", help="DuckDB memory_limit, e.g. 24GB. Defaults to DuckDB's own.")
    parser.add_argument("--reuse", action="store_true", help="Reuse the name tables already in --workdir.")
    args = parser.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    # A small analysis script under docs/, so plain duckdb.connect() rather than connect_duckdb() (AGENTS.md).
    # The tables go in a file so the joins spill to disk and --reuse can skip rebuilding them.
    db = duckdb.connect(os.path.join(args.workdir, "cross_pairs.duckdb"))
    db.execute(f"SET temp_directory = '{os.path.join(args.workdir, 'duckdb-tmp')}'")
    db.execute("SET preserve_insertion_order = false")
    if args.memory_limit:
        db.execute(f"SET memory_limit = '{args.memory_limit}'")

    if not args.reuse:
        build_name_tables(db, args.build_dir)

    build_name = args.build_name or os.path.basename(args.build_dir.rstrip("/"))
    out = [f"# GeneProtein conflation and SAPBERT training pairs: {build_name}\n"]
    out.append(
        para(
            """Generated by [`scripts/analyze_cross_pairs.py`](scripts/analyze_cross_pairs.py); do not
            edit by hand. [`README.md`](README.md) says what the numbers mean for the decision."""
        )
    )
    out.append("")
    command = " ".join(shlex.quote(arg) for arg in ["analyze_cross_pairs.py"] + sys.argv[1:] if arg != "--reuse")
    out.append("```text\n" + command + "\n```\n")
    out.extend(report_population(db, args.build_dir))
    if args.filtered_pairs:
        out.extend(report_filtered_pairs(db, args.filtered_pairs))
    with open(args.output, "w", encoding="utf-8") as report:
        report.write("\n".join(out).rstrip("\n") + "\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
