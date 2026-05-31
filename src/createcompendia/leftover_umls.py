import json

from src.babel_utils import TypedClique, write_compendium
from src.categories import (
    ACTIVITY,
    AGENT,
    DEVICE,
    DRUG,
    FOOD,
    NAMED_THING,
    PHYSICAL_ENTITY,
    PROCEDURE,
    PUBLICATION,
    SMALL_MOLECULE,
)
from src.datahandlers import umls
from src.prefixes import UMLS
from src.util import get_biolink_model_toolkit, get_logger

logger = get_logger(__name__)

def write_leftover_umls(metadata_yamls, compendia, mrconso, mrsty,
                        umls_compendium, umls_synonyms, report, biolink_version, icrdf_filename):
    """
    Search for "leftover" UMLS concepts, i.e. those that are defined and valid in MRCONSO but are not
    mapped to a concept in Babel.

    As described in https://github.com/NCATSTranslator/NodeNormalization/issues/119#issuecomment-1154751451

    :param metadata_yamls: A list of metadata YAML files that led to this compendium.
    :param compendia: A list of compendia to collect.
    :param mrconso: MRCONSO.RRF file path
    :param mrsty: MRSTY.RRF file path
    :param umls_compendium: The UMLS compendium file to write out.
    :param umls_synonyms: The synonyms file to generate for this compendium.
    :param report: The report file to write out.
    :param biolink_version: The Biolink Model version to use.
    :param icrdf_filename: The information content file used by write_compendium().
    :return: Nothing.
    """

    logger.info(
        f"write_leftover_umls({metadata_yamls}, {compendia}, {mrconso}, {mrsty}, {umls_compendium}, {umls_synonyms}, {report}, {biolink_version}, {icrdf_filename})"
    )

    # For now, we have many more UMLS entities in MRCONSO than in the compendia, so
    # we'll make an in-memory list of those first. Once that flips, this should be
    # switched to the other way around (or perhaps written into an in-memory database
    # of some sort).
    umls_ids_in_other_compendia = set()

    # If we were interested in keeping all UMLS labels, we would create an identifier file as described in
    # babel_utils.read_identifier_file() and then glom them with babel_utils.glom(). However, for this initial
    # run, it's probably okay to just pick the first label for each code.
    umls_ids_in_this_compendium = set()

    with open(report, "w") as reportf:
        # This defaults to the version of the Biolink model that is included with this BMT.
        biolink_toolkit = get_biolink_model_toolkit(biolink_version)

        for compendium in compendia:
            logger.info(f"Starting compendium: {compendium}")
            umls_ids = set()

            with open(compendium) as f:
                for row in f:
                    cluster = json.loads(row)
                    for id in cluster["identifiers"]:
                        if id["i"].startswith(UMLS + ":"):
                            umls_ids.add(id["i"])

            logger.info(f"Completed compendium {compendium} with {len(umls_ids)} UMLS IDs")
            umls_ids_in_other_compendia.update(umls_ids)

        logger.info(f"Completed all compendia with {len(umls_ids_in_other_compendia)} UMLS IDs.")
        reportf.write(f"Completed all compendia with {len(umls_ids_in_other_compendia)} UMLS IDs.\n")
        # print(umls_ids_in_other_compendia)

        # Load all the semantic types.
        preferred_name_by_id = dict()
        types_by_id = dict()
        types_by_tui = dict()
        with open(mrsty) as inf:
            for line in inf:
                x = line.strip().split("|")
                umls_id = f"{UMLS}:{x[0]}"
                tui = x[1]
                # stn = x[2]
                sty = x[3]

                if umls_id not in types_by_id:
                    types_by_id[umls_id] = dict()
                if tui not in types_by_id[umls_id]:
                    types_by_id[umls_id][tui] = set()
                types_by_id[umls_id][tui].add(sty)

                if tui not in types_by_tui:
                    types_by_tui[tui] = set()
                types_by_tui[tui].add(sty)

        logger.info(f"Completed loading {len(types_by_id.keys())} UMLS IDs from MRSTY.RRF.")
        reportf.write(f"Completed loading {len(types_by_id.keys())} UMLS IDs from MRSTY.RRF.\n")

        with open("babel_outputs/reports/umls-types.tsv", "w") as outf:
            for tui in sorted(types_by_tui.keys()):
                for sty in sorted(list(types_by_tui[tui])):
                    outf.write(f"{tui}\t{sty}\n")

        # Create a compendium that consists solely of all MRCONSO entries that haven't been referenced.
        curies_no_umls_type = set()
        curies_multiple_umls_type = set()
        leftover_cliques = []
        with open(mrconso) as inf:
            for line in inf:
                if not umls.check_mrconso_line(line):
                    continue

                x = line.strip().split("|")
                cui = x[0]
                umls_id = f"{UMLS}:{cui}"
                if umls_id in umls_ids_in_other_compendia:
                    logger.debug(f"UMLS ID {umls_id} is in another compendium, skipping.")
                    continue
                if umls_id in umls_ids_in_this_compendium:
                    logger.debug(f"UMLS ID {umls_id} has already been included in this compendium, skipping.")
                    continue
                if umls_id in curies_no_umls_type or umls_id in curies_multiple_umls_type:
                    # This CURIE was already evaluated and skipped due to type resolution failure.
                    # Skip it here to avoid redundant type lookups on subsequent MRCONSO rows for the same CUI.
                    continue

                # The STR value should be the label.
                label = x[14]

                # Lookup type.
                def umls_type_to_biolink_type(umls_tui):
                    biolink_type = biolink_toolkit.get_element_by_mapping(f"STY:{umls_tui}", most_specific=True, formatted=True, mixin=True)
                    if biolink_type is None:
                        logger.debug(f"No Biolink type found for UMLS TUI {umls_tui}")
                    return biolink_type

                umls_type_results = types_by_id.get(umls_id, {NAMED_THING: {"Named thing"}})
                biolink_types = set(list(map(umls_type_to_biolink_type, umls_type_results.keys())))

                # How to deal with multiple Biolink types? We currently only have the following multiple
                # types, so we can resolve these manually:
                biolink_types_as_set = set(map(lambda t: "(None)" if t is None else t, list(biolink_types)))
                biolink_types_as_str = "|".join(sorted(list(biolink_types_as_set)))

                if None in biolink_types:
                    # One of the TUIs couldn't be converted; let's delete all of them so that we can report this.
                    biolink_types = list()

                # Some Biolink multiple types we handle manually.
                if biolink_types_as_set == {DEVICE, DRUG}:
                    biolink_types = [DRUG]
                elif biolink_types_as_set == {DRUG, SMALL_MOLECULE}:
                    biolink_types = [SMALL_MOLECULE]
                elif biolink_types_as_set == {AGENT, PHYSICAL_ENTITY}:
                    biolink_types = [AGENT]
                elif biolink_types_as_set == {PHYSICAL_ENTITY, PUBLICATION}:
                    biolink_types = [PUBLICATION]
                elif biolink_types_as_set == {ACTIVITY, PROCEDURE}:
                    biolink_types = [PROCEDURE]
                elif biolink_types_as_set == {DRUG, FOOD}:
                    biolink_types = [FOOD]

                if len(biolink_types) == 0:
                    # We skip this CURIE, but we don't want to print multiple log messages for the same CURIE.
                    if umls_id not in curies_no_umls_type:
                        curies_no_umls_type.add(umls_id)
                        logger.warning(f"No UMLS type found for {umls_id}: {umls_type_results} -> {biolink_types}, skipping")
                        reportf.write(f"NO_UMLS_TYPE [{umls_id}]: {umls_type_results} -> {biolink_types}\n")
                    continue
                if len(biolink_types) > 1:
                    # We skip this CURIE, but we don't want to print multiple log messages for the same CURIE.
                    if umls_id not in curies_multiple_umls_type:
                        curies_multiple_umls_type.add(umls_id)
                        logger.debug(f"Multiple UMLS types not yet supported for {umls_id}: {umls_type_results} -> {biolink_types}, skipping")
                        reportf.write(f"MULTIPLE_UMLS_TYPES [{umls_id}]\t{biolink_types_as_str}\t{umls_type_results} -> {biolink_types}\n")
                    continue
                biolink_type = list(biolink_types)[0]
                preferred_name_by_id[umls_id] = label

                # Let write_compendium() generate this singleton's compendium and synonym JSON.
                leftover_cliques.append(TypedClique(node_type=biolink_type, identifiers=[umls_id]))
                umls_ids_in_this_compendium.add(umls_id)

        logger.info(f"Wrote out {len(umls_ids_in_this_compendium)} UMLS IDs into the leftover UMLS compendium.")
        reportf.write(f"Wrote out {len(umls_ids_in_this_compendium)} UMLS IDs into the leftover UMLS compendium.\n")

        logger.info(f"Found {len(curies_no_umls_type)} UMLS IDs without UMLS types and {len(curies_multiple_umls_type)} UMLS IDs with multiple UMLS types.")
        reportf.write(f"Found {len(curies_no_umls_type)} UMLS IDs without UMLS types and {len(curies_multiple_umls_type)} UMLS IDs with multiple UMLS types.\n")

        logger.info(f"Writing {len(leftover_cliques)} leftover UMLS cliques with write_compendium().")
        reportf.write(f"Writing {len(leftover_cliques)} leftover UMLS cliques with write_compendium().\n")

    write_compendium(metadata_yamls, leftover_cliques, "umls.txt", None, labels=preferred_name_by_id, extra_prefixes=[UMLS],
                     icrdf_filename=icrdf_filename)

    logger.info(f"Wrote leftover UMLS outputs: {umls_compendium}, {umls_synonyms}, metadata/umls.yaml.")
