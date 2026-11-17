"""Measure what a change to conflate_synonyms() does to a finished build's conflated synonym file,
without rebuilding it: replay the old and the new function over that build's own inputs, and diff.

The old function is read from a git ref (default: the `2026jul22` tag that built 2026jul22). Its replay
is first checked against the conflated file the build published: if every record matches, the
reconstructed inputs are faithful and the old-vs-new diff is the change's effect. See ../README.md.

Inputs are read in place from the build directory, so no local build is needed:
- `conflation/<Name>.txt`, optionally sampled by primary ID (`--sample N` keeps about 1/N of the groups;
  GeneProtein's full merge needed 512G on the cluster).
- each compendium's `duckdb/parquet/filename=<Type>/Edge.parquet`, read in file order, to rebuild the
  compendium lines of every conflated clique, plus every clique sharing a CURIE with one, transitively
  (the old step 1.1 pulled those in through the shared CURIE).
- each type's synonym file, from `synonyms-conflated/<Type>.txt.gz` (where the build published the
  unconflated per-type synonyms), and the published `synonyms/<Name>Conflated.txt.gz`, both filtered
  to the CURIEs of those cliques.

Usage:
  uv run python replay_conflated_synonyms.py <build_url> DrugChemical \\
      MolecularMixture SmallMolecule Polypeptide ComplexMolecularMixture ChemicalEntity ChemicalMixture Drug Food \\
      --workdir data/synonym-replay/DrugChemical
Pass the types in the order the rule passes them (`config.yaml`: chemical_outputs; gene_outputs then
protein_outputs). Downloads are cached in --workdir, so a re-run only replays and compares.
"""

import argparse
import collections
import concurrent.futures
import gzip
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import urllib.request

import duckdb

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, REPO_ROOT)

CURIE_PREFIX = '{"curie": "'


def curie_of(line):
    """The CURIE of a synonym JSONL line, without parsing the whole record (they all lead with it)."""
    if line.startswith(CURIE_PREFIX):
        return line[len(CURIE_PREFIX) : line.index('"', len(CURIE_PREFIX))]
    return json.loads(line)["curie"]


def cached(path, build):
    """Run build(tmp_path) unless `path` already exists, then rename the result into place."""
    if not os.path.exists(path):
        build(path + ".part")
        os.replace(path + ".part", path)
    return path


def sample_conflation(build_url, name, sample, out_path):
    """Write the conflation lines whose primary ID falls in the sample (all of them if sample == 1)."""
    with urllib.request.urlopen(f"{build_url}/conflation/{name}.txt") as fh, open(out_path, "w") as out:
        for raw in fh:
            primary = json.loads(raw)[0]
            if sample == 1 or int(hashlib.sha1(primary.encode()).hexdigest(), 16) % sample == 0:
                out.write(raw.decode())


def write_mini_compendia(build_url, types, conflation_path, workdir):
    """Rebuild, per type, the compendium lines of every clique that holds a conflation ID or shares a CURIE
    (transitively) with one that does, in the compendium's own order. Returns every CURIE in those cliques.

    The Edge tables are copied into a DuckDB file in `workdir` once (GeneProtein's are too big for memory);
    `file_row_number` keeps each compendium's own order, which the old step 1.1 depended on."""
    listed_path = os.path.join(workdir, "listed.tsv")
    with open(listed_path, "w") as out:
        out.write("curie\n")
        out.writelines(f"{i}\n" for i in {i for line in open(conflation_path) for i in json.loads(line)})
    db_path = os.path.join(workdir, "edges.duckdb")
    fresh = not os.path.exists(db_path)
    c = duckdb.connect(db_path)
    c.execute("INSTALL httpfs; LOAD httpfs; SET threads=8; SET memory_limit='16GB';")
    if fresh:
        union = " UNION ALL ".join(
            f"SELECT {n} AS file_index, file_row_number AS row, clique_leader, curie FROM read_parquet("
            f"'{build_url}/duckdb/parquet/filename%3D{t}/Edge.parquet', file_row_number=true)"
            for n, t in enumerate(types)
        )
        c.execute(f"CREATE TABLE edges AS {union}")
    c.execute(
        f"CREATE OR REPLACE TABLE curies AS SELECT DISTINCT curie FROM read_csv('{listed_path}', header=true, quote='')"
    )
    while True:
        before = c.execute("SELECT count(*) FROM curies").fetchone()[0]
        c.execute(
            """CREATE OR REPLACE TABLE curies AS SELECT DISTINCT e.curie FROM edges e JOIN (
                SELECT DISTINCT file_index, clique_leader FROM edges JOIN curies USING (curie)
            ) USING (file_index, clique_leader) UNION SELECT curie FROM curies"""
        )
        if c.execute("SELECT count(*) FROM curies").fetchone()[0] == before:
            break
    rows = c.execute(
        """SELECT file_index, list(curie ORDER BY row) FROM edges JOIN (
            SELECT DISTINCT file_index, clique_leader FROM edges JOIN curies USING (curie)
        ) USING (file_index, clique_leader) GROUP BY file_index, clique_leader ORDER BY file_index, min(row)"""
    ).fetchall()
    paths = [os.path.join(workdir, f"compendium-{t}.txt") for t in types]
    handles = [open(p, "w") for p in paths]
    for file_index, ids in rows:
        handles[file_index].write(json.dumps({"identifiers": [{"i": i} for i in ids]}) + "\n")
    for h in handles:
        h.close()
    return paths, {r[0] for r in c.execute("SELECT curie FROM curies").fetchall()}


