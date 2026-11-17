"""
Conflate synonym files: merge the synonym records of cliques that a conflation file (GeneProtein.txt,
DrugChemical.txt) says are the same thing into one record per conflated group. Called by the
`geneprotein_conflated_synonyms` and `drugchemical_conflated_synonyms` rules.
"""

import gzip
import json
from collections import defaultdict

from src import util
from src.babel_utils import get_numerical_curie_suffix

logger = util.get_logger(__name__)


def conflate_synonyms(synonym_files_gz, compendia_files, conflation_file, output_gz):
    """
    Write a synonym file in which the records of every conflated group are merged into one.

    Each conflation line (`["primary", "secondary", ...]`) is a group. A group claims the synonym records keyed on any
    member of a compendium clique that one of its listed IDs belongs to, not only those keyed on the listed IDs, so a
    record keyed on a clique member the conflation file doesn't name is still merged (#989). A clique the conflation
    file never names is left alone even if it shares a CURIE with a conflated one. Records no group claims are written
    out unchanged; each group's records are merged by merge_conflated_group(), which describes the merge.

    Two conflation lines with the same primary ID form one group, their IDs taken in file order.

    :param synonym_files_gz: The input synonym files (gzipped JSONL).
    :param compendia_files: The compendia (JSONL) whose cliques expand each conflation ID to its clique's members.
    :param conflation_file: The conflation files to apply (JSONL, one list of IDs per line).
    :param output_gz: The gzipped synonym file to write.
    :raises RuntimeError: If two groups claim one clique -- its members are listed in two conflation lines, or it
        shares a CURIE with a conflated clique of another group -- since its records would be split between them.
    """

    logger.info(f"conflate_synonyms({synonym_files_gz}, {compendia_files}, {conflation_file}, {output_gz})")

    # Some common code to manage the conflation index.
    # This is simply a large dictionary, where every key is an identifier and the value is the identifier to map it to.
    conflation_index = dict()

    # This is a map of primary IDs to the list of conflation IDs. This allows us to conflate terms in the correct order.
    # Two lines with the same primary ID are concatenated in file order, so step 3 reaches the IDs of both.
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
                        f"Two conflations have the same primary ID: {conflation} and {conflations[conflation[0]]}; "
                        "merging both, in file order."
                    )
                conflations[conflation[0]].extend(conflation)
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
    # stop here -- minutes into the rule, not hours -- and name every such clique. No such clique occurs in the 2026jul22
    # build: docs/conflation/split-cliques/README.md.
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
                                "Duplicate CURIE in conflation: %s appears multiple times in %s; its identifiers "
                                "are counted once.",
                                curie,
                                preferred_id,
                            )
                        synonyms_to_conflate[preferred_id][curie].append(synonym)

        logger.info(f"Identified {len(synonyms_to_conflate)} conflated cliques that need to be synonymized.")

        # Step 3. Conflate any synonyms that need conflating.
        for curie, synonyms_by_curie in synonyms_to_conflate.items():
            final_conflation = merge_conflated_group(
                curie, conflations[curie], synonyms_by_curie, cliques_with_conflations
            )
            print(json.dumps(final_conflation), file=outputf)


def merge_conflated_group(primary_id, conflation_order, synonyms_by_curie, cliques_with_conflations):
    """
    Merge the synonym records of one conflated group into a single record, keyed on the group's primary ID.

    The records are visited one clique at a time, in conflation order: each ID in `conflation_order` is expanded to
    every member of its compendium clique (an ID in no clique stands for itself), and a member already reached through
    an earlier ID is skipped. Names and types are concatenated in that order without repeats, so the lead clique's
    come first; the preferred name is the first one found, the shortest name length the minimum, and taxa the union.

    `clique_identifier_count` is added once per *clique*, not once per record. A synonym file holds one record per
    clique, keyed on its leader, but a clique can have records under two of its identifiers (or the same CURIE in two
    synonym files); adding each record's count would count the clique's identifiers twice. The clique contributes the
    largest count any of its records gives.

    :param primary_id: The group's primary ID (the first ID of its conflation line); the merged record's CURIE.
    :param conflation_order: The group's conflation IDs, in conflation-file order.
    :param synonyms_by_curie: CURIE -> the synonym records keyed on it, for every record step 2 gave this group.
    :param cliques_with_conflations: Listed conflation ID -> the identifier lists of the cliques it belongs to.
    :return: The merged synonym record.
    :raises RuntimeError: If a record of this group is not reached by expanding `conflation_order`. Step 1.1 only
        gives a group the members of cliques its listed IDs belong to, so this means the two steps disagree.
    """
    # BUG: set("OntologyClass") is the set of the string's letters, so this filter has never matched a type and every
    # conflated record keeps OntologyClass. #1179 (stacked on #1176) makes it {"OntologyClass"}.
    types_to_ignore = set("OntologyClass")

    preferred_name = None
    names = []
    names_included = set()
    types = []
    types_included = set()
    shortest_name_length = None
    clique_identifier_count = None
    taxa = set()
    first_curie = None

    members_seen = set()
    for conflation_id in conflation_order:
        # .get(), not [], so an ID in no compendium clique doesn't grow the defaultdict.
        for clique_ids in cliques_with_conflations.get(conflation_id) or [[conflation_id]]:
            members = [i for i in clique_ids if i not in members_seen]
            members_seen.update(members)
            records = [record for member in members for record in synonyms_by_curie.get(member, ())]
            if not records:
                continue

            counts = [record["clique_identifier_count"] for record in records if "clique_identifier_count" in record]
            if counts:
                clique_identifier_count = (clique_identifier_count or 0) + max(counts)

            for record in records:
                if first_curie is None:
                    first_curie = record["curie"]
                if preferred_name is None:
                    preferred_name = record.get("preferred_name")
                # Sets alongside the lists: a gene/protein group can carry thousands of names.
                for name in record["names"]:
                    if name not in names_included:
                        names.append(name)
                        names_included.add(name)
                for typ in record["types"]:
                    if typ not in types_included and typ not in types_to_ignore:
                        types.append(typ)
                        types_included.add(typ)
                if "shortest_name_length" in record and (
                    shortest_name_length is None or record["shortest_name_length"] < shortest_name_length
                ):
                    shortest_name_length = record["shortest_name_length"]
                taxa.update(record.get("taxa", ()))

    unreached = sorted(set(synonyms_by_curie) - members_seen)
    if unreached:
        raise RuntimeError(f"Conflation {primary_id} does not reach its synonym records under {unreached}.")

    if first_curie != primary_id:
        logger.warning(
            "Conflation %s has no synonym record of its own; its first is %s. Is the conflation file not normalized? "
            "Using %s, to be consistent with the conflation file.",
            primary_id,
            first_curie,
            primary_id,
        )

    # Keys in the order the merge used to add them, so output stays comparable with earlier builds line by line.
    final_conflation = {"curie": primary_id}
    if preferred_name is not None:
        final_conflation["preferred_name"] = preferred_name
    final_conflation["names"] = names
    final_conflation["types"] = types
    if shortest_name_length is not None:
        final_conflation["shortest_name_length"] = shortest_name_length
    if clique_identifier_count is not None:
        final_conflation["clique_identifier_count"] = clique_identifier_count
    final_conflation["taxa"] = sorted(taxa, key=get_numerical_curie_suffix)
    final_conflation["taxon_specific"] = len(taxa) > 0
    curie_suffix = get_numerical_curie_suffix(primary_id)
    if curie_suffix:
        final_conflation["curie_suffix"] = curie_suffix
    return final_conflation
