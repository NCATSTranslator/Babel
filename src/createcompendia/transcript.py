"""Build the Transcript compendium: Ensembl transcript identifiers (ENST*) as biolink:Transcript.

Babel historically downloaded transcript identifiers but parsed them away: NCBI's ``gene2ensembl.gz``
carries an ``Ensembl_rna_identifier`` column (col 4) that ``gene.build_gene_ncbi_ensembl_relationships``
never reads (it uses only the gene columns), and ``UniProtKB/idmapping.dat`` ``Ensembl_TRS`` rows are
similarly dropped by ``protein.build_protein_uniprotkb_ensemble_relationships``. This module exposes
those Ensembl transcript identifiers as a first-class ``biolink:Transcript`` compendium, resolving the
transcript checkbox in https://github.com/NCATSTranslator/Babel/issues/84.

Design notes (load-bearing — read before changing):

- **Transcripts live in their own compendium.** ``ENSEMBL`` is shared by the Gene, Protein, and
  Transcript ``id_prefixes``, and two compendia must never share an identifier, so ENST identifiers are
  built here in an isolated pipeline rather than added to the gene/protein concords.
- **No transcript<->gene or transcript<->protein edges here.** ``glom`` merges *every* concord pair
  regardless of the relation column (``eq`` and ``xref`` alike), so a transcript<->gene concord would
  pull the transcript into a gene clique and mis-type it as ``biolink:Gene``. The only concord this
  module writes is the transcript-internal versioned<->unversioned equivalence (the issue #72 pattern),
  which lets a versioned query (``ENST00000263368.3``) normalize into the same clique as the stable
  unversioned id (``ENST00000263368``). Cross-granularity transcript<->gene/protein relationships are a
  deliberate follow-up (they are not equivalences); the source data for them is already on disk.
- **``ENSEMBL`` is registered for ``biolink:Transcript``** in the pinned Biolink Model (4.4.3
  ``id_prefixes: [ENSEMBL, FB]``), so no ``extra_prefixes`` escape hatch is needed.
- **``ENSEMBL`` is deliberately NOT a ``unique_prefixes`` entry** for this compendium: a transcript
  clique legitimately holds the versioned and unversioned ENST together.
- **v1 transcript cliques are unlabeled.** Ensembl assigns no labels or synonyms to its gene/transcript
  identifiers (see ``src/datahandlers/ensembl.py``), and the versioned<->unversioned concord has no
  labeled partner, so every Transcript node currently ships with an empty label. Labels arrive with the
  deferred transcript<->gene/protein relationships (e.g. via HGNC's ``ensembl_transcript_id``).

v1 sources the transcript set from ``gene2ensembl.gz`` alone (the richest already-downloaded source).
Coverage follow-ups: ``idmapping.dat`` ``Ensembl_TRS``, the BioMart/MyGene ``ensembl_transcript_id``
attribute, and RefSeq RNA accessions (``NM_``/``NR_`` — deferred because no prefix is registered for
them on ``biolink:Transcript``).
"""

import gzip
import re

from src.babel_utils import write_compendium
from src.categories import TRANSCRIPT
from src.metadata.provenance import write_concord_metadata
from src.model.cliques import glom_from_files
from src.prefixes import ENSEMBL
from src.util import ensure_parent_dir, get_logger

logger = get_logger(__name__)

# gene2ensembl.gz column index of the Ensembl transcript identifier (Ensembl_rna_identifier).
# Header: #tax_id GeneID Ensembl_gene_identifier RNA_nucleotide_accession.version
#         Ensembl_rna_identifier protein_accession.version Ensembl_protein_identifier
_ENSEMBL_RNA_COLUMN = 4

# Matches a versioned Ensembl id (ENST00000263368.3) and captures the unversioned form
# (ENST00000263368). Same pattern the gene/protein modules use (issue #72).
_VERSION_RE = re.compile(r"^([A-Z]+\d+)\.\d+")


