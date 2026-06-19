import csv
import json
from collections import defaultdict
from pathlib import Path

from src.babel_utils import TypedClique, reduce_to_most_specific_tree_codes, write_compendium
from src.categories import (
    ACTIVITY,
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
    POPULATION_OF_INDIVIDUAL_ORGANISMS,
    PROCEDURE,
    SMALL_MOLECULE,
)
from src.datahandlers import umls
from src.node import NodeFactory
from src.prefixes import UMLS
from src.util import get_biolink_model_toolkit, get_logger

logger = get_logger(__name__)

_UMLS_PREFIX = UMLS + ":"

# Up to this many (CURIE, label) samples are kept per report bucket -- enough to eyeball what a
# bucket contains without unbounded memory across millions of MRCONSO lines.
_SAMPLE_LIMIT = 5


# Manual overrides of the Biolink type that bmt assigns to a UMLS semantic type. bmt looks these up
# by the mapping ``STY:<code>`` (e.g. ``STY:T033``), so we key this table by that STY code -- which is
# technically the UMLS TUI, but "STY" is the namespace Biolink Model and bmt actually use. A value of None
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
    # https://github.com/NCATSTranslator/Babel/issues/817
    # "Occupation or Discipline", "Biomedical Occupation or Discipline", and "Professional or
    # Occupational Group" are all mapped to PopulationOfIndividualOrganisms as a placeholder until
    # the Biolink mapping is resolved. T090/T091 have no bmt mapping; T097 is overridden from
    # biolink:Cohort to the parent class for consistency across this cluster. This is imprecise but
    # lets these concepts normalise and carry labels rather than being dropped entirely.
    "T090": POPULATION_OF_INDIVIDUAL_ORGANISMS,
    "T091": POPULATION_OF_INDIVIDUAL_ORGANISMS,
    "T097": POPULATION_OF_INDIVIDUAL_ORGANISMS,
    # https://github.com/NCATSTranslator/Babel/issues/840
    # "Physical Object" (T072) and "Manufactured Object" (T073) both map to biolink:PhysicalEntity,
    # which has no id_prefixes in the Biolink Model. write_compendium() can nonetheless write these
    # because the leftover UMLS rule passes extra_prefixes=[UMLS] (see Change in node.create_node),
    # so we keep them typed as PhysicalEntity rather than dropping them. PhysicalEntity is listed in
    # GENERIC_TYPES below, so a concept that carries T072/T073 *alongside* a more specific semantic
    # type keeps the specific type instead of being dropped as multiply-typed.
    "T072": PHYSICAL_ENTITY,
    "T073": PHYSICAL_ENTITY,
}

# Very high-level Biolink types that should never shadow a more specific co-type. When a UMLS concept
# resolves to more than one Biolink type and one of them is generic (e.g. biolink:PhysicalEntity from
# T072/T073 "Physical Object"/"Manufactured Object"), the generic type is dropped so the specific
# type wins. This is the cleaner successor to the old approach of rejecting T072/T073 with None (which
# kept the specific type only by contributing no type at all, at the cost of dropping concepts whose
# *only* type was T072/T073). A concept typed solely as a generic type still keeps it and is written.
GENERIC_TYPES: frozenset[str] = frozenset({PHYSICAL_ENTITY})

# Disambiguation applied when a single UMLS concept resolves to more than one Biolink type (because
# it carries multiple semantic types). Keyed by the frozenset of resolved Biolink types; the value is
# the single type to keep. Migrated from the inline if-chain that previously lived in
# write_leftover_umls().
TYPE_COMBO_OVERRIDES: dict[frozenset[str], str] = {
    frozenset({DEVICE, DRUG}): DRUG,
    frozenset({DRUG, SMALL_MOLECULE}): SMALL_MOLECULE,
    frozenset({ACTIVITY, PROCEDURE}): PROCEDURE,
    frozenset({DRUG, FOOD}): FOOD,
    # https://github.com/NCATSTranslator/Babel/issues/569
    # A concept typed both T033 "Finding" (-> Phenomenon) and its more specific child T034
    # "Laboratory or Test Result" (-> ClinicalFinding) keeps the more specific ClinicalFinding.
    # Without this, such concepts -- now routed to leftover after being excluded from
    # diseasephenotype.py -- would resolve to two types and be dropped.
    frozenset({PHENOMENON, CLINICAL_FINDING}): CLINICAL_FINDING,
}