def filter_remote_gz(url, wanted, out_path):
    """Stream a remote gzipped JSONL file, keeping the lines whose CURIE is wanted."""
    with urllib.request.urlopen(url) as resp, gzip.open(resp, "rt", encoding="utf-8") as fh:
        with gzip.open(out_path, "wt", encoding="utf-8") as out:
            for line in fh:
                if curie_of(line) in wanted:
                    out.write(line)


def load_old_module(ref):
    """Import synonymconflation.py as it was at `ref`."""
    source = subprocess.run(
        ["git", "-C", REPO_ROOT, "show", f"{ref}:src/synonyms/synonymconflation.py"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    spec = importlib.util.spec_from_loader(f"synonymconflation_{ref}", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, f"{ref}:src/synonyms/synonymconflation.py", "exec"), module.__dict__)
    return module


def read_records(path):
    """CURIE -> sorted list of canonical JSON strings of its records."""
    records = collections.defaultdict(list)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            records[curie_of(line)].append(json.dumps(json.loads(line), sort_keys=True))
    return {curie: sorted(rs) for curie, rs in records.items()}


def compare(label, a, b, examples=5):
    """Print how records under each CURIE differ between `a` and `b`, by field."""
    only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    both = set(a) & set(b)
    changed = sorted(c for c in both if a[c] != b[c])
    print(f"\n## {label}")
    print(f"- CURIEs compared: {len(set(a) | set(b)):,}; identical: {len(both) - len(changed):,}")
    print(f"- changed: {len(changed):,}; only in first: {len(only_a):,}; only in second: {len(only_b):,}")
    fields = collections.Counter()
    count_delta = collections.Counter()
    for c in changed:
        if len(a[c]) == 1 and len(b[c]) == 1:
            ra, rb = json.loads(a[c][0]), json.loads(b[c][0])
            for k in set(ra) | set(rb):
                if ra.get(k) != rb.get(k):
                    fields[k] += 1
            count_delta[rb.get("clique_identifier_count", 0) - ra.get("clique_identifier_count", 0)] += 1
        else:
            fields[f"record count {len(a[c])} -> {len(b[c])}"] += 1
    for k, n in fields.most_common():
        print(f"  - field `{k}` differs in {n:,}")
    if count_delta:
        print(f"  - clique_identifier_count change (second - first): {dict(sorted(count_delta.items()))}")
    for c in (changed + only_a + only_b)[:examples]:
        print(f"  - e.g. {c}: first={a.get(c)} second={b.get(c)}"[:1500])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("build_url")
    parser.add_argument("name", help="Conflation name: DrugChemical or GeneProtein")
    parser.add_argument("types", nargs="+", help="Compendium/synonym types, in the rule's order")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--sample", type=int, default=1, help="Keep about 1/N of the conflation groups")
    parser.add_argument("--old-ref", default="2026jul22")
    args = parser.parse_args()
    os.makedirs(args.workdir, exist_ok=True)
    w = lambda name: os.path.join(args.workdir, name)  # noqa: E731

    conflation = cached(w("conflation.txt"), lambda p: sample_conflation(args.build_url, args.name, args.sample, p))
    compendia, wanted = write_mini_compendia(args.build_url, args.types, conflation, args.workdir)
    print(f"{sum(1 for _ in open(conflation)):,} conflation lines; {len(wanted):,} CURIEs in their cliques")

    jobs = {w(f"synonyms-{t}.txt.gz"): f"{args.build_url}/synonyms-conflated/{t}.txt.gz" for t in args.types}
    jobs[w("published.txt.gz")] = f"{args.build_url}/synonyms/{args.name}Conflated.txt.gz"
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(cached, path, lambda p, url=url: filter_remote_gz(url, wanted, p)) for path, url in jobs.items()
        ]
        for f in futures:
            f.result()
    synonyms = [w(f"synonyms-{t}.txt.gz") for t in args.types]

    from src.synonyms import synonymconflation as new_module

    old_module = load_old_module(args.old_ref)
    old_module.conflate_synonyms(synonyms, compendia, [conflation], w("old.txt.gz"))
    new_module.conflate_synonyms(synonyms, compendia, [conflation], w("new.txt.gz"))

    published, old, new = (read_records(w(f)) for f in ("published.txt.gz", "old.txt.gz", "new.txt.gz"))
    print(f"# {args.name} (sample 1/{args.sample}, old code from {args.old_ref})")
    compare(f"Validation: published (first) vs replay of {args.old_ref} (second)", published, old)
    compare(f"Change: replay of {args.old_ref} (first) vs replay of this branch (second)", old, new)


if __name__ == "__main__":
    main()
