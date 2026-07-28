"""Parse LOINC (Logical Observation Identifiers Names and Codes) for the ClinicalFinding compendium.

LOINC (https://loinc.org) is a terminology of clinical observations (lab tests, clinical measurements,
survey items, ...). Babel ingests the *clinical* subset as ``biolink:ClinicalFinding`` in a dedicated
``clinicalfinding`` pipeline.

Download caveat (load-bearing): the full LOINC release (``loinc.csv``) is available only under a FREE
LOINC account (https://loinc.org/downloads) — it cannot be fetched anonymously. The ``get_loinc`` rule
pulls it from ``loinc_download_url`` in ``config.yaml`` (an authenticated URL the operator supplies);
absent that, place ``loinc.csv`` at ``babel_downloads/LOINC/loinc.csv`` manually. Consequently this
module is unit-tested against an *illustrative* fixture built from the documented LOINC Table Structure
and public LOINC codes — NOT a verbatim download extract — and must be validated against the real file
(with credentials) on a build machine before relying on it.

Design notes:

- **CLASSTYPE filter.** LOINC's ``CLASSTYPE`` is the authoritative primary key: 1=Laboratory, 2=Clinical,
  3=Claims attachments, 4=Surveys. v1 ingests ``CLASSTYPE=2`` (Clinical) as clinical findings;
  lab/claims/surveys are excluded (a deliberate, expandable choice).
- **No concords in v1.** No comprehensive LOINC↔HP/EFO/UMLS equivalence source is identified, so LOINC
  terms form singleton cliques (still useful — they get labels and normalize as biolink:ClinicalFinding).
  A future LOINC↔ontology concord would require integrating LOINC into the diseasephenotype pipeline so
  the equivalences glom.
- **No extra_prefixes.** LOINC is the #1 registered prefix for ``biolink:ClinicalFinding`` in the pinned
  Biolink Model, so ``write_compendium`` keeps LOINC CURIEs without an escape hatch.
"""

import csv

from src.categories import CLINICAL_FINDING
from src.util import ensure_parent_dir, get_logger

logger = get_logger(__name__)

# loinc.csv column names, read by name (robust to column reordering and the file's many extra columns).
_LOINC_NUM_COLUMN = "LOINC_NUM"
_CLASSTYPE_COLUMN = "CLASSTYPE"
_LONG_NAME_COLUMN = "LONG_COMMON_NAME"

# CLASSTYPE primary-key value for the Clinical class (the only class v1 ingests).
_CLINICAL_CLASSTYPE = "2"


def _iter_clinical_loinc(loinc_csv):
    """Yield ``(loinc_num, long_common_name)`` for each Clinical-class (``CLASSTYPE=2``) LOINC row.

    Opens with ``utf-8-sig`` so a UTF-8 BOM (which would otherwise corrupt the first header name,
    ``LOINC_NUM``, and silently skip every row) is stripped; it is identical to ``utf-8`` when no BOM is
    present.
    """
    with open(loinc_csv, newline="", encoding="utf-8-sig") as inf:
        reader = csv.DictReader(inf)
        for row in reader:
            if (row.get(_CLASSTYPE_COLUMN) or "").strip() != _CLINICAL_CLASSTYPE:
                continue
            loinc_num = (row.get(_LOINC_NUM_COLUMN) or "").strip()
            if not loinc_num:
                continue
            yield loinc_num, (row.get(_LONG_NAME_COLUMN) or "").strip()


def write_loinc_ids(loinc_csv, outfile):
    """Write Clinical-class LOINC identifiers as a Babel ids file typed ``biolink:ClinicalFinding``.

    Raises ``RuntimeError`` if no Clinical-class rows are parsed: because the download is
    credential-gated, a failed download (e.g. an expired credential returning an HTML login page that wget
    saves as ``loinc.csv``) would otherwise produce a silent empty compendium.
    """
    ensure_parent_dir(outfile)
    wrote = set()
    with open(outfile, "w", encoding="utf-8") as outf:
        for loinc_num, _name in _iter_clinical_loinc(loinc_csv):
            curie = f"LOINC:{loinc_num}"
            if curie in wrote:
                continue
            wrote.add(curie)
            outf.write(f"{curie}\t{CLINICAL_FINDING}\n")
    if not wrote:
        raise RuntimeError(
            f"No CLASSTYPE=2 (Clinical) LOINC rows were parsed from {loinc_csv}. The download may have "
            "failed (e.g. an expired credential returning an HTML login page saved as loinc.csv) — verify "
            "loinc.csv is the real LOINC release."
        )
    logger.info(f"Wrote {len(wrote)} Clinical-class LOINC identifiers from {loinc_csv}")


def write_loinc_labels(loinc_csv, outfile):
    """Write a ``CURIE\\tlabel`` labels file for Clinical-class LOINC terms (from ``LONG_COMMON_NAME``)."""
    ensure_parent_dir(outfile)
    wrote = set()
    with open(outfile, "w", encoding="utf-8") as outf:
        for loinc_num, name in _iter_clinical_loinc(loinc_csv):
            curie = f"LOINC:{loinc_num}"
            if curie in wrote or not name:
                continue
            wrote.add(curie)
            outf.write(f"{curie}\t{name}\n")
    logger.info(f"Wrote {len(wrote)} Clinical-class LOINC labels from {loinc_csv}")
