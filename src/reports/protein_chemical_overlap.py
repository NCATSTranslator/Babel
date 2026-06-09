"""Protein/Chemical overlap report.

Babel deliberately keeps the chemical compendia (``biolink:ChemicalEntity`` and its subtypes:
SmallMolecule, Drug, MolecularMixture, ChemicalMixture, ComplexMolecularMixture, Polypeptide)
separate from the protein compendium (``biolink:Protein``). But a large family of biomedical
concepts straddles that boundary -- complex chemicals that are proteins (human insulin), grouping
concepts (hemoglobins, insulins), formulations, and amino-acid sequences -- and many source
vocabularies cross-reference a chemical identifier to a protein identifier as if they were the same
thing.

This report inventories exactly those crossings so they can be reviewed by the Translator community
when deciding whether (and how) to combine proteins and chemicals (see Babel issues #706, #667,
#440, #513, #276). It produces four files:

* ``bridges`` -- one row per concord (cross-reference) edge whose two endpoints landed in different
  cliques, one on the chemical side and one on the protein side. This is the raw evidence: the
  cross-reference that *would* merge a chemical clique with a protein clique, attributed to the
  source concord that asserts it.
* ``candidate_pairs`` -- the bridges deduplicated to unique (chemical clique leader, protein clique
  leader) pairs, with the supporting sources/predicates aggregated. This is the SSSOM-able list of
  mappings that a DrugProtein conflation (#440) would apply.
* ``duplicate_curies`` -- CURIEs that ended up in *both* a chemical clique and a protein clique (the
  same identifier duplicated across two cliques, #276/#513). Scoped to CURIEs that are referenced by
  a concord, since those are the cross-reference-induced duplicates relevant here and that scope
  keeps the report's memory bounded; for the exhaustive across-the-whole-build duplicate list, query
  the DuckDB ``Edge`` table instead (one CURIE in two ``clique_leader``\\ s).
* ``summary`` -- per-source counts, split by the discriminators below, for a quick overview.

Each candidate carries two discriminators that help triage the cases:

* ``chem_has_inchikey`` -- whether the chemical clique contains an ``INCHIKEY`` structure. A real,
  structurally-defined small molecule that is cross-referenced to a protein is usually a *bug* (e.g.
  CHEBI:24536 "Pepsin" actually being hexachlorocyclohexane); the genuine "protein-as-chemical"
  cases (prothrombin, hemoglobin) characteristically have *no* InChIKey.
* ``prot_reaches_gene`` -- whether the protein clique is GeneProtein-conflated, i.e. merging it with
  a chemical would make that chemical normalize all the way to a *gene* -- the confusing downstream
  effect that motivated issue #662.
"""

import csv
import os
from collections import defaultdict
from dataclasses import dataclass

import jsonlines

from src.prefixes import INCHIKEY, NCBIGENE, UNIPROTKB
from src.util import get_logger

logger = get_logger(__name__)

INCHIKEY_PREFIX = INCHIKEY + ":"
NCBIGENE_PREFIX = NCBIGENE + ":"
UNIPROTKB_PREFIX = UNIPROTKB + ":"

# How many example bridge edges to record per candidate pair.
MAX_EXAMPLE_BRIDGES = 3


@dataclass
class CliqueInfo:
    """The bits of a clique we need to describe a boundary crossing."""

    leader: str
    label: str
    biolink_type: str
    size: int
    has_inchikey: bool


def concord_source_label(path):
    """Turn a concord file path into a short, stable provenance label.

    ``.../intermediate/chemicals/concords/DrugCentral`` -> ``chemicals/DrugCentral``
    ``.../intermediate/protein/concords/UNICHEM/UNICHEM_1_7`` -> ``protein/UNICHEM/UNICHEM_1_7``

    Falls back to the basename if ``/concords/`` is not in the path.
    """
    norm = path.replace(os.sep, "/")
    marker = "/concords/"
    idx = norm.find(marker)
    if idx == -1:
        return os.path.basename(path)
    after = norm[idx + len(marker) :]
    before = norm[:idx]
    group = before.rsplit("/", 1)[-1] if "/" in before else before
    return f"{group}/{after}"


