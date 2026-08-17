"""NCATS GARD (Genetic and Rare Diseases) rare-disease registry data handler.

GARD is a flat registry of rare-disease terms distributed by NCATS as a single CSV (UTF-8 with
BOM, CRLF line endings) with four columns -- ``ID``, ``DisplayName``, ``Synonyms``, ``URL``:

* ``ID`` -- a ``GARD:NNNNNNN`` CURIE (zero-padded to seven digits in the distribution; see
  "Local-id form" below -- Babel emits the unpadded form).
* ``DisplayName`` -- the preferred label.
* ``Synonyms`` -- pipe-separated (``|``) alternative names; empty for many rows.
* ``URL`` -- the rarediseases.info.nih.gov page. Babel has no per-identifier URL attribute file
  (handlers emit only labels/synonyms/taxa/descriptions), so the column is not ingested.

Local-id form
-------------
The distribution zero-pads every local id to seven digits (``GARD:0006038``), but DOID -- the one
other disease source that cross-references GARD -- overwhelmingly emits the unpadded form
(``GARD:6038``: 2,164 of its 2,187 GARD xrefs, the remaining 23 padded). Babel standardizes on the
**unpadded** form, so :func:`normalize_gard_curie` strips leading zeros both here and on DOID's
xref targets (``src/datahandlers/doid.py``). Without that, ``GARD:0006038`` from the registry and
``GARD:6038`` from DOID are two identifiers for one disease and ~1,886 rare diseases normalize to
two conflicting cliques.

GARD itself carries no cross-references to other disease vocabularies (MONDO/DOID/UMLS/...), so it
contributes identifiers and labels/synonyms only -- there is no GARD concord file. Cliques still
merge, in the other direction: DOID's xrefs pull 1,886 registry terms into existing DOID/MONDO
disease cliques. (DOID also asserts 300 GARD ids that the current registry no longer publishes;
those join their DOID clique without a label, the same as any other xref target Babel does not
ingest.)

Every GARD term is typed ``biolink:Disease``. ``GARD`` is registered neither in the Biolink Model's
``disease`` ``id_prefixes`` nor in its prefix map (verified against the pinned
``biolink_version``), so the disease compendium build passes ``extra_prefixes=[GARD]`` to keep the
identifiers (see ``src/createcompendia/diseasephenotype.py``); registering GARD with the Biolink
team is the long-term fix, the same situation GTDB is in (see PR #978).

Field-shape note: a scan of the published CSV (16,214 rows) found no ``DisplayName`` or
``Synonyms`` value containing an embedded tab or newline, and no row with an empty
``DisplayName``. The labels/synonyms writers therefore emit raw values without sanitization,
matching the Orphanet/DOID handlers.
"""

import csv
import urllib.request

from src.babel_utils import get_user_agent, make_local_name
from src.prefixes import GARD, OIO
from src.util import get_config, get_logger

logger = get_logger(__name__)


def normalize_gard_curie(curie):
    """Strip the zero-padding from a ``GARD:`` local id, leaving non-GARD CURIEs untouched.

    ``GARD:0006038`` -> ``GARD:6038``. Babel standardizes on the unpadded form because that is what
    DOID's xrefs overwhelmingly use; see the module docstring. Applied both when reading the
    registry CSV and to DOID's xref targets, so the two ID spaces meet.
    """
    prefix, _, local_id = curie.partition(":")
    if prefix != GARD or not local_id.lstrip("0").isdigit():
        return curie
    return f"{GARD}:{local_id.lstrip('0')}"


def pull_gard():
    """Download the GARD term CSV to ``babel_downloads/GARD/gard.csv`` and return the path.

    The distribution is a Salesforce ContentVersion download link -- a single URL with a query
    string and no stable filename on the server -- so ``pull_via_urllib``'s ``url + in_file_name``
    assembly does not fit. We fetch the configured URL directly with redirect + User-Agent
    handling (mirroring ``pull_via_urllib``). The URL lives in ``config.yaml``
    (``gard_download_url``) so it can be pinned or repointed without a code change.
    """
    url = get_config()["gard_download_url"]
    outfile = make_local_name("gard.csv", subpath=GARD)

    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
    request = urllib.request.Request(url, headers={"User-Agent": get_user_agent()})
    logger.info("Downloading GARD term list from %s", url)
    with opener.open(request) as response, open(outfile, "wb") as out:
        out.write(response.read())
    return outfile


def pull_gard_labels_and_synonyms(infile, labelfile, synonymfile):
    """Parse the GARD CSV into per-prefix ``labels`` and ``synonyms`` files.

    * ``labels`` -- one ``GARD:<id>\\t<DisplayName>`` row per term that has a name.
    * ``synonyms`` -- one ``GARD:<id>\\tOIO:hasExactSynonym\\t<synonym>`` row per synonym, with
      the ``DisplayName`` itself emitted first as an exact synonym (the Orphanet/DOID convention,
      so the preferred label is searchable as a synonym too).

    Local ids are unpadded via :func:`normalize_gard_curie` so they match DOID's xrefs.

    The CSV is UTF-8 with a BOM and CRLF line endings; ``utf-8-sig`` strips the BOM and
    ``newline=""`` lets the ``csv`` module handle embedded/CRLF quoting correctly. Rows whose
    ``ID`` is not a ``GARD:`` CURIE are skipped defensively (the registry contains only GARD ids,
    but a malformed trailing row must never abort the whole ingest).

    A parse summary is logged at the end so a future NCATS format change (e.g. a header or
    ID-column rename that silently zeroes the output) is visible in the build log rather than
    producing an empty file quietly.
    """
    parsed = 0
    skipped_non_gard = 0
    empty_name = 0
    with (
        open(infile, encoding="utf-8-sig", newline="") as inf,
        open(labelfile, "w") as labels,
        open(synonymfile, "w") as syns,
    ):
        reader = csv.DictReader(inf)
        for row in reader:
            curie = normalize_gard_curie((row.get("ID") or "").strip())
            if not curie.startswith(f"{GARD}:"):
                skipped_non_gard += 1
                continue
            name = (row.get("DisplayName") or "").strip()
            if not name:
                # A GARD term with no name yields no label row, so disease_gard_ids' awk (which
                # derives ids from the labels file) would never emit it and the term would be
                # silently lost. The published CSV has none, but warn per-row so a future
                # distribution change can't quietly drop terms.
                empty_name += 1
                logger.warning("GARD term %s has no DisplayName; it will not be ingested", curie)
                continue
            parsed += 1
            labels.write(f"{curie}\t{name}\n")
            syns.write(f"{curie}\t{OIO}:hasExactSynonym\t{name}\n")
            synonyms_field = (row.get("Synonyms") or "").strip()
            if not synonyms_field:
                continue
            for syn in synonyms_field.split("|"):
                syn = syn.strip()
                if syn:
                    syns.write(f"{curie}\t{OIO}:hasExactSynonym\t{syn}\n")
    logger.info(
        "GARD parse: %d terms written, %d non-GARD rows skipped, %d GARD rows with no DisplayName",
        parsed,
        skipped_non_gard,
        empty_name,
    )
