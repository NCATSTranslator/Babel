"""Clients for the deployed Node Normalization and Name Resolution services, and Babel Explorer links.

Babel's output is only ever seen by users through these services, so investigating a report ("these two
CURIEs should be one node") starts by asking each deployment what it currently serves. The instance keys
(``dev``, ``ci``, ``test``, ``prod``, ``exp``) are the ones Babel Explorer and babel-validation use, so a
link or a ``--target`` means the same deployment everywhere.

Every function that touches the network is named ``fetch_*``.
"""

import urllib.parse

import requests

# Deployments by instance key, matching the targets in babel-validation's tests/targets.ini and the keys
# Babel Explorer accepts in `target=`. dev and exp are RENCI's Redis/Solr deployments that Babel developers
# update first; ci, test and prod are the ITRB pipeline (NodeNorm on ElasticSearch), in promotion order.
# Each one serves a single Babel build; fetch_babel_version() says which.
NODENORM_INSTANCES = {
    "dev": "https://nodenormalization-sri.renci.org/",
    "exp": "https://nodenormalization-exp.apps.renci.org/",
    "ci": "https://nodenorm-es.ci.transltr.io/",
    "test": "https://nodenorm-es.test.transltr.io/",
    "prod": "https://nodenorm-es.transltr.io/",
}
NAMERES_INSTANCES = {
    "dev": "https://name-resolution-sri.renci.org/",
    "exp": "https://name-resolution-exp.apps.renci.org/",
    "ci": "https://name-lookup.ci.transltr.io/",
    "test": "https://name-lookup.test.transltr.io/",
    "prod": "https://name-lookup.transltr.io/",
}

# Seconds before a request to one of the services gives up. A get_normalized_nodes call for a few dozen
# CURIEs with DrugChemical conflation returns in well under a second when the service is healthy; the
# margin covers a cold ElasticSearch cache without letting a dead deployment stall a report for minutes.
REQUEST_TIMEOUT_SECONDS = 60

BABEL_EXPLORER_NODENORM_URL = "https://translatorsri.github.io/babel-explorer/nodenorm/"

# The NodeNorm options Babel Explorer's form offers. All default to true there, so a link carries an option
# only to turn it off (`drug_chemical_conflate=false`); see web/src/lib/types.ts in babel-explorer.
# TranslatorSRI/babel-explorer#76 asks for this format to be documented for agents.
BABEL_EXPLORER_NODENORM_OPTIONS = ("conflate", "drug_chemical_conflate", "description", "include_taxa")

# The order Babel Explorer itself shows deployments in, used when a caller doesn't choose.
DEFAULT_EXPLORER_TARGETS = ("dev", "ci", "test", "prod")


def fetch_normalized_nodes(
    base_url: str, curies: list[str], conflate: bool = True, drug_chemical_conflate: bool = False
) -> dict[str, dict | None]:
    """Normalize ``curies`` on one NodeNorm deployment; a CURIE NodeNorm doesn't know maps to ``None``.

    Uses POST so a long CURIE list never meets a URL length limit. Descriptions are left out: nothing here
    reads them, and they are most of the response's size.
    """
    response = requests.post(
        urllib.parse.urljoin(base_url, "get_normalized_nodes"),
        json={
            "curies": list(curies),
            "conflate": conflate,
            "drug_chemical_conflate": drug_chemical_conflate,
            "description": False,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def fetch_name_lookup(base_url: str, name: str, limit: int = 20) -> list[dict]:
    """Search one NameRes deployment for ``name`` (not as autocomplete) and return its ranked hits.

    NameRes indexes the DrugChemical-conflated cliques, so two hits here are separate nodes even with
    conflation on.
    """
    response = requests.get(
        urllib.parse.urljoin(base_url, "lookup"),
        params={"string": name, "limit": limit, "autocomplete": "false"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def fetch_babel_version(base_url: str) -> str | None:
    """The Babel build a NodeNorm or NameRes deployment serves, from its ``/status``; ``None`` if it doesn't say."""
    response = requests.get(urllib.parse.urljoin(base_url, "status"), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json().get("babel_version")


def babel_explorer_url(curies: list[str], targets=DEFAULT_EXPLORER_TARGETS, **options: bool) -> str:
    """A Babel Explorer link comparing ``curies`` across the NodeNorm ``targets``.

    The state goes in the URL fragment, which never reaches a server, so a long CURIE list is fine. Options
    are the ones in :data:`BABEL_EXPLORER_NODENORM_OPTIONS`; since Babel Explorer turns them all on by
    default, only an option set to ``False`` is written to the link.
    """
    unknown = set(options) - set(BABEL_EXPLORER_NODENORM_OPTIONS)
    if unknown:
        raise ValueError(f"Babel Explorer has no NodeNorm option(s) {sorted(unknown)}")
    unknown_targets = [t for t in targets if t not in NODENORM_INSTANCES]
    if unknown_targets:
        raise ValueError(f"Unknown NodeNorm instance(s) {unknown_targets}; known: {sorted(NODENORM_INSTANCES)}")
    params = [("curie", curie) for curie in curies] + [("target", target) for target in targets]
    params += [(name, "false") for name in BABEL_EXPLORER_NODENORM_OPTIONS if options.get(name) is False]
    return BABEL_EXPLORER_NODENORM_URL + "#" + urllib.parse.urlencode(params)