def iter_concord_edges(concord_files):
    """Yield ``(subject, predicate, object, source_label)`` for every triple in the concord files.

    Skips metadata YAML sidecars and malformed (non-three-column) lines.
    """
    for path in concord_files:
        if path.endswith(".yaml") or os.path.basename(path).startswith("metadata-"):
            continue
        source = concord_source_label(path)
        with open(path) as inf:
            for line_number, line in enumerate(inf, start=1):
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) != 3:
                    logger.warning(f"Skipping malformed concord line {path}:{line_number}: {line!r}")
                    continue
                subject, predicate, object_ = parts
                yield subject, predicate, object_, source


def collect_concord_curies(concord_files):
    """Return the set of every CURIE mentioned on either side of any concord edge."""
    curies = set()
    for subject, _predicate, object_, _source in iter_concord_edges(concord_files):
        curies.add(subject)
        curies.add(object_)
    return curies


def load_clique_index(compendium_files, restrict_to):
    """Stream the compendia and return ``{curie: CliqueInfo}`` for every CURIE in ``restrict_to``.

    Memory is bounded by ``len(restrict_to)``, not by the (potentially enormous) compendia: we only
    keep an entry for CURIEs that actually appear in a concord, since only those can take part in a
    boundary crossing.
    """
    index = {}
    for path in compendium_files:
        logger.info(f"Indexing cliques from {path}")
        with jsonlines.open(path) as reader:
            for clique in reader:
                identifiers = [entry["i"] for entry in clique["identifiers"]]
                relevant = [curie for curie in identifiers if curie in restrict_to]
                if not relevant:
                    continue
                info = CliqueInfo(
                    leader=identifiers[0],
                    label=clique.get("preferred_name") or clique["identifiers"][0].get("l") or "",
                    biolink_type=clique.get("type", ""),
                    size=len(identifiers),
                    has_inchikey=any(curie.startswith(INCHIKEY_PREFIX) for curie in identifiers),
                )
                for curie in relevant:
                    index[curie] = info
    logger.info(f"Indexed {len(index):,} CURIEs from {len(compendium_files)} compendia.")
    return index


def load_geneprotein_proteins(geneprotein_conflation):
    """Return the set of UniProtKB CURIEs conflated with a gene in the GeneProtein conflation.

    These are the proteins for which a chemical/protein merge would make a chemical normalize all
    the way to a gene (issue #662). The conflation file is JSONL, one group per line, each group a
    list of CURIEs (NCBIGene first by construction).
    """
    proteins_reaching_gene = set()
    if not geneprotein_conflation:
        return proteins_reaching_gene
    with jsonlines.open(geneprotein_conflation) as reader:
        for group in reader:
            if any(curie.startswith(NCBIGENE_PREFIX) for curie in group):
                for curie in group:
                    if curie.startswith(UNIPROTKB_PREFIX):
                        proteins_reaching_gene.add(curie)
    logger.info(f"Loaded {len(proteins_reaching_gene):,} gene-reaching proteins from {geneprotein_conflation}.")
    return proteins_reaching_gene


def _normalize_label(label):
    return (label or "").strip().lower()


def _curie_prefix(curie):
    return curie.split(":", 1)[0] if ":" in curie else curie


def _bool_str(value):
    return "true" if value else "false"


def _write_duplicate_curies(path, chem_index, prot_index):
    """Write the CURIEs that appear in both a chemical clique and a protein clique."""
    shared = sorted(set(chem_index) & set(prot_index))
    with open(path, "w", newline="") as outf:
        writer = csv.writer(outf, delimiter="\t", lineterminator="\n")
        writer.writerow(
            ["curie", "curie_prefix", "chem_leader", "chem_type", "chem_has_inchikey", "prot_leader", "prot_type"]
        )
        for curie in shared:
            chem = chem_index[curie]
            prot = prot_index[curie]
            writer.writerow(
                [
                    curie,
                    _curie_prefix(curie),
                    chem.leader,
                    chem.biolink_type,
                    _bool_str(chem.has_inchikey),
                    prot.leader,
                    prot.biolink_type,
                ]
            )
    return len(shared)


