"""
conflation_reports.py - Reports for conflation files.
"""

import json
import logging
import os
from collections import defaultdict


def build_curie_taxa_map(compendium_path):
    """
    Read a JSONL compendium file and return a dict mapping each CURIE to its set of taxa.

    :param compendium_path: Path to a JSONL compendium file.
    :return: A dict of {curie: set of taxon CURIEs}.
    """
    curie_taxa = {}
    with open(compendium_path) as f:
        for line in f:
            clique = json.loads(line)
            for id_info in clique.get("identifiers", []):
                curie = id_info["i"]
                taxa = set(id_info.get("t", []))
                if curie in curie_taxa:
                    curie_taxa[curie].update(taxa)
                else:
                    curie_taxa[curie] = taxa
    return curie_taxa


def generate_taxon_report_for_geneprotein_conflation(conflation_path, gene_compendium_path, protein_compendium_path, report_path):
    """
    Generate a taxon report for the GeneProtein conflation file.

    For each conflation clique, collects the union of all taxa from the constituent
    Gene and Protein compendium entries, then reports how many cliques belong to each
    taxon and warns about any clique spanning multiple taxa.

    :param conflation_path: Path to the GeneProtein.txt conflation file (JSONL, each line a JSON array of CURIEs).
    :param gene_compendium_path: Path to the Gene.txt compendium file.
    :param protein_compendium_path: Path to the Protein.txt compendium file.
    :param report_path: Path to write the JSON report.
    """
    logging.info(f"Building CURIE→taxa map from {gene_compendium_path}")
    curie_taxa = build_curie_taxa_map(gene_compendium_path)
    logging.info(f"Building CURIE→taxa map from {protein_compendium_path}")
    curie_taxa.update(build_curie_taxa_map(protein_compendium_path))
    logging.info(f"CURIE→taxa map built with {len(curie_taxa):,} entries")

    total_conflations = 0
    conflations_with_taxa = 0
    conflations_without_taxa = 0
    conflations_by_taxon = defaultdict(int)
    multi_taxon_conflation_count = 0
    multi_taxon_conflation_examples = []

    with open(conflation_path) as f:
        for line in f:
            clique = json.loads(line)
            total_conflations += 1

            if total_conflations % 1000000 == 0:
                logging.info(f"Processed {total_conflations:,} conflation cliques")

            # Union taxa across all CURIEs in this conflation clique.
            clique_taxa = set()
            for curie in clique:
                clique_taxa.update(curie_taxa.get(curie, set()))

            if clique_taxa:
                conflations_with_taxa += 1
                for taxon in clique_taxa:
                    conflations_by_taxon[taxon] += 1
            else:
                conflations_without_taxa += 1

            if len(clique_taxa) > 1:
                multi_taxon_conflation_count += 1
                logging.warning(f"Multi-taxon conflation clique: {clique} has taxa {sorted(clique_taxa)}")
                if len(multi_taxon_conflation_examples) < 100:
                    multi_taxon_conflation_examples.append({"clique": clique, "taxa": sorted(clique_taxa)})

    if multi_taxon_conflation_count > 0:
        logging.warning(
            f"Found {multi_taxon_conflation_count:,} conflation cliques spanning multiple taxa "
            f"out of {total_conflations:,} total cliques."
        )

    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    report = {
        "conflation_path": conflation_path,
        "gene_compendium_path": gene_compendium_path,
        "protein_compendium_path": protein_compendium_path,
        "report_path": report_path,
        "total_conflations": total_conflations,
        "conflations_with_taxa": conflations_with_taxa,
        "conflations_without_taxa": conflations_without_taxa,
        "conflations_by_taxon_count": len(conflations_by_taxon),
        "conflations_by_taxon": dict(conflations_by_taxon),
        "multi_taxon_conflation_count": multi_taxon_conflation_count,
        "multi_taxon_conflation_examples": multi_taxon_conflation_examples,
    }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    logging.info(
        f"Taxon report written to {report_path}: "
        f"{total_conflations:,} total, {conflations_with_taxa:,} with taxa, "
        f"{multi_taxon_conflation_count:,} multi-taxon."
    )
