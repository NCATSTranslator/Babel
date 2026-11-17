"""Measure what the UNII-records concords (UNII -> PubChem CID, UNII -> CAS) would do to a finished build's chemical cliques.

Writes the two concords with the production writer (``chemicals.write_unii_records_concords``), filters each with the
production ``remove_overused_xrefs``, looks up every endpoint's clique in the build's chemical ``Edge.parquet`` files,
and then replays ``glom()``'s merge rule over those cliques: a pair joins two cliques unless both carry an InChIKey and
the keys differ (``chemical_unique_prefixes`` is ``[INCHIKEY]``), and a CURIE in no clique joins its partner's.
UNII_PUBCHEM, the concord the build uses, is applied first and in file order, as ``build_untyped_compendia()`` does;
UNII_CAS is then applied on top, to say what adding it too would change.

It is a model, not a rebuild. It starts from the build's *typed* cliques, so it cannot see the post-glom MolecularMixture
split (Babel #83) or a clique whose InChIKey ``write_compendium()`` dropped (Drug and Food), and it assumes the new
concords run last (they are last in ``config.yaml: chemical_concords``). A real build's clique diff is the check on it.

Usage (the build URL is a published build root holding ``duckdb/parquet/``)::

    uv run python docs/sources/UNII/records-xrefs/scripts/measure_unii_records_xrefs.py \
        --records babel_downloads/UNII/Latest_UNII_Records.txt \
        --build-url <build-root-url> --build-name 2026jul22 \
        --output-dir docs/sources/UNII/records-xrefs/output
"""

import argparse
import csv
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

import src.createcompendia.chemicals as chemicals
from src.babel_utils import remove_overused_xrefs
from src.datahandlers.unii import UNII_RECORDS_ENCODING
from src.model.intermediates import read_concord_pairs
from src.util import get_config

# CURIEs the insulin report (#1171) is about; the summary says where each one ends up.
INSULIN_CHECKS = {
    "rabbit": ("UNII:LWB6BD8SN9", "PUBCHEM.COMPOUND:118984376"),
    "beef": ("UNII:576O9IZ534", "PUBCHEM.COMPOUND:16131099"),
    "pork": ("UNII:AVT680JB39", "PUBCHEM.COMPOUND:16131098"),
}


def load_cliques(con, build_url, curies):
    """Return {curie: clique_leader}, {leader: biolink_type}, {leader: InChIKey}, {leader: (name, size)} for the cliques
    holding any of ``curies`` in the build's chemical compendia."""
    con.execute("CREATE TEMP TABLE wanted(curie VARCHAR)")
    con.executemany("INSERT INTO wanted VALUES (?)", [(c,) for c in sorted(curies)])
    files = [
        f"{build_url.rstrip('/')}/duckdb/parquet/filename%3D{name.removesuffix('.txt')}/"
        for name in get_config()["chemical_outputs"]
    ]
    edges = ", ".join(f"'{f}Edge.parquet'" for f in files)
    cliques = ", ".join(f"'{f}Clique.parquet'" for f in files)
    con.execute(
        f"CREATE TEMP TABLE hit AS SELECT e.curie, e.clique_leader, e.biolink_type "
        f"FROM read_parquet([{edges}]) e JOIN wanted w ON e.curie = w.curie"
    )
    con.execute(
        f"CREATE TEMP TABLE leader_key AS SELECT e.clique_leader, min(e.curie) AS inchikey, count(*) AS n "
        f"FROM read_parquet([{edges}]) e WHERE e.curie_prefix = 'INCHIKEY' "
        f"AND e.clique_leader IN (SELECT DISTINCT clique_leader FROM hit) GROUP BY e.clique_leader"
    )
    if con.execute("SELECT count(*) FROM leader_key WHERE n > 1").fetchone()[0]:
        raise RuntimeError(
            "A chemical clique holds more than one InChIKey; glom()'s guard no longer matches the build."
        )
    con.execute(
        f"CREATE TEMP TABLE leader_info AS SELECT clique_leader, preferred_name, clique_identifier_count "
        f"FROM read_parquet([{cliques}]) WHERE clique_leader IN (SELECT DISTINCT clique_leader FROM hit)"
    )
    leader_of, type_of = {}, {}
    for curie, leader, btype in con.execute("SELECT * FROM hit").fetchall():
        if curie in leader_of and leader_of[curie] != leader:
            raise RuntimeError(f"{curie} is in two chemical cliques: {leader_of[curie]} and {leader}")
        leader_of[curie] = leader
        type_of[leader] = btype
    key_of = dict(con.execute("SELECT clique_leader, inchikey FROM leader_key").fetchall())
    info = {r[0]: (r[1], r[2]) for r in con.execute("SELECT * FROM leader_info").fetchall()}
    return leader_of, type_of, key_of, info


