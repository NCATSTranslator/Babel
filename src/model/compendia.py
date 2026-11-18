"""Write the compendia of a pipeline that types its cliques into several Biolink classes.

Anatomy, chemicals, disease/phenotype and process each end the same way: one compendium per Biolink
type, written from one rule. :func:`write_typed_compendia` is that loop, kept in one place so the
icRDF.tsv load it shares across outputs can't be dropped by one copy of it (see its docstring).
"""

from collections.abc import Callable, Iterable, Mapping

from src.babel_utils import write_compendium
from src.node import InformationContentFactory
from src.util import get_logger

logger = get_logger(__name__)


def write_typed_compendia(
    metadata_yamls,
    typed_sets: Mapping[str, Iterable],
    icrdf_filename,
    extra_prefixes_for: Callable[[str], list] | None = None,
    **write_kwargs,
):
    """Write ``<BareType>.txt`` for each ``{biolink_type: cliques}`` entry of `typed_sets`, loading icRDF.tsv once.

    icRDF.tsv is ~3.9 million rows, and :func:`write_compendium` re-reads it on every call unless it is
    handed an ``ic_factory``. This builds that factory once and passes it to every write, and holds it
    only for the duration of this call: a module-level cache would keep the several-hundred-MB dict for
    the life of the process, which in a local Snakemake run is every rule that follows.

    :param metadata_yamls: Passed to every ``write_compendium`` call.
    :param typed_sets: ``{biolink_type: cliques}``, e.g. a pipeline's ``create_typed_sets()`` result.
        If it is empty, nothing is written and icRDF.tsv is not read.
    :param icrdf_filename: The icRDF.tsv path. Required, and checked before anything is loaded, so a
        rule that forgot to declare it as an input gets this error rather than one from ``open()``.
    :param extra_prefixes_for: Maps a Biolink type to the ``extra_prefixes`` for that type's compendium.
        It is a function of the type, not one list, because ``extra_prefixes`` is a per-class allowlist
        (see ``write_compendium``): one list passed to every output grants each class the exemptions
        argued for the others.
    :param write_kwargs: Any other ``write_compendium`` keyword argument, passed to every call
        (e.g. ``properties_jsonl_gz_files``).
    """
    if not icrdf_filename:
        raise RuntimeError("No icrdf_filename parameter provided to write_typed_compendia() -- this is required!")
    if not typed_sets:
        logger.warning(f"write_typed_compendia() was given no typed sets; writing nothing (outputs: {metadata_yamls})")
        return

    ic_factory = InformationContentFactory(icrdf_filename)
    for biotype, sets in typed_sets.items():
        baretype = biotype.split(":")[-1]
        write_compendium(
            metadata_yamls,
            sets,
            f"{baretype}.txt",
            biotype,
            {},
            extra_prefixes=extra_prefixes_for(biotype) if extra_prefixes_for else None,
            icrdf_filename=icrdf_filename,
            ic_factory=ic_factory,
            **write_kwargs,
        )