def generate_protein_chemical_overlap_report(
    chemical_compendia,
    protein_compendia,
    concord_files,
    bridges_tsv,
    candidate_pairs_tsv,
    duplicate_curies_tsv,
    summary_tsv,
    geneprotein_conflation=None,
):
    """Generate the protein/chemical overlap report.

    :param chemical_compendia: paths to the chemical-side compendia (ChemicalEntity.txt,
        SmallMolecule.txt, Drug.txt, MolecularMixture.txt, ChemicalMixture.txt,
        ComplexMolecularMixture.txt, Polypeptide.txt).
    :param protein_compendia: paths to the protein-side compendia (Protein.txt).
    :param concord_files: paths to every concord file used to build those compendia. Metadata YAML
        sidecars are ignored automatically.
    :param bridges_tsv: output -- one row per boundary-crossing concord edge.
    :param candidate_pairs_tsv: output -- deduplicated (chem leader, prot leader) merge candidates.
    :param duplicate_curies_tsv: output -- CURIEs present in both a chemical and a protein clique.
    :param summary_tsv: output -- per-source summary counts.
    :param geneprotein_conflation: optional GeneProtein.txt conflation, used to flag proteins whose
        merge would reach a gene.
    :return: a dict of summary counts (also useful for tests/logging).
    """
    for path in (bridges_tsv, candidate_pairs_tsv, duplicate_curies_tsv, summary_tsv):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    logger.info("Collecting CURIEs referenced by concords...")
    concord_curies = collect_concord_curies(concord_files)
    logger.info(f"{len(concord_curies):,} distinct CURIEs referenced by {len(concord_files)} concord files.")

    chem_index = load_clique_index(chemical_compendia, concord_curies)
    prot_index = load_clique_index(protein_compendia, concord_curies)
    gene_reaching_proteins = load_geneprotein_proteins(geneprotein_conflation)

    duplicate_count = _write_duplicate_curies(duplicate_curies_tsv, chem_index, prot_index)
    logger.info(f"Wrote {duplicate_count:,} duplicate CURIEs to {duplicate_curies_tsv}.")

    # Accumulators for the deduplicated candidate pairs and the per-source summary.
    pairs = {}
    source_edge_count = defaultdict(int)
    source_pairs = defaultdict(set)
    source_with_inchikey = defaultdict(int)
    source_without_inchikey = defaultdict(int)
    source_reaches_gene = defaultdict(int)

    bridge_edge_count = 0
    with open(bridges_tsv, "w", newline="") as bridges_out:
        writer = csv.writer(bridges_out, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "source_concord",
                "predicate",
                "bridge_subject",
                "bridge_object",
                "subject_side",
                "chem_curie",
                "chem_leader",
                "chem_leader_label",
                "chem_type",
                "chem_clique_size",
                "chem_has_inchikey",
                "prot_curie",
                "prot_leader",
                "prot_leader_label",
                "prot_type",
                "prot_clique_size",
                "prot_reaches_gene",
                "label_match",
            ]
        )

        for subject, predicate, object_, source in iter_concord_edges(concord_files):
            # Only edges that genuinely cross the chemical/protein boundary are of interest.
            if subject in chem_index and object_ in prot_index:
                chem_curie, prot_curie, subject_side = subject, object_, "chemical"
            elif subject in prot_index and object_ in chem_index:
                chem_curie, prot_curie, subject_side = object_, subject, "protein"
            else:
                continue

            chem = chem_index[chem_curie]
            prot = prot_index[prot_curie]
            reaches_gene = prot.leader in gene_reaching_proteins
            label_match = _normalize_label(chem.label) != "" and _normalize_label(chem.label) == _normalize_label(
                prot.label
            )

            bridge_edge_count += 1
            writer.writerow(
                [
                    source,
                    predicate,
                    subject,
                    object_,
                    subject_side,
                    chem_curie,
                    chem.leader,
                    chem.label,
                    chem.biolink_type,
                    chem.size,
                    _bool_str(chem.has_inchikey),
                    prot_curie,
                    prot.leader,
                    prot.label,
                    prot.biolink_type,
                    prot.size,
                    _bool_str(reaches_gene),
                    _bool_str(label_match),
                ]
            )

            # Per-source summary.
            source_edge_count[source] += 1
            source_pairs[source].add((chem.leader, prot.leader))
            if chem.has_inchikey:
                source_with_inchikey[source] += 1
            else:
                source_without_inchikey[source] += 1
            if reaches_gene:
                source_reaches_gene[source] += 1

            # Deduplicated candidate pair.
            key = (chem.leader, prot.leader)
            agg = pairs.get(key)
            if agg is None:
                agg = {
                    "chem_leader": chem.leader,
                    "chem_label": chem.label,
                    "chem_type": chem.biolink_type,
                    "chem_size": chem.size,
                    "chem_has_inchikey": chem.has_inchikey,
                    "prot_leader": prot.leader,
                    "prot_label": prot.label,
                    "prot_type": prot.biolink_type,
                    "prot_size": prot.size,
                    "prot_reaches_gene": reaches_gene,
                    "label_match": label_match,
                    "edge_count": 0,
                    "sources": set(),
                    "predicates": set(),
                    "example_bridges": [],
                }
                pairs[key] = agg
            agg["edge_count"] += 1
            agg["sources"].add(source)
            agg["predicates"].add(predicate)
            if len(agg["example_bridges"]) < MAX_EXAMPLE_BRIDGES:
                agg["example_bridges"].append(f"{subject} {predicate} {object_}")

    _write_candidate_pairs(candidate_pairs_tsv, pairs)
    logger.info(f"Wrote {len(pairs):,} candidate pairs ({bridge_edge_count:,} bridge edges) to {candidate_pairs_tsv}.")

    _write_summary(
        summary_tsv,
        source_edge_count,
        source_pairs,
        source_with_inchikey,
        source_without_inchikey,
        source_reaches_gene,
    )

    counts = {
        "concord_curies": len(concord_curies),
        "chemical_indexed": len(chem_index),
        "protein_indexed": len(prot_index),
        "duplicate_curies": duplicate_count,
        "bridge_edges": bridge_edge_count,
        "candidate_pairs": len(pairs),
    }
    logger.info(f"Protein/chemical overlap report complete: {counts}")
    return counts