class Groups:
    """Union-find over existing cliques (keyed by leader) and CURIEs in no clique, with glom()'s InChIKey guard."""

    def __init__(self, key_of):
        self.parent = {}
        self.key = dict(key_of)

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        """Merge a's and b's groups; return 'noop', 'refused' or 'merged'."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return "noop"
        ka, kb = self.key.get(ra), self.key.get(rb)
        if ka and kb and ka != kb:
            return "refused"
        self.parent[rb] = ra
        self.key[ra] = ka or kb
        return "merged"


def write_concords(records_file):
    """Run the production writer and return {concord name: [(UNII, object), ...]}."""
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        chemicals.write_unii_records_concords(
            records_file, t / "UNII_PUBCHEM", t / "UNII_CAS", t / "meta-pubchem.yaml", t / "meta-cas.yaml"
        )
        return {name: list(read_concord_pairs(t / name)) for name in ["UNII_PUBCHEM", "UNII_CAS"]}


def read_record_facts(records_file):
    """Return {UNII CURIE: (SUBSTANCE_TYPE, "INCHIKEY:..." or "")} from the records file."""
    with open(records_file, encoding=UNII_RECORDS_ENCODING) as f:
        return {
            f"UNII:{r['UNII']}": (r["SUBSTANCE_TYPE"], f"INCHIKEY:{r['INCHIKEY']}" if r["INCHIKEY"] else "")
            for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        }


def key_agreement(stated, joined):
    """Compare the InChIKey a UNII record states with the one the clique it joins carries."""
    if not stated:
        return "UNII record states no InChIKey"
    if not joined:
        return "joined cliques have no InChIKey"
    if stated == joined:
        return "same InChIKey"
    if stated.split("-")[0] == joined.split("-")[0]:
        return "same skeleton, different stereo or protonation"
    return "different skeleton"


def apply_concord(name, pairs, groups, leader_of, type_of, key_of, info, facts):
    """Apply one concord's pairs to ``groups``; return (outcome counts, joining rows, refused rows)."""
    outcome, joined, refused = Counter(), [], []
    for unii, other in pairs:
        a, b = leader_of.get(unii, unii), leader_of.get(other, other)
        verdict = groups.union(a, b)
        if verdict == "merged" and (unii not in leader_of or other not in leader_of):
            verdict = "added a CURIE in no clique" if unii in leader_of or other in leader_of else "new clique"
        elif verdict == "merged":
            verdict = "joined two cliques"
            substance_type, stated = facts.get(unii, ("", ""))
            agreement = key_agreement(stated, key_of.get(a) or key_of.get(b) or "")
            joined.append(
                [name, unii, substance_type, agreement, a, type_of[a], info.get(a, ("", ""))[0]]
                + [other, b, type_of[b], info.get(b, ("", ""))[0]]
            )
        elif verdict == "refused":
            refused.append([name, unii, a, key_of.get(a, ""), other, b, key_of.get(b, "")])
        outcome[verdict] += 1
    return outcome, joined, refused


