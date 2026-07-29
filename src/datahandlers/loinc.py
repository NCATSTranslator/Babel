"""Parse LOINC (Logical Observation Identifiers Names and Codes) for the ClinicalFinding compendium.

LOINC (https://loinc.org) is a terminology of clinical observations (lab tests, clinical measurements,
survey items, ...). Babel ingests the *clinical* subset as ``biolink:ClinicalFinding`` in a dedicated
``clinicalfinding`` pipeline.

Download: LOINC's official full release (``loinc.csv``) requires a free account at
https://loinc.org/downloads and cannot be fetched anonymously. When ``loinc_download_url`` is empty
(the default), the ``get_loinc`` rule falls back to the Tuva Project's public S3 mirror, which
re-distributes the LOINC release (same 104k+ codes, same CLASSTYPE semantics) as a headerless CSV —
no credentials required. That headerless format is handled by ``_loinc_has_header`` / the positional
branch of ``_iter_clinical_loinc``. When ``loinc_download_url`` is set, the official headered
loinc.csv is downloaded instead. The unit tests cover both formats.

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

# Tuva mirror CSV column indices (headerless, same LOINC data, positional layout). See
# _loinc_has_header / _iter_clinical_loinc: the anonymous Tuva fallback ships a headerless file.
_TUVA_LOINC_NUM_INDEX = 0
_TUVA_LONG_NAME_INDEX = 2
_TUVA_CLASSTYPE_INDEX = 11


def _loinc_has_header(loinc_csv):
    """Detect whether ``loinc_csv`` carries a header row.

    The official LOINC release uses the documented column names (``LOINC_NUM``, ``CLASSTYPE``,
    ``LONG_COMMON_NAME``) and is read by name. The Tuva Project mirror — the anonymous fallback
    used when no credential-gated ``loinc_download_url`` is configured — ships a headerless CSV
    with positional columns: same data, different layout.
    """
    with open(loinc_csv, newline="", encoding="utf-8-sig") as inf:
        first_row = next(csv.reader(inf), [])
    return bool(first_row) and "LOINC_NUM" in first_row


def _iter_clinical_loinc(loinc_csv):
    """Yield ``(loinc_num, long_common_name)`` for each Clinical-class (``CLASSTYPE=2``) LOINC row.

    Opens with ``utf-8-sig`` so a UTF-8 BOM (which would otherwise corrupt the first header name,
    ``LOINC_NUM``, and silently skip every row) is stripped; it is identical to ``utf-8`` when no BOM is
    present.

    Handles two on-disk formats:
    - **Official ``loinc.csv``** (header present): read by column name, robust to reordering.
    - **Tuva mirror** (headerless): read by fixed column index (0=LOINC_NUM, 2=LONG_COMMON_NAME,
      11=CLASSTYPE).
    """
    if _loinc_has_header(loinc_csv):
        with open(loinc_csv, newline="", encoding="utf-8-sig") as inf:
            reader = csv.DictReader(inf)
            for row in reader:
                if (row.get(_CLASSTYPE_COLUMN) or "").strip() != _CLINICAL_CLASSTYPE:
                    continue
                loinc_num = (row.get(_LOINC_NUM_COLUMN) or "").strip()
                if not loinc_num:
                    continue
                yield loinc_num, (row.get(_LONG_NAME_COLUMN) or "").strip()
    else:
        with open(loinc_csv, newline="", encoding="utf-8-sig") as inf:
            reader = csv.reader(inf)
            for row in reader:
                if len(row) <= _TUVA_CLASSTYPE_INDEX:
                    continue
                if row[_TUVA_CLASSTYPE_INDEX].strip() != _CLINICAL_CLASSTYPE:
                    continue
                loinc_num = row[_TUVA_LOINC_NUM_INDEX].strip()
                if not loinc_num:
                    continue
                yield loinc_num, row[_TUVA_LONG_NAME_INDEX].strip()


def write_loinc_ids(loinc_csv, outfile):
    """Write Clinical-class LOINC identifiers as a Babel ids file typed ``biolink:ClinicalFinding``.

    Raises ``RuntimeError`` if no Clinical-class rows are parsed: the default anonymous download
    (the Tuva mirror's ``loinc.csv_0_0_0.csv.gz``) can still fail — e.g. a network error leaving a stale
    or truncated file — and a silent empty compendium is worse than a loud failure.
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
