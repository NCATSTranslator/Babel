"""Build the SequenceVariant compendium (``biolink:SequenceVariant``) — currently ClinVar variants.

A dedicated pipeline (like ``transcript``/``clinicalfinding``). ClinVar is registered for
``biolink:SequenceVariant`` (as is ``DBSNP``), so no ``extra_prefixes`` is needed. The only concord is
``CLINVAR``↔``DBSNP`` (an identifier equivalence); variant↔gene relationships are deliberately excluded
(a variant is in a gene but is not the gene — see ``src/datahandlers/clinvar.py``).
"""

from src.babel_utils import write_compendium
from src.categories import SEQUENCE_VARIANT
from src.model.cliques import glom_from_files
from src.util import get_logger

logger = get_logger(__name__)


def compute_cliques_for_impact_report(concordances, identifiers, excluded_sources=()):
    """Build the SequenceVariant clique state in memory without writing compendia.

    Shaped for registration in the source-impact report's ``PIPELINE_CONFIG`` (see
    ``docs/AddingNewSources.md`` step 8) but not yet registered. ``excluded_sources`` lets the report
    compute the before-new-source state once registered.
    """
    return glom_from_files(concordances, identifiers, unique_prefixes=[], excluded_sources=excluded_sources)


def build_compendia(concordances, metadata_yamls, identifiers, icrdf_filename):
    """Glom the SequenceVariant ids/concords and write ``SequenceVariant.txt``."""
    dicts, _types = compute_cliques_for_impact_report(concordances, identifiers)
    variant_sets = set(frozenset(clique) for clique in dicts.values())
    baretype = SEQUENCE_VARIANT.split(":")[-1]  # "SequenceVariant"
    logger.info(f"Building SequenceVariant compendium: {len(variant_sets)} cliques")
    write_compendium(
        metadata_yamls, variant_sets, f"{baretype}.txt", SEQUENCE_VARIANT, {}, icrdf_filename=icrdf_filename
    )
