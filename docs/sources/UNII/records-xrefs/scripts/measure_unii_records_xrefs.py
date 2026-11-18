"""Measure what the UNII-records concords (UNII -> PubChem CID, UNII -> CAS) would do to a finished build's chemical cliques.

Writes the two concords with the production writer (``chemicals.write_unii_records_concords``), filters each with the
production ``remove_overused_xrefs``, looks up every endpoint's clique in the build's chemical ``Edge.parquet`` files,
and then replays the pairs through the production ``glom()`` with ``config.yaml: chemical_unique_prefixes``. Each
existing clique stands in as its leader plus its InChIKey, which is all ``glom()``'s guard looks at, and a CURIE in no
clique joins as itself. UNII_PUBCHEM, the concord the build uses, is applied first and in file order, as
``build_untyped_compendia()`` does; UNII_CAS is then applied on top, to say what adding it too would change.

Each pair is labelled by the state of the groups when it is applied, not by where its endpoints sat in the build: a
pair between two CIDs that were in no clique, but that earlier pairs have each attached to a clique, joins two cliques.

With ``--ids-dir`` (a directory holding the build's chemical ``ids/UNII`` and ``ids/PUBCHEM.COMPOUND``) and
``--fetch-pubchem-titles``, it also says why each UNII_PUBCHEM CURIE that is in no clique of the build is there: missing
from the build's ids file, and, for a CID, whether PubChem gives it a title today (the PubChem ids file is every CID in
PubChem's ``CID-Title.gz``, so an untitled CID never gets a row).

It is a model, not a rebuild. It starts from the build's *typed* cliques, so it cannot see the post-glom MolecularMixture
split (Babel #83) or a clique whose InChIKey ``write_compendium()`` dropped (Drug and Food), and it assumes the new
concords run last (they are last in ``config.yaml: chemical_concords``). A real build's clique diff is the check on it.

Usage (the build URL is a published build root holding ``duckdb/parquet/``)::

    uv run python docs/sources/UNII/records-xrefs/scripts/measure_unii_records_xrefs.py \
        --records babel_downloads/UNII/Latest_UNII_Records.txt \
        --build-url <build-root-url> --build-name 2026jul22 \
        --ids-dir <the build's intermediate/chemicals/ids> --fetch-pubchem-titles \
        --output-dir docs/sources/UNII/records-xrefs/output
"""

import argparse
import csv
import json
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import duckdb
import requests

import src.createcompendia.chemicals as chemicals
from src.babel_utils import glom, remove_overused_xrefs, unique_prefixes_from_config
from src.datahandlers.unii import read_unii_records
from src.model.intermediates import read_concord_pairs
from src.util import get_config

# PUG REST's property endpoint, POSTed a comma-separated "cid" list; a CID PubChem gives no title has no Title key.
PUG_TITLE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/property/Title/JSON"
# CIDs per PUG REST request; PubChem asks for no more than five requests a second.
PUG_BATCH_SIZE = 200

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


class CliqueReplay:
    """glom()'s ``conc_set``, seeded with the build's cliques, that concord pairs are replayed into one at a time.

    Each existing clique is seeded as ``{leader, its InChIKey}``: ``glom()`` refuses a pair only when the merged set
    would hold two different identifiers of a unique prefix, so the leader (to find the clique) and the key (for the
    guard) are the members that matter. The guard itself is ``glom()``'s, so this cannot drift from the build's rule.
    """

    def __init__(self, type_of, key_of):
        self.unique_prefixes = unique_prefixes_from_config("chemical_unique_prefixes")
        self.leaders = frozenset(type_of)
        self.sets = {}
        for leader in sorted(type_of):
            members = {leader} | ({key_of[leader]} if leader in key_of else set())
            for m in members:
                if m in self.sets:
                    raise RuntimeError(f"{m} is in two chemical cliques")
                self.sets[m] = members

    def group(self, x):
        return self.sets.get(x, {x})

    def same_group(self, x, y):
        return x in self.sets and self.sets.get(y) is self.sets[x]

    def cliques(self, x):
        """The existing cliques (by leader) in x's group."""
        return sorted(self.group(x) & self.leaders)

    def key(self, x):
        """The InChIKey x's group carries, or ""."""
        return next((m for m in sorted(self.group(x)) if m.startswith("INCHIKEY:")), "")

    def apply(self, a, b):
        """Replay the pair (a, b) through glom(); return 'noop', 'merged' or 'refused'."""
        if self.same_group(a, b):
            return "noop"
        glom(self.sets, [(a, b)], unique_prefixes=self.unique_prefixes)
        return "merged" if self.same_group(a, b) else "refused"