def apply_generic_demotion(biolink_types: set[str]) -> set[str]:
    """
    Drop GENERIC_TYPES from biolink_types when a more specific co-type is present; keep them when
    they are the only type. This is a pure function used both in write_leftover_umls() and in tests.
    """
    if len(biolink_types) > 1:
        specific_types = biolink_types - GENERIC_TYPES
        if specific_types:
            return specific_types
    return biolink_types


def writable_output_types() -> set[str]:
    """
    Every Biolink type the leftover UMLS rule can emit from its manual override tables: all non-None
    STY_OVERRIDES values, all TYPE_COMBO_OVERRIDES values, and NAMED_THING (the fallback type used
    when a concept has no MRSTY semantic type). Used by the preflight check in write_leftover_umls()
    and by the regression test to confirm each type is writable with extra_prefixes=[UMLS] -- some of
    them (e.g. biolink:Phenomenon, biolink:PhysicalEntity) have no id_prefixes of their own.

    The dynamic, Biolink-mapped TUIs are not enumerated here because they are made crash-proof by
    node.create_node() tolerating prefix-less types when extra_prefixes is supplied.
    """
    types = {t for t in STY_OVERRIDES.values() if t is not None}
    types.update(TYPE_COMBO_OVERRIDES.values())
    types.add(NAMED_THING)
    return types


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
        logger.warning(f"No Biolink type found for UMLS TUI {umls_tui}")
    return result


def _format_samples(pairs):
    """Render ``(curie, label)`` pairs as a single ``CURIE=label; ...`` string."""
    return "; ".join(f"{curie}={label}" for curie, label in pairs)


def summarize_compendium_umls_by_semantic_type(clusters, semantic_key, sample_limit=_SAMPLE_LIMIT):
    """Group one compendium's UMLS members by their most-specific UMLS semantic-type set.

    Each unique UMLS CURIE in the compendium is bucketed by ``semantic_key(curie)`` (a frozenset of
    the concept's most-specific TUIs). A CURIE is counted once even if it appears in several cliques;
    it counts toward ``single_umls_clique_count`` if it is ever seen in a clique whose only member is
    that single UMLS identifier.

    :param clusters: iterable of compendium clique dicts, each with an ``"identifiers"`` list of
        ``{"i": curie, "l": label, ...}`` entries.
    :param semantic_key: callable mapping a UMLS CURIE to a frozenset of TUIs.
    :param sample_limit: max ``(curie, label)`` samples kept per bucket.
    :return: ``(breakdown, umls_ids)`` where ``breakdown`` maps ``frozenset(TUIs)`` to
        ``[unique_curie_count, single_umls_clique_count, [(curie, label), ...]]`` and ``umls_ids`` is
        the set of every UMLS CURIE seen in this compendium.
    """
    umls_ids = set()
    single_umls_ids = set()
    labels_by_id = dict()
    for cluster in clusters:
        identifiers = cluster["identifiers"]
        umls_in_clique = [identifier["i"] for identifier in identifiers if identifier["i"].startswith(_UMLS_PREFIX)]
        umls_ids.update(umls_in_clique)
        for identifier in identifiers:
            if identifier["i"].startswith(_UMLS_PREFIX) and identifier["i"] not in labels_by_id:
                labels_by_id[identifier["i"]] = identifier.get("l", "")
        if len(identifiers) == 1 and len(umls_in_clique) == 1:
            single_umls_ids.add(umls_in_clique[0])

    breakdown = defaultdict(lambda: [0, 0, []])
    for umls_id in umls_ids:
        entry = breakdown[semantic_key(umls_id)]
        entry[0] += 1
        if umls_id in single_umls_ids:
            entry[1] += 1
        if len(entry[2]) < sample_limit:
            entry[2].append((umls_id, labels_by_id.get(umls_id, "")))
    return breakdown, umls_ids