def _write_candidate_pairs(path, pairs):
    rows = sorted(pairs.values(), key=lambda agg: (-agg["edge_count"], agg["chem_leader"], agg["prot_leader"]))
    with open(path, "w", newline="") as outf:
        writer = csv.writer(outf, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "chem_leader",
                "chem_leader_label",
                "chem_type",
                "chem_clique_size",
                "chem_has_inchikey",
                "prot_leader",
                "prot_leader_label",
                "prot_type",
                "prot_clique_size",
                "prot_reaches_gene",
                "label_match",
                "support_edge_count",
                "sources",
                "predicates",
                "example_bridges",
            ]
        )
        for agg in rows:
            writer.writerow(
                [
                    agg["chem_leader"],
                    agg["chem_label"],
                    agg["chem_type"],
                    agg["chem_size"],
                    _bool_str(agg["chem_has_inchikey"]),
                    agg["prot_leader"],
                    agg["prot_label"],
                    agg["prot_type"],
                    agg["prot_size"],
                    _bool_str(agg["prot_reaches_gene"]),
                    _bool_str(agg["label_match"]),
                    agg["edge_count"],
                    "|".join(sorted(agg["sources"])),
                    "|".join(sorted(agg["predicates"])),
                    "|".join(agg["example_bridges"]),
                ]
            )


def _write_summary(
    path,
    source_edge_count,
    source_pairs,
    source_with_inchikey,
    source_without_inchikey,
    source_reaches_gene,
):
    with open(path, "w", newline="") as outf:
        writer = csv.writer(outf, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "source_concord",
                "bridge_edges",
                "distinct_candidate_pairs",
                "edges_with_chem_inchikey",
                "edges_without_chem_inchikey",
                "edges_prot_reaches_gene",
            ]
        )
        totals = [0, 0, 0, 0, 0]
        for source in sorted(source_edge_count, key=lambda s: (-source_edge_count[s], s)):
            row = [
                source_edge_count[source],
                len(source_pairs[source]),
                source_with_inchikey[source],
                source_without_inchikey[source],
                source_reaches_gene[source],
            ]
            writer.writerow([source, *row])
            for i, value in enumerate(row):
                totals[i] += value
        # The distinct-pairs total is across all sources (a pair can be supported by several sources).
        all_pairs = set()
        for source_pair_set in source_pairs.values():
            all_pairs |= source_pair_set
        totals[1] = len(all_pairs)
        writer.writerow(["TOTAL", *totals])