def write_concords(records_file, skip_substance_types=chemicals.UNII_SUBSTANCE_TYPES_WITHOUT_XREFS):
    """Run the production writer and return {concord name: [(UNII, object), ...]}."""
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        chemicals.write_unii_records_concords(
            records_file,
            t / "UNII_PUBCHEM",
            t / "UNII_CAS",
            t / "meta-pubchem.yaml",
            t / "meta-cas.yaml",
            skip_substance_types=skip_substance_types,
        )
        return {name: list(read_concord_pairs(t / name)) for name in ["UNII_PUBCHEM", "UNII_CAS"]}


def read_record_facts(records_file):
    """Return {UNII CURIE: (SUBSTANCE_TYPE, "INCHIKEY:..." or "")} from the records file."""
    return {
        f"UNII:{r['UNII']}": (r["SUBSTANCE_TYPE"], f"INCHIKEY:{r['INCHIKEY']}" if r["INCHIKEY"] else "")
        for r in read_unii_records(records_file)
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


def apply_concord(name, pairs, replay, leader_of, type_of, info, facts):
    """Apply one concord's pairs to ``replay``; return (outcome counts, joining rows, refused rows).

    A pair's outcome, and the cliques and InChIKeys its rows name, come from the endpoints' groups just before the
    pair is applied. An endpoint in no clique of the build is reported by the first clique its group has gained.
    """
    outcome, joined, refused = Counter(), [], []
    for unii, other in pairs:
        a, b = leader_of.get(unii, unii), leader_of.get(other, other)
        cliques_a, cliques_b = replay.cliques(a), replay.cliques(b)
        key_a, key_b = replay.key(a), replay.key(b)
        verdict = replay.apply(a, b)
        clique_a = a if a in type_of else (cliques_a[0] if cliques_a else "")
        clique_b = b if b in type_of else (cliques_b[0] if cliques_b else "")
        if verdict == "merged":
            if cliques_a and cliques_b:
                verdict = "joined two cliques"
                substance_type, stated = facts.get(unii, ("", ""))
                joined.append(
                    [name, unii, substance_type, key_agreement(stated, key_a or key_b)]
                    + [clique_a, type_of[clique_a], info.get(clique_a, ("", ""))[0]]
                    + [other, clique_b, type_of[clique_b], info.get(clique_b, ("", ""))[0]]
                )
            elif cliques_a or cliques_b:
                verdict = "added a CURIE in no clique"
            else:
                verdict = "new clique"
        elif verdict == "refused":
            refused.append([name, unii, clique_a, key_a, other, clique_b, key_b])
        outcome[verdict] += 1
    return outcome, joined, refused


def read_ids_curies(ids_file, wanted):
    """Return the CURIEs in ``wanted`` that have a row in ``ids_file`` (streamed: PUBCHEM.COMPOUND is ~6 GB)."""
    found = set()
    with open(ids_file) as f:
        for line in f:
            curie = line.split("\t", 1)[0]
            if curie in wanted:
                found.add(curie)
    return found


def fetch_pubchem_titles(cid_curies):
    """Return {CID CURIE: PubChem's title today, "" if untitled}; a CID PubChem doesn't return is left out."""
    numbers = sorted(int(c.split(":")[1]) for c in cid_curies)
    titles = {}
    for i in range(0, len(numbers), PUG_BATCH_SIZE):
        batch = ",".join(str(n) for n in numbers[i : i + PUG_BATCH_SIZE])
        response = requests.post(PUG_TITLE_URL, data={"cid": batch}, timeout=120)
        response.raise_for_status()
        for row in response.json()["PropertyTable"]["Properties"]:
            titles[f"PUBCHEM.COMPOUND:{row['CID']}"] = row.get("Title", "")
        time.sleep(0.5)
    return titles


def explain_unplaced(curies, ids_dir, fetch_titles):
    """Return a row per CURIE in no clique of the build: [curie, in the build's ids file, PubChem title today]."""
    in_ids = {}
    for prefix in ["UNII", "PUBCHEM.COMPOUND"]:
        wanted = {c for c in curies if c.startswith(prefix + ":")}
        found = read_ids_curies(Path(ids_dir) / prefix, wanted) if ids_dir else set()
        in_ids.update({c: ("yes" if c in found else "no") if ids_dir else "" for c in wanted})
    cids = [c for c in curies if c.startswith("PUBCHEM.COMPOUND:")]
    titles = fetch_pubchem_titles(cids) if fetch_titles else {}

    def title_status(c):
        if not fetch_titles or not c.startswith("PUBCHEM.COMPOUND:"):
            return ""
        if c not in titles:
            return "not in PubChem"
        return titles[c] or "(untitled)"

    return [[c, in_ids.get(c, ""), title_status(c)] for c in curies]


def describe_unplaced(curie, in_ids, title):
    """Summarise one explain_unplaced() row as e.g. "PUBCHEM.COMPOUND / not in the build's ids file / untitled"."""
    parts = [curie.split(":")[0]]
    if in_ids:
        parts.append("in the build's ids file" if in_ids == "yes" else "not in the build's ids file")
    if title:
        parts.append({"not in PubChem": "not in PubChem", "(untitled)": "untitled in PubChem"}.get(title, "titled"))
    return " / ".join(parts)


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
    parser.add_argument(
        "--ids-dir", help="The build's intermediate/chemicals/ids, to check CURIEs in no clique against"
    )
    parser.add_argument(
        "--fetch-pubchem-titles", action="store_true", help="Ask PubChem whether each CID in no clique has a title"
    )
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    raw = write_concords(args.records)
    concords = {name: remove_overused_xrefs(pairs) for name, pairs in raw.items()}
    # The same concords with no SUBSTANCE_TYPE skipped, to measure what that skip removes.
    skipped_types = chemicals.UNII_SUBSTANCE_TYPES_WITHOUT_XREFS
    unskipped = {
        name: remove_overused_xrefs(pairs)
        for name, pairs in write_concords(args.records, skip_substance_types=frozenset()).items()
    }
    facts = read_record_facts(args.records)

    curies = {c for pairs in [*concords.values(), *unskipped.values()] for pair in pairs for c in pair}
    curies |= {c for pair in INSULIN_CHECKS.values() for c in pair}
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    leader_of, type_of, key_of, info = load_cliques(con, args.build_url, curies)

    summary = {"build": args.build_name, "records_file": Path(args.records).name, "concords": {}}
    replay = CliqueReplay(type_of, key_of)
    joined_rows, refused_rows = [], []
    # UNII_PUBCHEM is what ships (config.yaml: chemical_concords). UNII_CAS is applied on top of it afterwards, as it
    # would be if it were added after UNII_PUBCHEM, so its figures say what adding it would change.
    for name in ["UNII_PUBCHEM", "UNII_CAS"]:
        outcome, joined, refused = apply_concord(name, concords[name], replay, leader_of, type_of, info, facts)
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
                members[id(replay.sets[leader])].append(leader)
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
                    "same clique" if replay.same_group(leader_of.get(u, u), leader_of.get(p, p)) else "separate cliques"
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

    # Why a UNII_PUBCHEM CURIE is in no clique of the build.
    unplaced = sorted({c for pair in concords["UNII_PUBCHEM"] for c in pair if c not in leader_of})
    unplaced_rows = explain_unplaced(unplaced, args.ids_dir, args.fetch_pubchem_titles)
    summary["UNII_PUBCHEM CURIEs in no clique of the build"] = dict(
        sorted(Counter(describe_unplaced(*row) for row in unplaced_rows).items())
    )
    write_tsv(
        out / "curies-in-no-clique.tsv",
        ["curie", "in_build_ids_file", "pubchem_title_today"],
        unplaced_rows,
    )

    # What the SUBSTANCE_TYPE skip removes: UNII_PUBCHEM without it, applied alone to fresh cliques, counting the pairs
    # that join two cliques by the skipped UNIIs' type.
    _, joined, _ = apply_concord(
        "UNII_PUBCHEM", unskipped["UNII_PUBCHEM"], CliqueReplay(type_of, key_of), leader_of, type_of, info, facts
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
