import csv
import json
from collections import defaultdict
from pathlib import Path

from src.babel_utils import TypedClique, write_compendium
from src.categories import (
    ACTIVITY,
    AGENT,
    BIOLOGICAL_PROCESS,
    CHEMICAL_ENTITY,
    CLINICAL_FINDING,
    CLINICAL_INTERVENTION,
    DEVICE,
    DRUG,
    FOOD,
    GROSS_ANATOMICAL_STRUCTURE,
    NAMED_THING,
    PHENOMENON,
    PHYSICAL_ENTITY,
    PROCEDURE,
    PUBLICATION,
    SMALL_MOLECULE,
)
from src.datahandlers import umls
from src.prefixes import UMLS
from src.util import get_biolink_model_toolkit, get_logger

logger = get_logger(__name__)


# Manual overrides of the Biolink type that bmt assigns to a UMLS semantic type. bmt looks these up
# by the mapping ``STY:<code>`` (e.g. ``STY:T033``), so we key this table by that STY code -- which is
# technically the UMLS TUI, but "STY" is the namespace UMLS and bmt actually use. A value of None
# means "deliberately reject": a concept whose only remaining semantic type is this one is excluded
# from the leftover UMLS compendium.
#
# Each entry MUST cite the GitHub issue that motivates it. These overrides exist because the right
# fix is in the Biolink Model, but it is hard to predict how a Biolink change lands in real Babel
# data. The companion test tests/createcompendia/test_leftover_umls.py records the *current* Biolink
# mapping for each code, so we are alerted when an override drifts (Biolink changed underneath us) or
# has become redundant (Biolink now agrees with the override and it can be removed). See
# docs/sources/UMLS/Leftover.md.
STY_OVERRIDES: dict[str, str | None] = {
    # https://github.com/NCATSTranslator/Babel/issues/569
    # "Finding" is too broad to be a PhenotypicFeature; treat it as a Phenomenon.
    "T033": PHENOMENON,
    # https://github.com/NCATSTranslator/Babel/issues/569
    # "Laboratory or Test Result" is a clinical finding, not a generic Phenomenon.
    "T034": CLINICAL_FINDING,
    # https://github.com/NCATSTranslator/Babel/issues/90
    # "Health Care Activity" (e.g. Hospitalization) is better modeled as a clinical intervention
    # than the generic biolink:Activity that bmt assigns. See biolink/biolink-model#1156.
    "T058": CLINICAL_INTERVENTION,
    # https://github.com/NCATSTranslator/Babel/issues/421
    # bmt has no STY mapping for these semantic types, so the concepts were being dropped as
    # unmapped. The overrides below keep them, typed as proposed in the issue. See the linked
    # biolink-model issues in each case.
    # "Genetic Function" -> biolink:BiologicalProcess (biolink/biolink-model#1601).
    "T045": BIOLOGICAL_PROCESS,
    # "Fully Formed Anatomical Structure" -> biolink:GrossAnatomicalStructure (biolink/biolink-model#1602).
    "T021": GROSS_ANATOMICAL_STRUCTURE,
    # "Chemical Viewed Functionally" -> biolink:ChemicalEntity (biolink/biolink-model#1600).
    "T120": CHEMICAL_ENTITY,
    # "Biomedical or Dental Material" -> biolink:ChemicalEntity (biolink/biolink-model#1599).
    "T122": CHEMICAL_ENTITY,
    # "Food" -> biolink:Food (biolink/biolink-model#1598).
    "T168": FOOD,
}

# Disambiguation applied when a single UMLS concept resolves to more than one Biolink type (because
# it carries multiple semantic types). Keyed by the frozenset of resolved Biolink types; the value is
# the single type to keep. Migrated from the inline if-chain that previously lived in
# write_leftover_umls().
TYPE_COMBO_OVERRIDES: dict[frozenset[str], str] = {
    frozenset({DEVICE, DRUG}): DRUG,
    frozenset({DRUG, SMALL_MOLECULE}): SMALL_MOLECULE,
    frozenset({AGENT, PHYSICAL_ENTITY}): AGENT,
    frozenset({PHYSICAL_ENTITY, PUBLICATION}): PUBLICATION,
    frozenset({ACTIVITY, PROCEDURE}): PROCEDURE,
    frozenset({DRUG, FOOD}): FOOD,
    # https://github.com/NCATSTranslator/Babel/issues/569
    # A concept typed both T033 "Finding" (-> Phenomenon) and its more specific child T034
    # "Laboratory or Test Result" (-> ClinicalFinding) keeps the more specific ClinicalFinding.
    # Without this, such concepts -- now routed to leftover after being excluded from
    # diseasephenotype.py -- would resolve to two types and be dropped.
    frozenset({PHENOMENON, CLINICAL_FINDING}): CLINICAL_FINDING,
}


