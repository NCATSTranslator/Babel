"""Shared clique-building scaffolding used by multiple compendium modules.

Factors out the common skeleton of turning a set of identifier files and concord files
into union-find clique state via :func:`src.babel_utils.glom`:

    load each ids file  -> glom into the clique state
    load each concord   -> optionally filter pairs -> optionally drop overused xrefs ->
                           glom into the clique state

Each pipeline's ``build_compendia`` (and its ``compute_cliques_for_impact_report``)
can call :func:`glom_from_files` with a few injected hooks rather than duplicating the
loop. Routing the real build through the same function the source-impact report uses
keeps the report from drifting away from what the pipeline actually produces.

The three hooks below cover every divergence currently seen across the anatomy, taxon,
process, and disease compendia, so adopting this helper in those modules later is a
drop-in change:

- ``concord_pair_filter`` — anatomy's "only keep UMLS<->GO pairs already in the clique
  state" rule, process's UMLS gating, disease's per-prefix bad-xref files.
- ``overused_xref_remover`` — anatomy's default :func:`remove_overused_xrefs`, process's
  ``bothways=True`` variant, disease's prefix-conditional removal.
- ``glom_kwargs`` — disease's ``close={MONDO: ...}`` map.
"""

import os
from collections.abc import Callable

from src.babel_utils import glom, read_identifier_file
from src.util import get_logger

logger = get_logger(__name__)

# A concord-pair filter receives the tab-split concord line, the concord file path, and
# the current clique state, and returns True to keep the pair. The clique state is passed
# so a filter can gate a pair on whether its CURIEs were already glommed in (e.g. anatomy
# only trusts UMLS<->GO pairs when both terms are already present).
ConcordPairFilter = Callable[[list[str], str, dict], bool]

# An overused-xref remover receives the list of ``[curie1, curie2]`` pairs read from one
# concord file (plus the file path, so it can vary behaviour per source) and returns the
# filtered list.
OverusedXrefRemover = Callable[[list[list[str]], str], list[list[str]]]


def glom_from_files(
    concordances,
    identifiers,
    *,
    unique_prefixes,
    concord_pair_filter: ConcordPairFilter | None = None,
    overused_xref_remover: OverusedXrefRemover | None = None,
    glom_kwargs: dict | None = None,
    excluded_sources=(),
):
    """Build union-find clique state from identifier and concord files without writing compendia.

    The source-impact report CLI calls a compendium's wrapper twice — once with the new
    source's files excluded, once with everything — to compute a before/after diff.

    :param concordances: list of paths to concord files (tab-separated ``CURIE1 REL CURIE2``)
    :param identifiers: list of paths to ids files
    :param unique_prefixes: passed through to :func:`glom`; prefixes for which at most one
        identifier may appear per clique
    :param concord_pair_filter: optional ``(parts, infile, dicts) -> bool`` hook; return
        False to drop a concord pair. ``parts`` is the tab-split line, ``dicts`` is the
        clique state built so far.
    :param overused_xref_remover: optional ``(pairs, infile) -> pairs`` hook applied to
        each concord file's pairs before they are glommed.
    :param glom_kwargs: optional extra keyword arguments forwarded to every :func:`glom`
        call (e.g. ``{"close": {MONDO: close_mondos}}``).
    :param excluded_sources: set of source names (file basenames) to skip; used to compute
        the "before-new-source" state for the impact report.
    :returns: ``(dicts, types)`` where ``dicts`` is the glom dict-of-sets and ``types``
        maps CURIE to its declared biolink type.
    """
    excluded = set(excluded_sources)
    glom_kwargs = glom_kwargs or {}
    dicts = {}
    types = {}
    for ifile in identifiers:
        if os.path.basename(ifile) in excluded:
            continue
        logger.info("loading ids file %s", ifile)
        new_identifiers, new_types = read_identifier_file(ifile)
        glom(dicts, new_identifiers, unique_prefixes=unique_prefixes, **glom_kwargs)
        types.update(new_types)
    for infile in concordances:
        if os.path.basename(infile) in excluded:
            continue
        logger.info("loading concordance file %s", infile)
        pairs = []
        with open(infile) as inf:
            for line in inf:
                parts = line.strip().split("\t")
                # Skip blank/malformed lines before indexing parts[2]: a concord row is
                # `CURIE1 \t REL \t CURIE2`, so anything with fewer than 3 fields would
                # IndexError here and in concord_pair_filter hooks (e.g. anatomy's, which
                # reads parts[0]/parts[2]).
                if len(parts) < 3:
                    continue
                if concord_pair_filter is not None and not concord_pair_filter(parts, infile, dicts):
                    continue
                pairs.append([parts[0], parts[2]])
        if overused_xref_remover is not None:
            pairs = overused_xref_remover(pairs, infile)
        setpairs = [set(x) for x in pairs]
        glom(dicts, setpairs, unique_prefixes=unique_prefixes, **glom_kwargs)
    return dicts, types