def write_tsv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--records", required=True, help="Latest_UNII_Records.txt")
    parser.add_argument("--build-url", required=True, help="Root URL of a published build with duckdb/parquet/")
    parser.add_argument("--build-name", required=True, help="Build name to record in the output, e.g. 2026jul22")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    raw = write_concords(args.records)
    concords = {name: remove_overused_xrefs(pairs) for name, pairs in raw.items()}
    # The same concords with no SUBSTANCE_TYPE skipped, to measure what that skip removes.
    skipped_types = set(chemicals.UNII_SUBSTANCE_TYPES_WITHOUT_XREFS)
    chemicals.UNII_SUBSTANCE_TYPES_WITHOUT_XREFS = set()
    unskipped = {name: remove_overused_xrefs(pairs) for name, pairs in write_concords(args.records).items()}
    chemicals.UNII_SUBSTANCE_TYPES_WITHOUT_XREFS = skipped_types
    facts = read_record_facts(args.records)

    curies = {c for pairs in [*concords.values(), *unskipped.values()] for pair in pairs for c in pair}
    curies |= {c for pair in INSULIN_CHECKS.values() for c in pair}
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    leader_of, type_of, key_of, info = load_cliques(con, args.build_url, curies)

    summary = {"build": args.build_name, "records_file": Path(args.records).name, "concords": {}}
    groups = Groups(key_of)
    joined_rows, refused_rows = [], []
    # UNII_PUBCHEM is what ships (config.yaml: chemical_concords). UNII_CAS is applied on top of it afterwards, as it
    # would be if it were added after UNII_PUBCHEM, so its figures say what adding it would change.
    for name in ["UNII_PUBCHEM", "UNII_CAS"]:
        outcome, joined, refused = apply_concord(name, concords[name], groups, leader_of, type_of, key_of, info, facts)
        joined_rows += joined
        refused_rows += refused
        summary["concords"][name] = {
            "in chemical_concords": name == "UNII_PUBCHEM",
            "rows written": len(raw[name]),
            "rows after remove_overused_xrefs": len(concords[name]),
            "outcomes": dict(sorted(outcome.items())),
            "pairs joining two cliques, by UNII record's InChIKey vs the joined clique's": dict(
                sorted(Counter(row[3] for row in joined).items())
            ),
            "pairs joining two cliques, by UNII SUBSTANCE_TYPE": dict(Counter(row[2] for row in joined).most_common()),
        }
        if name == "UNII_PUBCHEM":
            members = defaultdict(list)
            for leader in type_of:
                members[groups.find(leader)].append(leader)
            merged = {root: sorted(ms) for root, ms in members.items() if len(ms) > 1}
            summary["UNII_PUBCHEM merged groups"] = {
                "existing cliques merged away": sum(len(ms) - 1 for ms in merged.values()),
                "groups by number of existing cliques": {
                    str(k): v for k, v in sorted(Counter(len(ms) for ms in merged.values()).items())
                },
                "groups by Biolink types joined": dict(
                    Counter(" + ".join(sorted({type_of[m] for m in ms})) for ms in merged.values()).most_common()
                ),
            }
            summary["insulin (#1171), UNII_PUBCHEM"] = {
                species: (
                    "same clique"
                    if groups.find(leader_of.get(u, u)) == groups.find(leader_of.get(p, p))
                    else "separate cliques"
                )
                for species, (u, p) in INSULIN_CHECKS.items()
            }
            write_tsv(
                out / "merged-groups.tsv",
                ["group", "clique_leader", "biolink_type", "inchikey", "preferred_name", "clique_size"],
                [
                    [i, m, type_of[m], key_of.get(m, ""), *info.get(m, ("", ""))]
                    for i, (_, ms) in enumerate(sorted(merged.items(), key=lambda kv: (-len(kv[1]), kv[1][0])), 1)
                    for m in ms
                ],
            )

    # What the SUBSTANCE_TYPE skip removes: UNII_PUBCHEM without it, applied alone to fresh cliques, counting the pairs
    # that join two cliques by the skipped UNIIs' type.
    _, joined, _ = apply_concord(
        "UNII_PUBCHEM", unskipped["UNII_PUBCHEM"], Groups(key_of), leader_of, type_of, key_of, info, facts
    )
    summary["UNII_PUBCHEM pairs joining two cliques that the SUBSTANCE_TYPE skip removes"] = dict(
        Counter(row[2] for row in joined if row[2] in skipped_types)
    )

    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_tsv(
        out / "joining-pairs.tsv",
        ["concord", "unii", "substance_type", "inchikey_agreement", "unii_clique", "unii_clique_type"]
        + ["unii_clique_name", "object", "object_clique", "object_clique_type", "object_clique_name"],
        sorted(joined_rows),
    )
    write_tsv(
        out / "refused-pairs.tsv",
        ["concord", "unii", "unii_clique", "unii_clique_key", "object", "object_clique", "object_clique_key"],
        sorted(refused_rows),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
