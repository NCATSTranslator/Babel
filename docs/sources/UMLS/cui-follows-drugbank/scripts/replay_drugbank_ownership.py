"""Replay "a CUI follows its DrugBank ingredient" (umls.compute_drugbank_owners) over a published build's ids files.

It writes the umls_mesh_ownership rule's file twice -- with MeSH ownership alone, and with DrugBank ownership as
well -- runs every MeSH-owning pipeline's production ``write_umls_ids`` against each, and reports what the
DrugBank rule adds on top of the MeSH rule: which CUIs move, from where, and with which semantic types; which
concords other than ``<pipeline>/concords/UMLS`` still name a moved CUI (the pairs the compendium builds skip);
which of the build's duplicated DrugBank IDs the move resolves; and which CUIs with a DrugBank ingredient the
rule leaves alone, and why. glom() is transitive, so the duplicate count is a prediction; confirm it with
babel-clique-diff after a build.

Inputs are those of ``../../cui-follows-mesh/scripts/replay_mesh_ownership.py``, whose helpers this imports,
plus the build's ``chemicals/ids/DRUGBANK`` (``fetch_build_inputs.py`` exports it). Example (about two minutes):

    uv run python docs/sources/UMLS/cui-follows-mesh/scripts/fetch_build_inputs.py \\
        --build-url <build-url> --output-dir data/duplicate-curies
    uv run python docs/sources/UMLS/cui-follows-drugbank/scripts/replay_drugbank_ownership.py \\
        --ids-dir data/duplicate-curies/ids --reports-dir data/duplicate-curies \\
        --concord-parquet <build-url>/duckdb/Concord.parquet \\
        --output docs/sources/UMLS/cui-follows-drugbank/2026jul22.md
"""

import argparse
import csv
import os
import sys
import tempfile
import textwrap
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "cui-follows-mesh", "scripts")))

import replay_mesh_ownership as mesh_replay  # noqa: E402

from src.datahandlers import umls  # noqa: E402
from src.reports.duckdb_reports import _parse_filenames  # noqa: E402
from src.util import get_config  # noqa: E402


def load_drugbank_concord_edges(concord_parquet):
    """{DrugBank CURIE: {(pipeline, cui)}} for every <pipeline>/concords/UMLS edge to a DrugBank ID."""
    import duckdb

    con = duckdb.connect()
    if concord_parquet.startswith("http"):
        con.execute("INSTALL httpfs; LOAD httpfs;")
    rows = con.execute(
        f"""
        SELECT DISTINCT regexp_extract(filename, 'intermediate/([^/]+)/concords/UMLS$', 1) AS pipeline, subj, obj
        FROM read_parquet('{concord_parquet}')
        WHERE filename LIKE '%/concords/UMLS' AND obj LIKE 'DRUGBANK:%'
        """
    ).fetchall()
    edges = defaultdict(set)
    for pipeline, cui, drugbank in rows:
        if pipeline:
            edges[drugbank].add((pipeline, cui))
    return edges


