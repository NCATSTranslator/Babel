"""Build the ClinicalFinding compendium (``biolink:ClinicalFinding``) — currently LOINC clinical terms.

A dedicated pipeline (like ``transcript``) rather than a fold into ``diseasephenotype``: LOINC is
registered for ``biolink:ClinicalFinding`` and, in v1, has no concord linking it to HP/MP/MONDO, so its
terms form singleton cliques that don't interact with the disease/phenotype classifier. If a
LOINC↔ontology concord becomes available, LOINC should move into the diseasephenotype pipeline so the
equivalences glom into the existing disease/phenotype cliques.
"""

from src.babel_utils import write_compendium
from src.categories import CLINICAL_FINDING
from src.model.cliques import glom_from_files
from src.util import get_logger

logger = get_logger(__name__)


def compute_cliques_for_impact_report(concordances, identifiers, excluded_sources=()):
    """Build the ClinicalFinding clique state in memory without writing compendia.

    Shaped for registration in the source-impact report's ``PIPELINE_CONFIG`` (see
    ``docs/AddingNewSources.md`` step 8) but not yet registered. ``excluded_sources`` lets the report
    compute the before-new-source state once registered.
    """
    return glom_from_files(concordances, identifiers, unique_prefixes=[], excluded_sources=excluded_sources)


def build_compendia(concordances, metadata_yamls, identifiers, icrdf_filename):
    """Glom the ClinicalFinding ids/concords and write ``ClinicalFinding.txt``.

    LOINC has no concords in v1, so ``concordances``/``metadata_yamls`` are empty and the compendium is
    built from the ids alone (singleton cliques); ``write_compendium`` accepts an empty metadata list.
    """
    dicts, _types = compute_cliques_for_impact_report(concordances, identifiers)
    clinical_sets = set(frozenset(clique) for clique in dicts.values())
    baretype = CLINICAL_FINDING.split(":")[-1]  # "ClinicalFinding"
    logger.info(f"Building ClinicalFinding compendium: {len(clinical_sets)} cliques")
    write_compendium(
        metadata_yamls, clinical_sets, f"{baretype}.txt", CLINICAL_FINDING, {}, icrdf_filename=icrdf_filename
    )
