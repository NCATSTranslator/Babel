#!/usr/bin/env python3

"""
conflate-synonyms.py is a Python script for conflating synonym files using one or more
conflation files.
"""

import gzip
import json
from collections import defaultdict

from src import util
from src.babel_utils import get_numerical_curie_suffix

logger = util.get_logger(__name__)


# click.command()
# click.option('--conflation-file', multiple=True, type=click.Path(exists=True))
# click.option('--output', type=click.Path(exists=False), default='-')
# click.argument("synonym_files", nargs=-1, type=click.Path(exists=True))
def conflate_synonyms(synonym_files_gz, compendia_files, conflation_file, output_gz):
    """
    Generate a synonym file based on a single input synonym, the conflation described in the input conflation files,
    and any cross-references present in the input compendia files.

    :param synonym_files_gz: The input synonym files (gzipped).
    :param conflation_file: Any conflation files to apply.
    :param output_gz: The file to write the synonyms to.
    :return:
    """

    logger.info(f"conflate_synonyms({synonym_files_gz}, {compendia_files}, {conflation_file}, {output_gz})")

    # Some common code to manage the conflation index.
    # This is simply a large dictionary, where every key is an identifier and the value is the identifier to map it to.
    conflation_index = dict()

    # This is a map of primary IDs to the list of conflation IDs. This allows us to conflate terms in the correct order.
    conflations = defaultdict(list)

    # Step 1. Load all the conflations. We only need to work on these identifiers, so that simplifies our work.
    for conflation_filename in conflation_file:
        logger.info(f"Reading conflation file {conflation_filename}")
        with open(conflation_filename) as conflationf:
            count_primary = 0
            count_secondary = 0
            for line in conflationf:
                conflation = json.loads(line)

                # The conflation line is a list of identifiers, e.g. `["ID1", "ID2", "ID3"]`
                # Note that we map the primary identifier to itself.
                for ident in conflation:
                    if ident in conflation_index and conflation_index[ident] != conflation[0]:
                        logger.error(
                            f"Secondary ID {ident} is mapped to both {conflation_index[ident]} and "
                            + f"{conflation[0]}, the latter will be used."
                        )
                    conflation_index[ident] = conflation[0]
                    count_secondary += 1

                # Store the entire conflation list for later use.
                if conflation[0] in conflations:
                    logger.error(
                        f"Two conflations have the same primary ID: {conflation} and {conflations[conflation[0]]}"
                    )
                conflations[conflation[0]] = conflation
                count_primary += 1

            logger.info(
                f"Loaded {count_primary} primary identifiers mapped from {count_secondary} secondary identifiers from conflation file {conflationf.name}."
            )

    logger.info(f"Loaded all conflation files, found {len(conflation_index):,} identifiers in total.")

    # Step 1.1. What if we have synonyms connected with identifiers that are not primary identifiers? To solve that
    # problem, we further enrich these identifiers with information from the compendia files: every member of a
    # clique the conflation file names joins that clique's group. That way, if someone refers to
    # PUBCHEM.COMPOUND:962 when the preferred ID is CHEBI:15377, we will pull in synonyms from CHEBI:15377 as well.
    #
    # A clique joins a group only through an ID the conflation file lists. The members it adds go into
    # `member_index`, not `conflation_index`, until every compendium has been read: otherwise a clique that merely
    # shares a CURIE with a conflated clique would be pulled into its group too, but only if it came later in the
    # compendia, and step 3 (which expands only listed IDs) would never reach its records.
    #
    # Listed ID -> the identifier lists of the cliques it belongs to. Only the identifiers are kept, not the parsed
    # clique: step 3 reads nothing else, and labels and descriptions would just hold memory.
    cliques_with_conflations = defaultdict(list)
    member_index = dict()
    # Leader of each clique that two groups claim -> those groups' primary IDs.
    split_cliques = dict()
    count_conflated_cliques = 0

    for compendium_filename in compendia_files:
        logger.info(f"Reading compendium file {compendium_filename}")
        with open(compendium_filename) as compendiumf:
            for line in compendiumf:
                clique = json.loads(line)
                # A list, not a map(): it is iterated more than once below, and a one-shot iterator would leave the
                # later passes only what the first one hadn't consumed, dropping the ID the conflation names (#989).
                ids = [i["i"] for i in clique.get("identifiers", [])]

                # Is this clique being conflated? If not, we can just ignore it.
                listed_ids = [i for i in ids if i in conflation_index]
                if not listed_ids:
                    continue

                # The group(s) claiming this clique: through the IDs the conflation file lists, and through members
                # an earlier clique already gave to a group (a CURIE in two cliques).
                groups = {conflation_index[i] for i in listed_ids}
                groups.update(member_index[i] for i in ids if i in member_index)
                if len(groups) > 1:
                    split_cliques[ids[0]] = sorted(groups)
                    continue
                (group,) = groups

                count_conflated_cliques += 1
                for listed_id in listed_ids:
                    cliques_with_conflations[listed_id].append(ids)
                for id in ids:
                    if id not in conflation_index:
                        member_index[id] = group

    # The synonym records of a clique two groups claim would be split between the two conflated records, so neither
    # record would describe the whole clique. That is a fault in the conflation file (or a CURIE in two cliques), so
    # stop here -- minutes into the rule, not hours -- and name every such clique.
    if split_cliques:
        examples = "; ".join(f"{leader} in {groups}" for leader, groups in list(split_cliques.items())[:20])
        raise RuntimeError(
            f"{len(split_cliques):,} cliques are claimed by more than one conflation group, so their synonym records "
            f"would be split between conflated records. First {min(len(split_cliques), 20)}: {examples}"
        )

    conflation_index.update(member_index)
    logger.info(f"Added {len(member_index):,} IDs from {count_conflated_cliques:,} cliques involved in conflation.")
    del member_index

    logger.info(f"Writing output to {output_gz}.")
    with gzip.open(output_gz, "wt", encoding="utf8") as outputf:
        # Step 2. Conflate the synonyms.
        synonyms_to_conflate = defaultdict(lambda: defaultdict(list))
        for synonym_filename_gz in synonym_files_gz:
            logger.info(f"Reading synonym file {synonym_filename_gz}")
            with gzip.open(synonym_filename_gz, "rt", encoding="utf-8") as synonymsf:
                for synonym_text in synonymsf:
                    synonym = json.loads(synonym_text)

                    # Do we need to conflate this synonym at all?
                    curie = synonym["curie"]
                    if curie not in conflation_index:
                        # No known conflation. We can just write it out.
                        print(json.dumps(synonym), file=outputf)
                        logger.debug("Ignoring synonym %s, no known conflation.", curie)
                    else:
                        # We need to conflate this. Add this to the synonyms_to_conflate list.
                        preferred_id = conflation_index[curie]
                        if curie in synonyms_to_conflate[preferred_id]:
                            logger.warning(
                                f"Duplicate CURIE in conflation: {curie} appears multiple times in {preferred_id}"
                            )
                        synonyms_to_conflate[preferred_id][curie].append(synonym)

        logger.info(f"Identified {len(synonyms_to_conflate)} conflated cliques that need to be synonymized.")

        # Step 3. Conflate any synonyms that need conflating.
        for curie in synonyms_to_conflate:
            synonyms_by_curie = synonyms_to_conflate[curie]

            # We conflate synonyms in this way:
            # 1. We traverse the list in the order of identifiers in the original conflation.
            # 2. We concatenate types onto the end of subsequent conflation types, i.e. we begin with
            #    all the types of the lead clique, and then add the types of subsequent cliques.
            conflation_order = conflations[curie]

            final_conflation = dict()

            names_included = set()
            types_included = set()
            types_to_ignore = set("OntologyClass")
            # Expand each conflation ID to every member of its clique, in conflation order. Two conflation IDs can
            # reach the same member (e.g. both are in one clique), so each member is listed once; otherwise its
            # record would be merged, and its identifier count summed, twice.
            merge_order = []
            conflation_ids_seen = set()
            for conflation_id_not_normalized in conflation_order:
                # .get(), not [], so an ID in no compendium clique doesn't grow the defaultdict.
                cliques = cliques_with_conflations.get(conflation_id_not_normalized) or [[conflation_id_not_normalized]]
                logger.debug("Expanded %s into %s.", conflation_id_not_normalized, cliques)
                for ids in cliques:
                    # A synonym file has one record per clique, keyed on its leader. Records under two of a clique's
                    # identifiers would both be merged, counting its identifiers twice; that should never happen.
                    keyed = [i for i in ids if i in synonyms_by_curie and i not in conflation_ids_seen]
                    if len(keyed) > 1:
                        logger.warning(
                            "Clique %s has synonym records under %d of its identifiers (%s); merging all of them "
                            "counts its identifiers %d times.",
                            ids[0],
                            len(keyed),
                            keyed,
                            len(keyed),
                        )
                    for conflation_id in ids:
                        if conflation_id not in conflation_ids_seen:
                            conflation_ids_seen.add(conflation_id)
                            merge_order.append(conflation_id)

            # Merge last, rather than drop, any record of this group that the expansion didn't reach, e.g. one keyed
            # on an ID from an earlier conflation line with the same primary ID (`conflations` keeps only the last).
            unreached = [c for c in synonyms_by_curie if c not in conflation_ids_seen]
            if unreached:
                logger.warning("Conflation %s does not reach %s; merging them after its own members.", curie, unreached)
                merge_order.extend(unreached)

            for conflation_id in merge_order:
                # .get(), not [], so a clique member with no synonym record doesn't grow the defaultdict.
                for synonym in synonyms_by_curie.get(conflation_id, ()):
                    if "curie" not in final_conflation:
                        final_conflation["curie"] = synonym["curie"]

                    if "preferred_name" not in final_conflation and "preferred_name" in synonym:
                        final_conflation["preferred_name"] = synonym["preferred_name"]

                    if "names" not in final_conflation:
                        final_conflation["names"] = list()

                    for name in synonym["names"]:
                        # Don't repeat names that are already in the final conflation.
                        if name not in names_included:
                            final_conflation["names"].append(name)
                            names_included.add(name)

                    if "types" not in final_conflation:
                        final_conflation["types"] = list()

                    for typ in synonym["types"]:
                        # Ignore types to be ignored.
                        if typ in types_to_ignore:
                            continue

                        # Don't repeat types that are already in the final conflation.
                        if typ not in types_included:
                            final_conflation["types"].append(typ)
                            types_included.add(typ)

                    # Handle shortest_name_length.
                    if "shortest_name_length" in synonym:
                        # If we don't have a shortest_name_length in final_conflation OR if
                        # it is smaller than synonym['shortest_name_length'], use that instead.
                        if (
                            "shortest_name_length" not in final_conflation
                            or synonym["shortest_name_length"] < final_conflation["shortest_name_length"]
                        ):
                            final_conflation["shortest_name_length"] = synonym["shortest_name_length"]

                    # Handle clique_identifier_count.
                    if "clique_identifier_count" in synonym:
                        if "clique_identifier_count" not in final_conflation:
                            # If we don't have a clique_identifier_count in final_conflation, set it to zero.
                            final_conflation["clique_identifier_count"] = 0

                        # If we do have a clique_identifier_count in final_conflation, add the count from this synonym.
                        final_conflation["clique_identifier_count"] += synonym["clique_identifier_count"]

                    # Handle taxa.
                    if "taxa" in synonym:
                        if "taxa" not in final_conflation:
                            final_conflation["taxa"] = set()
                        final_conflation["taxa"].update(synonym["taxa"])

            # Convert the taxa into a list.
            final_conflation["taxa"] = sorted(final_conflation["taxa"], key=get_numerical_curie_suffix)
            if len(final_conflation["taxa"]) > 0:
                final_conflation["taxon_specific"] = True
            else:
                final_conflation["taxon_specific"] = False

            # Checks
            if "curie" not in final_conflation:
                logger.warning(
                    f"Conflated synonym entry missing CURIE entirely! Using primary CURIE {curie} for: "
                    + f"{final_conflation}"
                )
                final_conflation["curie"] = curie

            if final_conflation["curie"] != curie:
                logger.warning(
                    f"Synonym entry {curie} has a different CURIE from {final_conflation['curie']}, is "
                    + f"the conflation file not normalized? {final_conflation}"
                )
                logger.warning(
                    f"CURIE {curie} will be used instead of the actual normalized CURIE, {final_conflation['curie']}, "
                    "in order to be consistent with conflation file."
                )
                final_conflation["curie"] = curie

            # Recalculate the CURIE suffix.
            curie_suffix = get_numerical_curie_suffix(final_conflation["curie"])
            if curie_suffix:
                final_conflation["curie_suffix"] = curie_suffix

            # Write it out.
            print(json.dumps(final_conflation), file=outputf)


if __name__ == "__main__":
    conflate_synonyms()
