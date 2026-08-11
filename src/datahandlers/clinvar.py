"""Parse ClinVar variants for the SequenceVariant compendium.

ClinVar (https://www.ncbi.nlm.nih.gov/clinvar/) archives the clinical significance of genomic variants.
Babel ingests it as ``biolink:SequenceVariant`` in a dedicated ``sequencevariant`` pipeline: each ClinVar
variation becomes a ``CLINVAR:<VariationID>`` identifier, linked ``eq`` to its dbSNP ``rs`` identifier
(``DBSNP:rs<N>``) when one is assigned. All variant types (SNV, deletion, indel, ...) are typed
``biolink:SequenceVariant`` (the general class); finer typing (e.g. ``biolink:Snv``) is a refinement.

The source is NCBI's public ``variant_summary.txt.gz`` (anonymous download — no credentials). Its header
prefixes the first column with ``#`` (``#AlleleID``), so the parser strips a leading ``#`` from the header
and reads every column by name (robust to ClinVar's ~40 columns and any reordering); it opens with
``utf-8-sig`` to also tolerate a BOM.

Design notes:

- **Identifier = VariationID.** The ``CLINVAR`` prefix denotes the ClinVar variation (Bioregistry pattern
  ``^\\d+$``), i.e. the ``VariationID`` column — not the per-allele ``AlleleID``. Each variation appears once
  per genome assembly (GRCh37/GRCh38), so identifiers are deduplicated by ``VariationID``.
- **dbSNP link is an equivalence; the gene link is not.** A variant *is* its dbSNP ``rs`` id (different
  identifier, same entity), so ``CLINVAR``↔``DBSNP`` is an ``eq`` concord. A variant is *in* a gene but is not
  the gene, so the ``GeneID`` column is deliberately NOT emitted as an ``eq`` concord (that would merge the
  variant into a gene clique and mis-type it).
- **No extra_prefixes.** Both ``CLINVAR`` and ``DBSNP`` are registered for ``biolink:SequenceVariant`` in the
  pinned Biolink Model, so ``write_compendium`` keeps both without an escape hatch.
"""

from src.categories import SEQUENCE_VARIANT
from src.metadata.provenance import write_concord_metadata
from src.prefixes import CLINVAR, DBSNP
from src.util import ensure_parent_dir, get_logger

logger = get_logger(__name__)

# variant_summary.txt column names, read by name (the first column is '#AlleleID'; the leading '#' is
# stripped from the header before indexing).
_VARIATION_ID_COLUMN = "VariationID"
_RS_COLUMN = "RS# (dbSNP)"
_NAME_COLUMN = "Name"

# RS values that mean "no dbSNP rs identifier assigned".
_NO_RS_VALUES = {"", "-1", "na", "NA"}


def _iter_clinvar_rows(clinvar_tsv):
    """Yield each ``variant_summary.txt`` row as a dict keyed by (de-``#``-ed) column name.

    Splits on tabs directly: ClinVar's ``variant_summary.txt`` is an unquoted TSV, and using ``csv`` with
    its default quoting would let a field starting with a quote silently merge across tabs/newlines. Opens
    with ``utf-8-sig`` to strip a BOM, and strips the leading ``#`` ClinVar puts on the first column name.
    """
    with open(clinvar_tsv, encoding="utf-8-sig") as inf:
        header = inf.readline().rstrip("\n").split("\t")
        header[0] = header[0].lstrip("#")  # ClinVar prefixes the first column name with '#'
        for line in inf:
            row = line.rstrip("\n").split("\t")
            if len(row) < len(header):
                continue
            yield dict(zip(header, row))


def _rs_curies(rs_value):
    """Return the list of ``DBSNP`` CURIEs for an ``RS# (dbSNP)`` value (may be comma-separated).

    The RS column holds the bare rs number(s) (e.g. ``397704705``); the DBSNP CURIE local part is
    ``rs``-prefixed (Bioregistry pattern ``^rs\\d+$``), e.g. ``DBSNP:rs397704705``. Returns ``[]`` when no
    rs id is assigned, and skips (with a warning) any token that is not ``rs`` + digits so every emitted
    CURIE is well-formed.
    """
    raw = (rs_value or "").strip()
    if raw in _NO_RS_VALUES:
        return []
    curies = []
    for part in raw.split(","):
        part = part.strip()
        if part in _NO_RS_VALUES:
            continue
        number = part[2:] if part.startswith("rs") else part
        if not number.isdigit():
            logger.warning(f"Skipping malformed dbSNP rs id {part!r} (expected rs<digits>)")
            continue
        curies.append(f"{DBSNP}:rs{number}")
    return curies