def write_leftover_umls(
    metadata_yamls, compendia, mrconso, mrsty, umls_compendium, umls_synonyms, report, biolink_version, icrdf_filename
):
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
    :param report: The report file to write out (e.g. ``reports/umls/log.txt``). All other
        UMLS report CSVs are written into the same directory.
    :param biolink_version: The Biolink Model version to use.
    :param icrdf_filename: The information content file used by write_compendium().
    :return: Nothing.
    """

    logger.info(
        f"write_leftover_umls({metadata_yamls}, {compendia}, {mrconso}, {mrsty}, {umls_compendium}, {umls_synonyms}, {report}, {biolink_version}, {icrdf_filename})"
    )

    report_dir = Path(report).parent
    report_dir.mkdir(parents=True, exist_ok=True)

    # Preflight: confirm every Biolink type this rule can emit from its manual override tables can
    # actually be written with extra_prefixes=[UMLS], before we spend hours loading the compendia,
    # MRSTY and MRCONSO. create_node() with empty identifiers exercises get_prefixes() (the call that
    # historically crashed write_compendium after ~5h on a prefix-less type) and then returns None
    # without touching any labels or files. Fail fast here with a clear message instead.
    preflight_factory = NodeFactory(label_dir=None, biolink_version=biolink_version)
    output_types = writable_output_types()
    for output_type in sorted(output_types):
        try:
            preflight_factory.create_node(input_identifiers=[], node_type=output_type, labels={}, extra_prefixes=[UMLS])
        except RuntimeError as e:
            raise RuntimeError(
                f"leftover_umls preflight failed: Biolink type {output_type} is not writable even with "
                f"extra_prefixes=[UMLS] ({e}). Fix the override tables in leftover_umls.py before running the rule."
            ) from e
    logger.info(f"Preflight passed: all {len(output_types)} override output types are writable.")

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

        # Load all the semantic types first: the per-compendium coverage breakdown below needs to
        # look up each UMLS CURIE's semantic types, and the MRCONSO sweep needs them to type each
        # leftover concept. types_by_id maps each UMLS CURIE to {TUI: {STY name}}; types_by_tui maps
        # each TUI to its STY name(s); tui_to_tree maps each TUI to its semantic-type tree number
        # (MRSTY STN, e.g. T116 -> A1.4.1.2.1.7), used to reduce a concept's TUIs to the most
        # specific ones.
        preferred_name_by_id = dict()
        types_by_id = dict()
        types_by_tui = dict()
        tui_to_tree = dict()
        with open(mrsty) as inf:
            for line in inf:
                x = line.strip().split("|")
                umls_id = f"{UMLS}:{x[0]}"
                tui = x[1]
                tree = x[2]
                sty = x[3]

                if umls_id not in types_by_id:
                    types_by_id[umls_id] = dict()
                if tui not in types_by_id[umls_id]:
                    types_by_id[umls_id][tui] = set()
                types_by_id[umls_id][tui].add(sty)

                if tui not in types_by_tui:
                    types_by_tui[tui] = set()
                types_by_tui[tui].add(sty)

                # A TUI has a single, fixed tree number; record the first one we see.
                if tui not in tui_to_tree:
                    tui_to_tree[tui] = tree

        logger.info(f"Completed loading {len(types_by_id.keys())} UMLS IDs from MRSTY.RRF.")
        reportf.write(f"COMPLETED Loading {len(types_by_id.keys())} UMLS IDs from MRSTY.RRF.\n")

        with open(report_dir / "tui-sty.tsv", "w") as outf:
            for tui in sorted(types_by_tui.keys()):
                for sty in sorted(list(types_by_tui[tui])):
                    outf.write(f"{tui}\t{sty}\n")

        def semantic_key(umls_id: str) -> frozenset:
            """The most-specific set of UMLS semantic types (TUIs) for a UMLS CURIE.

            Looks up every TUI on the concept and drops any that is a proper ancestor of another
            TUI on the same concept (via tree-number prefixing), so co-types in the same lineage
            collapse to the leaf. Returns an empty frozenset if the CURIE has no MRSTY entry.
            """
            tuis = set(types_by_id.get(umls_id, {}).keys())
            return frozenset(reduce_to_most_specific_tree_codes(tuis, tui_to_tree))

        # Per-compendium UMLS coverage, broken down by most-specific semantic-type set. The key is
        # (compendium name, frozenset of TUIs); the value is [unique CURIE count, single-UMLS-clique
        # count, up to _SAMPLE_LIMIT (CURIE, label) samples]. This answers "where does UMLS go inside
        # Babel, by semantic type" -- summing curie_count over a compendium reproduces its total. The
        # leftover umls.txt compendium is added in the MRCONSO sweep below, so this one CSV spans every
        # compendium that consumes UMLS.
        semantic_breakdown: dict[tuple[str, frozenset], list] = defaultdict(lambda: [0, 0, []])

        for compendium in compendia:
            logger.info(f"Starting compendium: {compendium}")
            name = Path(compendium).name
            with open(compendium) as f:
                breakdown, umls_ids = summarize_compendium_umls_by_semantic_type(
                    (json.loads(row) for row in f), semantic_key
                )
            for key, (count, single_count, samples) in breakdown.items():
                entry = semantic_breakdown[(name, key)]
                entry[0] += count
                entry[1] += single_count
                entry[2].extend(samples[: _SAMPLE_LIMIT - len(entry[2])])

            logger.info(f"Completed compendium {compendium} with {len(umls_ids)} UMLS IDs")
            umls_ids_in_other_compendia.update(umls_ids)

        logger.info(f"Completed all compendia with {len(umls_ids_in_other_compendia)} UMLS IDs.")
        reportf.write(f"COMPLETED All compendia with {len(umls_ids_in_other_compendia)} UMLS IDs.\n")

        leftover_compendium_name = Path(umls_compendium).name

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

        # Report accumulators: exact counts plus up to 5 (CURIE, label) samples, keyed by Biolink type /
        # unmapped TUI / rejected TUI / frozenset of Biolink types. Counts and samples answer different
        # questions and are both kept: counts are quantitative (how many CUIs in each bucket, always
        # exact), samples are qualitative (what a concept in the bucket looks like, for eyeballing the
        # CSVs). The cap is not an approximation of the counts -- it only bounds memory across millions
        # of MRCONSO lines. The exhaustive per-CURIE record lives elsewhere: kept concepts in
        # compendia/umls.txt, skipped concepts in log.txt (NO_UMLS_TYPE / REJECTED / MULTIPLE_UMLS_TYPES).
        # See docs/sources/UMLS/Leftover.md ("Counts vs. samples"). (_SAMPLE_LIMIT defined above.)
        type_counts: dict[str, int] = defaultdict(int)
        type_samples: dict[str, list] = defaultdict(list)
        unmapped_tui_counts: dict[str, int] = defaultdict(int)
        unmapped_tui_examples: dict[str, list] = defaultdict(list)
        rejected_tui_counts: dict[str, int] = defaultdict(int)
        rejected_tui_examples: dict[str, list] = defaultdict(list)
        multi_type_counts: dict[frozenset, int] = defaultdict(int)
        multi_type_samples: dict[frozenset, list] = defaultdict(list)

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
                        logger.warning(
                            f"No Biolink type for {umls_id}: unmapped STY {sorted(unmapped_tuis)} in {umls_type_results}, skipping"
                        )
                        reportf.write(
                            f"NO_UMLS_TYPE [{umls_id}]: unmapped STY {sorted(unmapped_tuis)} in {umls_type_results}\n"
                        )
                        for tui in unmapped_tuis:
                            unmapped_tui_counts[tui] += 1
                            if len(unmapped_tui_examples[tui]) < _SAMPLE_LIMIT:
                                unmapped_tui_examples[tui].append((umls_id, label))
                    continue

                # If every semantic type was deliberately rejected (or there were none), skip and
                # report as rejected -- distinct from "couldn't be mapped".
                if not mapped_types:
                    if umls_id not in curies_rejected:
                        curies_rejected.add(umls_id)
                        logger.info(
                            f"Rejected {umls_id}: rejected STY {sorted(rejected_tuis)} in {umls_type_results}, skipping"
                        )
                        reportf.write(
                            f"REJECTED [{umls_id}]: rejected STY {sorted(rejected_tuis)} in {umls_type_results}\n"
                        )
                        for tui in rejected_tuis:
                            rejected_tui_counts[tui] += 1
                            if len(rejected_tui_examples[tui]) < _SAMPLE_LIMIT:
                                rejected_tui_examples[tui].append((umls_id, label))
                    continue

                # Disambiguate when a concept resolves to multiple Biolink types.
                biolink_types = apply_generic_demotion(mapped_types)
                if len(biolink_types) > 1 and frozenset(biolink_types) in TYPE_COMBO_OVERRIDES:
                    biolink_types = {TYPE_COMBO_OVERRIDES[frozenset(biolink_types)]}

                if len(biolink_types) > 1:
                    # We skip this CURIE, but we don't want to print multiple log messages for the same CURIE.
                    if umls_id not in curies_multiple_umls_type:
                        curies_multiple_umls_type.add(umls_id)
                        biolink_types_as_str = "|".join(sorted(biolink_types))
                        logger.warning(
                            f"Multiple Biolink types not yet supported for {umls_id}: {umls_type_results} -> {biolink_types_as_str}, skipping"
                        )
                        reportf.write(f"MULTIPLE_UMLS_TYPES [{umls_id}]\t{biolink_types_as_str}\t{umls_type_results}\n")
                        key = frozenset(biolink_types)
                        multi_type_counts[key] += 1
                        if len(multi_type_samples[key]) < _SAMPLE_LIMIT:
                            multi_type_samples[key].append((umls_id, label))
                    continue

                biolink_type = next(iter(biolink_types))
                preferred_name_by_id[umls_id] = label

                # Let write_compendium() generate this singleton's compendium and synonym JSON.
                leftover_umls_cliques.append(TypedClique(node_type=biolink_type, identifiers=[umls_id]))
                umls_ids_in_this_compendium.add(umls_id)
                type_counts[biolink_type] += 1
                if len(type_samples[biolink_type]) < _SAMPLE_LIMIT:
                    type_samples[biolink_type].append((umls_id, label))

                # Also record this leftover concept in the per-compendium semantic-type breakdown, so
                # umls.txt appears alongside the input compendia. Every leftover clique is a single
                # UMLS identifier, so it counts toward single_umls_clique_count too.
                leftover_entry = semantic_breakdown[(leftover_compendium_name, semantic_key(umls_id))]
                leftover_entry[0] += 1
                leftover_entry[1] += 1
                if len(leftover_entry[2]) < _SAMPLE_LIMIT:
                    leftover_entry[2].append((umls_id, label))

        logger.info(f"Wrote out {len(umls_ids_in_this_compendium)} UMLS IDs into the leftover UMLS compendium.")
        reportf.write(
            f"COMPLETED Wrote out {len(umls_ids_in_this_compendium)} UMLS IDs into the leftover UMLS compendium.\n"
        )

        logger.info(
            f"Found {len(curies_no_umls_type)} UMLS IDs without a Biolink type, "
            f"{len(curies_rejected)} deliberately rejected, and {len(curies_multiple_umls_type)} with multiple Biolink types."
        )
        reportf.write(
            f"COUNT Found {len(curies_no_umls_type)} UMLS IDs without a Biolink type, "
            f"{len(curies_rejected)} deliberately rejected, and {len(curies_multiple_umls_type)} with multiple Biolink types.\n"
        )

        logger.info(f"Writing {len(leftover_umls_cliques)} leftover UMLS cliques with write_compendium().")
        reportf.write(f"COUNT Writing {len(leftover_umls_cliques)} leftover UMLS cliques with write_compendium().\n")

        # Per-compendium UMLS coverage, broken down by most-specific UMLS semantic-type set. One row
        # per (compendium, TUI set). TUIs and tree numbers are emitted as codes (no labels) so the
        # grouping is scannable at a glance; tui-sty.tsv is the code -> label lookup. Summing
        # curie_count over a compendium reproduces its total unique UMLS count.
        with open(report_dir / "compendium-coverage.csv", "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(
                ["compendium", "tui_set", "tui_set_labels", "tree_set", "curie_count", "single_umls_clique_count", "sample_curies"]
            )
            for name, key in sorted(semantic_breakdown.keys(), key=lambda nk: (nk[0], sorted(nk[1]))):
                curie_count, single_count, samples = semantic_breakdown[(name, key)]
                sorted_tuis = sorted(key)
                tui_set = "|".join(sorted_tuis) if sorted_tuis else "(none)"
                tui_set_labels = "|".join("/".join(sorted(types_by_tui.get(tui, {""}))) for tui in sorted_tuis) if sorted_tuis else "(none)"
                tree_set = "|".join(tui_to_tree.get(tui, "") for tui in sorted_tuis)
                writer.writerow([name, tui_set, tui_set_labels, tree_set, curie_count, single_count, _format_samples(samples)])

        # Per-Biolink-type leftover clique coverage, with a few sample CURIEs and labels.
        with open(report_dir / "types-coverage.csv", "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(["biolink_type", "leftover_clique_count", "sample_curies"])
            for biolink_type in sorted(type_counts.keys()):
                writer.writerow([biolink_type, type_counts[biolink_type], _format_samples(type_samples[biolink_type])])

        # Semantic types we couldn't map or deliberately rejected, with affected CUI counts and samples.
        with open(report_dir / "unmapped-types.csv", "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(["tui", "sty_name", "status", "affected_cui_count", "sample_curies"])
            for status, counts, examples in (
                ("unmapped", unmapped_tui_counts, unmapped_tui_examples),
                ("rejected", rejected_tui_counts, rejected_tui_examples),
            ):
                for tui in sorted(counts.keys()):
                    sty_name = "|".join(sorted(types_by_tui.get(tui, set())))
                    writer.writerow([tui, sty_name, status, counts[tui], _format_samples(examples[tui])])

        # CURIEs that resolved to multiple Biolink types after TYPE_COMBO_OVERRIDES, with counts and samples.
        with open(report_dir / "multi-type-curies.csv", "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(["biolink_types", "affected_cui_count", "sample_curies"])
            for key in sorted(multi_type_counts.keys(), key=lambda s: "|".join(sorted(s))):
                writer.writerow(
                    ["|".join(sorted(key)), multi_type_counts[key], _format_samples(multi_type_samples[key])]
                )

    write_compendium(
        metadata_yamls,
        leftover_umls_cliques,
        "umls.txt",
        None,
        labels=preferred_name_by_id,
        extra_prefixes=[UMLS],
        icrdf_filename=icrdf_filename,
    )

    logger.info(
        f"Wrote leftover UMLS outputs: {umls_compendium}, {umls_synonyms}, metadata/umls.txt.yaml, and coverage CSVs in {report_dir}."
    )