def tui_to_biolink_type(umls_tui: str, toolkit=None, biolink_version: str | None = None) -> str | None:
    """
    Convert a UMLS TUI (Type Unique Identifier) to a Biolink Model type string.

    This is a thin wrapper over the Biolink Model Toolkit's ``STY:<TUI>`` mapping. It does NOT apply
    the manual ``STY_OVERRIDES``: it returns exactly what Biolink says, so the test can compare the
    overrides against the unmodified Biolink answer.

    Exactly one of ``toolkit`` or ``biolink_version`` must be supplied. Pass a pre-built
    ``toolkit`` when one is already available (avoids a redundant network fetch); pass
    ``biolink_version`` for standalone use.

    :param umls_tui: The UMLS TUI to look up (e.g. ``"T047"``).
    :param toolkit: A BMT Toolkit instance.  Ignored when ``biolink_version`` is given.
    :param biolink_version: Biolink Model version string (e.g. ``"4.3.6"``), used to build
        a toolkit when ``toolkit`` is not provided.
    :return: A formatted Biolink type string (e.g. ``"biolink:Disease"``), or ``None`` if
        no mapping exists for the TUI.
    :raises ValueError: If neither ``toolkit`` nor ``biolink_version`` is provided.
    """
    if toolkit is None:
        if biolink_version is None:
            raise ValueError("Either toolkit or biolink_version must be provided.")
        toolkit = get_biolink_model_toolkit(biolink_version)
    result = toolkit.get_element_by_mapping(f"STY:{umls_tui}", most_specific=True, formatted=True, mixin=True)
    if result is None:
        logger.debug(f"No Biolink type found for UMLS TUI {umls_tui}")
    return result


def _format_samples(pairs, limit=5):
    """Render up to ``limit`` ``(curie, label)`` pairs as a single ``CURIE=label; ...`` string."""
    return "; ".join(f"{curie}={label}" for curie, label in pairs[:limit])