def _iter_ensembl_transcripts(infile):
    """Yield ``(versioned, unversioned)`` Ensembl transcript id pairs from NCBI ``gene2ensembl.gz``.

    ``gene2ensembl.gz`` is a gzipped TSV; column 4 (``Ensembl_rna_identifier``) is the transcript,
    versioned (e.g. ``ENST00000263368.3``), with ``-`` marking an absent value. Yields one pair per row
    that has a transcript, where ``unversioned`` strips the trailing ``.N``. Rows without a transcript
    are skipped.
    """
    with gzip.open(infile, "rt", encoding="utf-8") as inf:
        _header = inf.readline()
        for line in inf:
            fields = line.strip().split("\t")
            if len(fields) <= _ENSEMBL_RNA_COLUMN:
                continue
            rna_id = fields[_ENSEMBL_RNA_COLUMN]
            if rna_id in ("", "-"):
                continue
            match = _VERSION_RE.match(rna_id)
            unversioned = match.group(1) if match else rna_id
            yield rna_id, unversioned


def write_transcript_ids(infile, outfile):
    """Write Ensembl transcript identifiers from ``gene2ensembl.gz`` as a Babel ids file.

    Each identifier is the *unversioned* ENST (the stable form) with a ``biolink:Transcript`` type hint
    in column 2; the versioned<->unversioned equivalence is added by
    :func:`build_transcript_ensembl_relationships`. Identifiers are deduplicated (the same unversioned
    ENST appears once per transcript version and once per RefSeq match).
    """
    ensure_parent_dir(outfile)
    wrote = set()
    with open(outfile, "w") as outf:
        for _versioned, unversioned in _iter_ensembl_transcripts(infile):
            curie = f"{ENSEMBL}:{unversioned}"
            if curie in wrote:
                continue
            wrote.add(curie)
            outf.write(f"{curie}\t{TRANSCRIPT}\n")


def build_transcript_ensembl_relationships(infile, outfile, metadata_yaml):
    """Write versioned<->unversioned Ensembl transcript equivalences from ``gene2ensembl.gz``.

    ``gene2ensembl.gz`` reports versioned transcript ids; the ids file carries the unversioned form, so
    this concord links each versioned id to its unversioned equivalent (issue #72 pattern) so a versioned
    query normalizes into the same clique. Only transcript-internal equivalences are written — see the
    module docstring for why transcript<->gene/protein edges are excluded.
    """
    ensure_parent_dir(outfile)
    wrote = set()
    with open(outfile, "w") as outf:
        for versioned, unversioned in _iter_ensembl_transcripts(infile):
            if versioned == unversioned:
                continue  # an unversioned id needs no versioned<->unversioned edge
            versioned_curie = f"{ENSEMBL}:{versioned}"
            unversioned_curie = f"{ENSEMBL}:{unversioned}"
            edge = (versioned_curie, unversioned_curie)
            if edge in wrote:
                continue
            wrote.add(edge)
            outf.write(f"{versioned_curie}\teq\t{unversioned_curie}\n")

    write_concord_metadata(
        metadata_yaml,
        name="build_transcript_ensembl_relationships()",
        description=(
            f"Extracts versioned<->unversioned Ensembl transcript equivalences from the NCBIGene "
            f"gene2ensembl.gz file ({infile})."
        ),
        sources=[
            {
                "type": "NCBIGENE",
                "name": "NCBIGene gene2ensembl.gz",
                "filename": infile,
            }
        ],
        concord_filename=outfile,
    )


def compute_cliques_for_impact_report(concordances, identifiers, excluded_sources=()):
    """Build the Transcript clique state in memory without writing compendia.

    Shaped for registration in the source-impact report's ``PIPELINE_CONFIG`` (see
    ``docs/AddingNewSources.md`` step 8) but not yet registered, so the report does not currently cover
    transcript. ``excluded_sources`` lets the report compute the before-new-source state once registered.
    """
    return glom_from_files(concordances, identifiers, unique_prefixes=[], excluded_sources=excluded_sources)


def build_compendia(concordances, metadata_yamls, identifiers, icrdf_filename):
    """Glom the Transcript ids and concords and write ``Transcript.txt``.

    :param concordances: list of concord files (versioned<->unversioned ENST equivalences).
    :param metadata_yamls: per-concord provenance YAMLs.
    :param identifiers: list of ids files (unversioned ENST typed biolink:Transcript).
    :param icrdf_filename: the icRDF file passed through to ``write_compendium``.
    """
    dicts, _types = compute_cliques_for_impact_report(concordances, identifiers)
    transcript_sets = set(frozenset(clique) for clique in dicts.values())
    baretype = TRANSCRIPT.split(":")[-1]  # "Transcript"
    write_compendium(metadata_yamls, transcript_sets, f"{baretype}.txt", TRANSCRIPT, {}, icrdf_filename=icrdf_filename)