def examples(cuis, n=3):
    """n CUIs spread across the sorted list rather than its first n."""
    cuis = sorted(cuis)
    step = max(1, len(cuis) // n)
    return ", ".join(cuis[::step][:n])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--umls-dir", default=os.path.join(get_config()["download_directory"], "UMLS"))
    ap.add_argument("--ids-dir", required=True, help="Directory with <pipeline>/{MESH,UMLS,DRUGBANK} ids files")
    ap.add_argument("--reports-dir", required=True, help="Directory with duplicate_curies.tsv")
    ap.add_argument("--concord-parquet", required=True, help="Path or URL of the build's Concord.parquet")
    ap.add_argument("--build", default="2026jul22")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    cfg = get_config()
    mesh_pipelines = cfg["umls_mesh_owning_pipelines"]
    drugbank_pipelines = cfg["umls_drugbank_owning_pipelines"]
    pipelines = mesh_pipelines + ["gene", "process"]
    mrconso = os.path.join(args.umls_dir, "MRCONSO.RRF")
    stn = mesh_replay.read_stn(os.path.join(args.umls_dir, "MRSTY.RRF"))
    mesh_ids = {p: os.path.join(args.ids_dir, p, "MESH") for p in mesh_pipelines}
    drugbank_ids = {p: os.path.join(args.ids_dir, p, "DRUGBANK") for p in drugbank_pipelines}

    before = {}
    after = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        non_mesh = {p: mesh_replay.run_writer(p, args.umls_dir, tmpdir, None) for p in ["gene", "process"]}
        ownership_files = {}
        for label, drugbank in (("mesh", None), ("drugbank", drugbank_ids)):
            ownership_files[label] = os.path.join(tmpdir, f"ownership_{label}.tsv")
            # The same call rule umls_mesh_ownership makes, without and with its drugbank_ids input.
            umls.write_mesh_ownership(
                mrconso,
                mesh_ids,
                ownership_files[label],
                blocklist_files_by_pipeline={"disease": os.path.join(cfg["input_directory"], "badumls")},
                non_mesh_umls_ids_files=list(non_mesh.values()),
                drugbank_ids_files_by_pipeline=drugbank,
            )
        owners_before = umls.read_mesh_ownership(ownership_files["mesh"])
        owners_after = umls.read_mesh_ownership(ownership_files["drugbank"])
        for p in pipelines:
            if p in non_mesh:
                before[p] = after[p] = mesh_replay.read_ids(non_mesh[p])
                continue
            # run_writer() names its output by whether ownership was given, so read each before the next run.
            before[p] = mesh_replay.read_ids(mesh_replay.run_writer(p, args.umls_dir, tmpdir, ownership_files["mesh"]))
            after[p] = mesh_replay.read_ids(
                mesh_replay.run_writer(p, args.umls_dir, tmpdir, ownership_files["drugbank"])
            )

    newly_owned = {cui: owner for cui, owner in owners_after.items() if cui not in owners_before}
    changed = {cui for cui in owners_before if owners_after.get(cui) != owners_before[cui]}
    if changed:
        raise RuntimeError(f"DrugBank ownership changed {len(changed)} MeSH owners, e.g. {sorted(changed)[:5]}")

    lines = [f"# Replaying DrugBank ownership over the {args.build} build", ""]
    lines.append(
        "Generated by `docs/sources/UMLS/cui-follows-drugbank/scripts/replay_drugbank_ownership.py` (see its "
        f"docstring). UMLS from `{args.umls_dir}`; ids files and duplicate reports from the {args.build} build. "
        "Every count is on top of MeSH ownership, which that build did not yet apply."
    )
    lines += ["", "## What the rule changes in each pipeline's `ids/UMLS`", ""]
    lines.append(
        f"MeSH ownership gives {len(owners_before):,} CUIs an owner. DrugBank ownership gives "
        f"{len(newly_owned):,} more an owner and changes none of those."
    )
    lines += [
        "",
        "| pipeline | with MeSH ownership | dropped | added | with DrugBank ownership too |",
        "|---|---:|---:|---:|---:|",
    ]
    for p in pipelines:
        dropped = [c for c in before[p] if c not in after[p]]
        added = [c for c in after[p] if c not in before[p]]
        lines.append(f"| {p} | {len(before[p]):,} | {len(dropped):,} | {len(added):,} | {len(after[p]):,} |")

    lines += ["", "Where the newly owned CUIs were before, and what they are typed as now:", ""]
    lines.append("| from | to | type | CUIs | most common semantic types | examples |")
    lines.append("|---|---|---|---:|---|---|")
    moves = defaultdict(list)
    for cui, (owner, _, biolink_type) in newly_owned.items():
        source = ",".join(sorted(p for p in pipelines if cui in before[p])) or "(no pipeline: leftover)"
        destination = ",".join(sorted(p for p in pipelines if cui in after[p])) or "(nobody)"
        if destination != owner:
            raise RuntimeError(f"{cui} is owned by {owner} but claimed by {destination}")
        moves[(source, destination, biolink_type)].append(cui)
    for (source, destination, biolink_type), cuis in sorted(moves.items(), key=lambda kv: -len(kv[1])):
        types = Counter(t for c in cuis for t in stn[c]).most_common(3)
        lines.append(
            f"| {source} | {destination} | {biolink_type} | {len(cuis):,} | "
            f"{'; '.join(f'{t} ({n:,})' for t, n in types)} | {examples(cuis)} |"
        )

    # CUIs with a DrugBank ingredient that the rule leaves alone.
    cui_to_drugbank = umls.read_cui_to_drugbank_ingredients(mrconso)
    cui_to_mesh = umls.read_cui_to_mesh_descriptors(mrconso)
    mesh_claimed = set()
    for path in mesh_ids.values():
        mesh_claimed |= set(mesh_replay.read_ids(path))
    drugbank_claimed = set()
    for path in drugbank_ids.values():
        drugbank_claimed |= set(mesh_replay.read_ids(path))
    unownable = set(before["gene"]) | set(before["process"])
    left = defaultdict(list)
    for cui, ingredients in cui_to_drugbank.items():
        if cui in newly_owned:
            continue
        where = ",".join(sorted(p for p in pipelines if cui in after[p])) or "(no pipeline: leftover)"
        if cui in owners_before:
            reason = "MeSH ownership already decided it"
        elif cui in unownable:
            reason = "gene or process selects it"
        elif cui_to_mesh.get(cui, set()) & mesh_claimed:
            reason = "its descriptors are claimed, but by two pipelines or one that refuses it"
        elif not ingredients & drugbank_claimed:
            reason = "no ids/DRUGBANK lists its DrugBank ID (no structure in UniChem)"
        else:
            reason = "other"
        left[(reason, where)].append(cui)
    lines += [
        "",
        "## CUIs with a DrugBank ingredient that the rule does not move",
        "",
        f"{len(cui_to_drugbank):,} CUIs have a DrugBank ingredient atom. Those not newly owned:",
        "",
        "| why | where it is | CUIs | most common semantic types | examples |",
        "|---|---|---:|---|---|",
    ]
    for (reason, where), cuis in sorted(left.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
        types = Counter(t for c in cuis for t in stn[c]).most_common(3)
        lines.append(
            f"| {reason} | {where} | {len(cuis):,} | {'; '.join(f'{t} ({n:,})' for t, n in types)} | {examples(cuis)} |"
        )

    several = sorted(cui for cui in newly_owned if len(cui_to_drugbank[cui] & drugbank_claimed) > 1)
    lines += [
        "",
        f"{len(several):,} newly owned CUIs have more than one claimed DrugBank ingredient, which the chemical "
        f"UMLS concord then links to each other: {', '.join(several[:10]) or 'none'}.",
    ]

    lines += [
        "",
        "## Newly owned CUIs that another pipeline's other concords still name",
        "",
        "Each MeSH-owning pipeline's compendium build skips these pairs (`umls.read_cuis_owned_elsewhere()`), "
        "so the CUI leaves the clique that concord put it in. Counted over the build's Concord.parquet:",
        "",
        "| pipeline | concord | owner | CUIs | examples |",
        "|---|---|---|---:|---|",
    ]
    leaks = mesh_replay.load_concords_naming_owned_cuis(args.concord_parquet, newly_owned)
    for (p, concord, owner), cuis in sorted(leaks.items(), key=lambda kv: (kv[0][0], -len(kv[1]), kv[0])):
        lines.append(f"| {p} | {concord} | {owner} | {len(cuis):,} | {examples(cuis)} |")
    if not leaks:
        lines.append("| (none) | | | 0 | |")

    # Predict the effect on duplicated DrugBank IDs.
    with open(os.path.join(args.reports_dir, "duplicate_curies.tsv")) as inf:
        duplicates = [row for row in csv.DictReader(inf, delimiter="\t") if row["curie"].startswith("DRUGBANK:")]
    edges = load_drugbank_concord_edges(args.concord_parquet)
    claimed_before = defaultdict(set)
    claimed_after = defaultdict(set)
    for p in pipelines:
        for cui in before[p]:
            claimed_before[cui].add(p)
        for cui in after[p]:
            claimed_after[cui].add(p)
    outcome = defaultdict(Counter)
    for row in duplicates:
        pair = ", ".join(sorted(set(_parse_filenames(row["filenames"]))))
        # A dragging edge is a non-DrugBank-owning pipeline's UMLS concord edge whose CUI that pipeline claims.
        dragging_before = {
            (p, c) for p, c in edges[row["curie"]] if p not in drugbank_pipelines and p in claimed_before[c]
        }
        dragging_after = {(p, c) for p, c in dragging_before if p in claimed_after[c]}
        if not dragging_before:
            outcome[pair]["already resolved by MeSH ownership, or not dragged through UMLS"] += 1
        elif not dragging_after:
            outcome[pair]["resolved by DrugBank ownership"] += 1
        else:
            outcome[pair]["still dragged"] += 1
    columns = [
        "resolved by DrugBank ownership",
        "already resolved by MeSH ownership, or not dragged through UMLS",
        "still dragged",
    ]
    lines += [
        "",
        "## Predicted effect on DrugBank IDs in two compendia",
        "",
        f"{len(duplicates):,} DrugBank IDs are in more than one compendium in {args.build} "
        "(`reports/duckdb/duplicate_curies.tsv`). A DrugBank ID is dragged when a pipeline other than its owner "
        "claims a CUI that its `concords/UMLS` links to it.",
        "",
        "| compendia | DrugBank IDs | " + " | ".join(columns) + " |",
        "|---|---:|" + "---:|" * len(columns),
    ]
    for pair, counts in sorted(outcome.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(f"| {pair} | {sum(counts.values()):,} | " + " | ".join(f"{counts[c]:,}" for c in columns) + " |")

    # Wrap prose and bullets to the repository's 100-column Markdown rule; tables and headings are exempt.
    def wrap(line):
        if not line or line.startswith(("|", "#")):
            return line
        return textwrap.fill(line, width=100, break_long_words=False, break_on_hyphens=False)

    with open(args.output, "w") as outf:
        outf.write("\n".join(wrap(line) for line in lines).rstrip("\n") + "\n")
    print(f"Wrote {args.output}")  # noqa: T201


if __name__ == "__main__":
    main()
