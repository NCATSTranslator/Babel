"""``babel-compare-resolution`` — how do these CURIEs normalize on each NodeNorm deployment, and why are they separate?

The first step in answering a report that two results "are the same thing". For each ``--target``
deployment it normalizes every CURIE with and without DrugChemical conflation, lists the distinct cliques
with their InChIKeys and key members, says how each pair of cliques' structures relate, and ends with a
Babel Explorer link and a draft ``babel_tests`` block::

    uv run babel-compare-resolution CHEBI:66919 CHEBI:91405 GTOPDB:5688 --target dev --target test
    uv run babel-compare-resolution --name pregabalin --name topiramate --out data/feedback-1438/compare.md
    uv run babel-compare-resolution GTOPDB:5688 CHEBI:66919 --same GTOPDB:5688,CHEBI:66919

``--name`` adds every NameRes hit whose label is that name, which is how to find the "same name, separate
result" nodes a report describes. Writes Markdown to ``--out`` or standard output. A deployment that can't
be reached is reported as such rather than failing the whole run.
"""

import argparse
import sys

import requests

from src.reports.normalization_comparison import (
    DEFAULT_HIGHLIGHT_PREFIXES,
    InstanceResult,
    render_report,
    same_label_curies,
    summarize_instance,
)
from src.util import get_logger
from src.utils.translator_services import (
    NAMERES_INSTANCES,
    NODENORM_INSTANCES,
    babel_explorer_url,
    fetch_babel_version,
    fetch_name_lookup,
    fetch_normalized_nodes,
)

logger = get_logger(__name__)

# NameRes hits to read per --name. A drug's same-label duplicates rank near the top, but salts, brand
# names and products with the name in their label can crowd them; 20 has covered every report so far.
NAME_LOOKUP_LIMIT = 20


def _groups(values: list[str]) -> list[list[str]]:
    """Parse repeated ``A,B[,C]`` arguments into lists of CURIEs."""
    groups = [[c.strip() for c in value.split(",") if c.strip()] for value in values]
    for group in groups:
        if len(group) < 2:
            raise ValueError(f"A group needs at least two comma-separated CURIEs: {group}")
    return groups


def _query_instance(target: str, curies: list[str], highlight_prefixes) -> InstanceResult:
    url = NODENORM_INSTANCES[target]
    try:
        return summarize_instance(
            target,
            fetch_babel_version(url),
            curies,
            fetch_normalized_nodes(url, curies, drug_chemical_conflate=False),
            fetch_normalized_nodes(url, curies, drug_chemical_conflate=True),
            highlight_prefixes,
        )
    except requests.RequestException as err:
        logger.warning("Could not query NodeNorm %s (%s): %s", target, url, err)
        return InstanceResult(target=target, error=str(err))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("curies", nargs="*", help="CURIEs to compare")
    parser.add_argument("--name", action="append", default=[], help="also compare NameRes hits with this label")
    parser.add_argument(
        "--target",
        action="append",
        choices=sorted(NODENORM_INSTANCES),
        help="NodeNorm deployment to query (repeatable; default: dev)",
    )
    parser.add_argument("--same", action="append", default=[], help="A,B: CURIEs the fix should put together")
    parser.add_argument("--different", action="append", default=[], help="A,B: CURIEs that must stay apart")
    parser.add_argument(
        "--show-prefix",
        action="append",
        help=f"prefix whose members to list per clique (repeatable; default: {', '.join(DEFAULT_HIGHLIGHT_PREFIXES)})",
    )
    parser.add_argument("--out", help="write the Markdown report here instead of standard output")
    args = parser.parse_args(argv)

    targets = args.target or ["dev"]
    highlight_prefixes = tuple(args.show_prefix) if args.show_prefix else DEFAULT_HIGHLIGHT_PREFIXES
    same_groups, different_groups = _groups(args.same), _groups(args.different)

    curies = list(args.curies)
    for group in same_groups + different_groups:
        curies += group
    for name in args.name:
        for target in targets:
            try:
                curies += same_label_curies(fetch_name_lookup(NAMERES_INSTANCES[target], name, NAME_LOOKUP_LIMIT), name)
            except requests.RequestException as err:
                logger.warning("Could not search NameRes %s for %r: %s", target, name, err)
    curies = list(dict.fromkeys(curies))
    if not curies:
        parser.error("give at least one CURIE, or a --name that NameRes finds")

    instances = [_query_instance(target, curies, highlight_prefixes) for target in targets]
    report = render_report(
        curies,
        instances,
        babel_explorer_url(curies, targets=targets),
        same_groups,
        different_groups,
        highlight_prefixes,
    )
    if args.out:
        with open(args.out, "w") as out:
            out.write(report)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