def write_leftover_umls(metadata_yamls, compendia, mrconso, mrsty, umls_compendium, umls_synonyms, report, biolink_version, icrdf_filename):
    """
    Search for "leftover" UMLS concepts, i.e. those that are defined and valid in MRCONSO but are not
    mapped to a concept in Babel.

    As described in https://github.com/NCATSTranslator/NodeNormalization/issues/119#issuecomment-1154751451

    The Biolink type for each leftover concept comes from its UMLS semantic type(s) via
    tui_to_biolink_type(), corrected by the manual STY_OVERRIDES / TYPE_COMBO_OVERRIDES tables at the
    top of this module. A machine-readable coverage report is written under
    ``<reports>/umls/`` (see docs/sources/UMLS/Leftover.md).

    :param metadata_yamls: A list of metadata YAML files that led to this compendium.
    :param compendia: A list of compendia to collect.
    :param mrconso: MRCONSO.RRF file path
    :param mrsty: MRSTY.RRF file path
    :param umls_compendium: The UMLS compendium file to write out.
    :param umls_synonyms: The synonyms file to generate for this compendium.
    :param report: The report file to write out. The coverage CSVs are written to a ``umls/``
        subdirectory alongside it.
    :param biolink_version: The Biolink Model version to use.
    :param icrdf_filename: The information content file used by write_compendium().
    :return: Nothing.
    """

    logger.info(
        f"write_leftover_umls({metadata_yamls}, {compendia}, {mrconso}, {mrsty}, {umls_compendium}, {umls_synonyms}, {report}, {biolink_version}, {icrdf_filename})"
    )

    # The coverage CSVs go into a umls/ subdirectory next to the text report (e.g.
    # babel_outputs/reports/umls/), so we can add further UMLS reports there over time.
    report_dir = Path(report).parent / "umls"
    report_dir.mkdir(parents=True, exist_ok=True)

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

        # Per-compendium UMLS coverage: how many UMLS CURIEs each input compendium contributes, and
        # how many of those sit in a clique consisting solely of a single UMLS identifier.
        compendium_umls_counts = []

        for compendium in compendia:
            logger.info(f"Starting compendium: {compendium}")
            umls_ids = set()
            single_umls_clique_count = 0

            with open(compendium) as f:
                for row in f:
                    cluster = json.loads(row)
                    identifiers = cluster["identifiers"]
                    umls_in_clique = [identifier["i"] for identifier in identifiers if identifier["i"].startswith(UMLS + ":")]
                    umls_ids.update(umls_in_clique)
                    if len(identifiers) == 1 and len(umls_in_clique) == 1:
                        single_umls_clique_count += 1

            logger.info(f"Completed compendium {compendium} with {len(umls_ids)} UMLS IDs")
            compendium_umls_counts.append((Path(compendium).name, len(umls_ids), single_umls_clique_count))
            umls_ids_in_other_compendia.update(umls_ids)

        logger.info(f"Completed all compendia with {len(umls_ids_in_other_compendia)} UMLS IDs.")
        reportf.write(f"Completed all compendia with {len(umls_ids_in_other_compendia)} UMLS IDs.\n")

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

        with open(report_dir / "tui-sty.tsv", "w") as outf:
            for tui in sorted(types_by_tui.keys()):
                for sty in sorted(list(types_by_tui[tui])):
                    outf.write(f"{tui}\t{sty}\n")

        # Resolve a UMLS semantic type (STY/TUI) to a Biolink type via Biolink, memoizing because the
        # same TUI recurs across many concepts. STY_OVERRIDES is applied separately (see below) so
        # this cache always reflects the raw Biolink answer.
        sty_biolink_cache: dict[str, str | None] = {}

        def resolve_sty_biolink(umls_tui: str) -> str | None:
            if umls_tui not in sty_biolink_cache:
                sty_biolink_cache[umls_tui] = tui_to_biolink_type(umls_tui, toolkit=biolink_toolkit)
            return sty_biolink_cache[umls_tui]

        # Create a compendium that consists solely of all MRCONSO entries that haven't been referenced.
        curies_no_umls_type = set()
        curies_multiple_umls_type = set()
        curies_rejected = set()

        # Leftover UMLS entries that are not referenced by any other compendia. Each will be a TypedClique that
        # consists of a single UMLS identifier and the appropriate Biolink type. This allows us to override Biolink types
        # if needed.
        leftover_umls_cliques: list[TypedClique] = []

        # Report accumulators: (CURIE, label) samples keyed by Biolink type / unmapped TUI / rejected TUI.
        type_samples: dict[str, list] = defaultdict(list)
        unmapped_tui_examples: dict[str, list] = defaultdict(list)
        rejected_tui_examples: dict[str, list] = defaultdict(list)

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
                if umls_id in curies_no_umls_type or umls_id in curies_multiple_umls_type or umls_id in curies_rejected:
                    # This CURIE was already evaluated and skipped due to type resolution failure.
                    # Skip it here to avoid redundant type lookups on subsequent MRCONSO rows for the same CUI.
                    continue

                # The STR value should be the label.
                label = x[14]

                # Resolve every semantic type (STY/TUI) on this concept into one of three outcomes:
                # a Biolink type, an explicit rejection (STY_OVERRIDES -> None), or unmapped (Biolink
                # has no mapping and there is no override).
                umls_type_results = types_by_id.get(umls_id, {NAMED_THING: {"Named thing"}})
                mapped_types = set()
                rejected_tuis = set()
                unmapped_tuis = set()
                for tui in umls_type_results.keys():
                    if tui in STY_OVERRIDES:
                        override = STY_OVERRIDES[tui]
                        if override is None:
                            rejected_tuis.add(tui)
                        else:
                            mapped_types.add(override)
                    else:
                        biolink_type = resolve_sty_biolink(tui)
                        if biolink_type is None:
                            unmapped_tuis.add(tui)
                        else:
                            mapped_types.add(biolink_type)

                # An unmapped semantic type means we can't fully type this concept, so we skip it
                # entirely (the existing conservative behavior) and report it as unmapped.
                if unmapped_tuis:
                    if umls_id not in curies_no_umls_type:
                        curies_no_umls_type.add(umls_id)
                        logger.warning(f"No Biolink type for {umls_id}: unmapped STY {sorted(unmapped_tuis)} in {umls_type_results}, skipping")
                        reportf.write(f"NO_UMLS_TYPE [{umls_id}]: unmapped STY {sorted(unmapped_tuis)} in {umls_type_results}\n")
                        for tui in unmapped_tuis:
                            unmapped_tui_examples[tui].append((umls_id, label))
                    continue

                # If every semantic type was deliberately rejected (or there were none), skip and
                # report as rejected -- distinct from "couldn't be mapped".
                if not mapped_types:
                    if umls_id not in curies_rejected:
                        curies_rejected.add(umls_id)
                        logger.debug(f"Rejected {umls_id}: rejected STY {sorted(rejected_tuis)} in {umls_type_results}, skipping")
                        reportf.write(f"REJECTED [{umls_id}]: rejected STY {sorted(rejected_tuis)} in {umls_type_results}\n")
                        for tui in rejected_tuis:
                            rejected_tui_examples[tui].append((umls_id, label))
                    continue

                # Disambiguate when a concept resolves to multiple Biolink types.
                biolink_types = mapped_types
                if len(biolink_types) > 1 and frozenset(biolink_types) in TYPE_COMBO_OVERRIDES:
                    biolink_types = {TYPE_COMBO_OVERRIDES[frozenset(biolink_types)]}

                if len(biolink_types) > 1:
                    # We skip this CURIE, but we don't want to print multiple log messages for the same CURIE.
                    if umls_id not in curies_multiple_umls_type:
                        curies_multiple_umls_type.add(umls_id)
                        biolink_types_as_str = "|".join(sorted(biolink_types))
                        logger.debug(f"Multiple Biolink types not yet supported for {umls_id}: {umls_type_results} -> {biolink_types_as_str}, skipping")
                        reportf.write(f"MULTIPLE_UMLS_TYPES [{umls_id}]\t{biolink_types_as_str}\t{umls_type_results}\n")
                    continue

                biolink_type = next(iter(biolink_types))
                preferred_name_by_id[umls_id] = label

                # Let write_compendium() generate this singleton's compendium and synonym JSON.
                leftover_umls_cliques.append(TypedClique(node_type=biolink_type, identifiers=[umls_id]))
                umls_ids_in_this_compendium.add(umls_id)
                type_samples[biolink_type].append((umls_id, label))

        logger.info(f"Wrote out {len(umls_ids_in_this_compendium)} UMLS IDs into the leftover UMLS compendium.")
        reportf.write(f"Wrote out {len(umls_ids_in_this_compendium)} UMLS IDs into the leftover UMLS compendium.\n")

        logger.info(
            f"Found {len(curies_no_umls_type)} UMLS IDs without a Biolink type, "
            f"{len(curies_rejected)} deliberately rejected, and {len(curies_multiple_umls_type)} with multiple Biolink types."
        )
        reportf.write(
            f"Found {len(curies_no_umls_type)} UMLS IDs without a Biolink type, "
            f"{len(curies_rejected)} deliberately rejected, and {len(curies_multiple_umls_type)} with multiple Biolink types.\n"
        )

        logger.info(f"Writing {len(leftover_umls_cliques)} leftover UMLS cliques with write_compendium().")
        reportf.write(f"Writing {len(leftover_umls_cliques)} leftover UMLS cliques with write_compendium().\n")

        # Per-compendium UMLS coverage.
        with open(report_dir / "compendium-coverage.csv", "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(["compendium", "total_umls_curies", "single_umls_clique_count"])
            for name, total, singles in sorted(compendium_umls_counts):
                writer.writerow([name, total, singles])

        # Per-Biolink-type leftover clique coverage, with a few sample CURIEs and labels.
        with open(report_dir / "types-coverage.csv", "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(["biolink_type", "leftover_clique_count", "sample_curies"])
            for biolink_type in sorted(type_samples.keys()):
                pairs = type_samples[biolink_type]
                writer.writerow([biolink_type, len(pairs), _format_samples(pairs)])

        # Semantic types we couldn't map or deliberately rejected, with affected CUI counts and samples.
        with open(report_dir / "unmapped-types.csv", "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(["tui", "sty_name", "status", "affected_cui_count", "sample_curies"])
            for status, examples in (("unmapped", unmapped_tui_examples), ("rejected", rejected_tui_examples)):
                for tui in sorted(examples.keys()):
                    pairs = examples[tui]
                    sty_name = "|".join(sorted(types_by_tui.get(tui, set())))
                    writer.writerow([tui, sty_name, status, len(pairs), _format_samples(pairs)])

    write_compendium(metadata_yamls, leftover_umls_cliques, "umls.txt", None, labels=preferred_name_by_id, extra_prefixes=[UMLS],
                     icrdf_filename=icrdf_filename)

    logger.info(f"Wrote leftover UMLS outputs: {umls_compendium}, {umls_synonyms}, metadata/umls.txt.yaml, and coverage CSVs in {report_dir}.")