def write_clinvar_ids(clinvar_tsv, outfile):
    """Write ClinVar variations as a Babel ids file typed ``biolink:SequenceVariant``.

    Identifiers are ``CLINVAR:<VariationID>``, deduplicated by VariationID (each variation appears once per
    assembly). Raises ``RuntimeError`` if no variations are parsed (e.g. a truncated/empty download).
    """
    ensure_parent_dir(outfile)
    wrote = set()
    with open(outfile, "w", encoding="utf-8") as outf:
        for row in _iter_clinvar_rows(clinvar_tsv):
            variation_id = (row.get(_VARIATION_ID_COLUMN) or "").strip()
            if not variation_id:
                continue
            curie = f"{CLINVAR}:{variation_id}"
            if curie in wrote:
                continue
            wrote.add(curie)
            outf.write(f"{curie}\t{SEQUENCE_VARIANT}\n")
    if not wrote:
        raise RuntimeError(f"No ClinVar variations were parsed from {clinvar_tsv} (empty or truncated download?).")
    logger.info(f"Wrote {len(wrote)} ClinVar SequenceVariant identifiers from {clinvar_tsv}")


def write_clinvar_labels(clinvar_tsv, outfile):
    """Write a ``CURIE\\tlabel`` labels file for ClinVar variations (the HGVS ``Name``), one per VariationID."""
    ensure_parent_dir(outfile)
    wrote = set()
    with open(outfile, "w", encoding="utf-8") as outf:
        for row in _iter_clinvar_rows(clinvar_tsv):
            variation_id = (row.get(_VARIATION_ID_COLUMN) or "").strip()
            name = (row.get(_NAME_COLUMN) or "").strip()
            if not variation_id or not name:
                continue
            curie = f"{CLINVAR}:{variation_id}"
            if curie in wrote:
                continue
            wrote.add(curie)
            outf.write(f"{curie}\t{name}\n")
    logger.info(f"Wrote {len(wrote)} ClinVar SequenceVariant labels from {clinvar_tsv}")


def build_clinvar_dbsnp_relationships(clinvar_tsv, outfile, metadata_yaml):
    """Write ``CLINVAR:<VariationID> eq DBSNP:rs<N>`` equivalences for variations with an assigned rs id.

    Deduplicated by ``(VariationID, rs)`` edge; a variation with no rs id (``RS`` in
    ``{'', '-1', 'na', 'NA'}``) produces no edge, and a comma-separated ``RS`` yields one edge per rs id.
    """
    ensure_parent_dir(outfile)
    seen = set()
    with open(outfile, "w", encoding="utf-8") as outf:
        for row in _iter_clinvar_rows(clinvar_tsv):
            variation_id = (row.get(_VARIATION_ID_COLUMN) or "").strip()
            if not variation_id:
                continue
            clinvar_curie = f"{CLINVAR}:{variation_id}"
            for rs_curie in _rs_curies(row.get(_RS_COLUMN)):
                edge = (clinvar_curie, rs_curie)
                if edge in seen:
                    continue
                seen.add(edge)
                outf.write(f"{clinvar_curie}\teq\t{rs_curie}\n")

    write_concord_metadata(
        metadata_yaml,
        name="build_clinvar_dbsnp_relationships()",
        description=(
            f"Extracts CLINVAR<->DBSNP (rs) equivalences from the ClinVar variant_summary file ({clinvar_tsv}), "
            f"linking each ClinVar VariationID to its dbSNP rs identifier."
        ),
        sources=[
            {
                "type": "ClinVar",
                "name": "ClinVar variant_summary.txt",
                "filename": clinvar_tsv,
            }
        ],
        concord_filename=outfile,
    )
