"""Parse GTDB (Genome Taxonomy Database) bacterial and archaeal taxonomy for the taxon compendium.

GTDB (https://gtdb.ecogenomic.org) provides a standardized, phylogenetically consistent taxonomy for
bacterial and archaeal genomes. Babel ingests it as a taxon vocabulary (``biolink:OrganismTaxon``) in
the existing ``taxon`` pipeline: every rank in each genome's ``gtdb_taxonomy`` string becomes a GTDB
CURIE (e.g. ``GTDB:s__Escherichia_coli``), labeled with the taxon name, and species-rank taxa are linked
to their NCBI taxonomy id (the ``ncbi_species_taxid`` metadata column) so a GTDB species resolves into
the same clique as its NCBITaxon equivalent. The bac120 (bacteria) and ar53 (archaea) metadata files are
downloaded by the ``get_gtdb_*`` rules in ``src/snakefiles/datacollect.snakefile``.

Design notes (load-bearing):

- **CURIE form.** The local part is the rank-prefixed name with spaces replaced by underscores
  (``s__Enterobacter_hormaechei_C``), matching the Bioregistry ``gtdb`` pattern ``^[cdfgops]__\\S+$``.
  The label is the name with the rank prefix removed and original spacing kept
  ("Enterobacter hormaechei_C"). Babel uses the display-cased prefix ``GTDB`` (Bioregistry's preferred
  prefix is lowercase ``gtdb``); GTDB is not yet in the Biolink Model, so there is no conflict —
  reconcile the casing if it is registered upstream.
- **``extra_prefixes=[GTDB]``.** GTDB is not in the Biolink Model's ``organism taxon`` ``id_prefixes``
  (``[NCBITaxon, MESH, UMLS]``), so ``write_compendium`` would silently drop every GTDB CURIE; the taxon
  build passes ``extra_prefixes=[GTDB]`` (the documented escape hatch).
- **Species<->NCBI is many-to-one.** Several GTDB species can share one ``ncbi_species_taxid``. ``GTDB``
  is therefore a ``unique_prefixes`` entry in the taxon build, so two GTDB taxa can never be merged
  through a shared NCBI taxid — at most one GTDB species joins a given NCBITaxon clique, the rest stay
  singletons. Higher ranks (domain..genus) have no NCBI taxid in the metadata and are exposed as labeled
  singletons.
"""

import gzip

from src.metadata.provenance import write_concord_metadata
from src.prefixes import GTDB, NCBITAXON
from src.util import ensure_parent_dir, get_logger

logger = get_logger(__name__)

# bac120/ar53_metadata.tsv column names, read by name so the parser is robust to column reordering.
_GTDB_TAXONOMY_COLUMN = "gtdb_taxonomy"
_NCBI_SPECIES_TAXID_COLUMN = "ncbi_species_taxid"

# The species rank prefix; only species-rank taxa carry an ncbi_species_taxid cross-reference.
_SPECIES_RANK_PREFIX = "s__"


def parse_gtdb_taxonomy(taxonomy_string):
    """Split a GTDB taxonomy string into ``(ranked_name, label)`` pairs, domain -> species.

    ``"d__Bacteria;...;s__Enterobacter hormaechei_C"`` yields ``("d__Bacteria", "Bacteria")`` through
    ``("s__Enterobacter_hormaechei_C", "Enterobacter hormaechei_C")``. The ``ranked_name`` is the CURIE
    local part (spaces replaced by underscores); the ``label`` is the name with the rank prefix removed
    and the original spacing kept. Malformed tokens (no ``__`` rank separator, or an empty name) are
    skipped.
    """
    taxa = []
    for token in taxonomy_string.split(";"):
        token = token.strip()
        if "__" not in token:
            continue
        rank, name = token.split("__", 1)
        if not rank or not name:
            continue
        ranked_name = f"{rank}__{name.replace(' ', '_')}"
        taxa.append((ranked_name, name))
    return taxa


def _open_metadata(path):
    """Open a GTDB metadata file whether gzipped (``.gz``) or plain TSV."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _taxonomy_and_taxid_indices(header_line):
    """Return the column indices of ``gtdb_taxonomy`` and ``ncbi_species_taxid`` from a metadata header."""
    columns = header_line.rstrip("\n").split("\t")
    return columns.index(_GTDB_TAXONOMY_COLUMN), columns.index(_NCBI_SPECIES_TAXID_COLUMN)


def _iter_metadata_rows(metadata_files):
    """Yield ``(gtdb_taxonomy, ncbi_species_taxid)`` for each genome row across the metadata files."""
    for metadata_file in metadata_files:
        with _open_metadata(metadata_file) as inf:
            taxonomy_idx, taxid_idx = _taxonomy_and_taxid_indices(inf.readline())
            needed = max(taxonomy_idx, taxid_idx)
            for line in inf:
                fields = line.rstrip("\n").split("\t")
                if len(fields) <= needed:
                    continue
                yield fields[taxonomy_idx], fields[taxid_idx]


def write_gtdb_labels(metadata_files, labels_outfile):
    """Write a ``CURIE\\tlabel`` labels file for every unique GTDB taxon (all ranks) in the metadata.

    The label is the taxon name with its rank prefix removed (original spacing). This file feeds both the
    taxon ids rule (ids are derived from its first column) and NodeFactory label assignment, mirroring
    how ``NCBITaxon/labels`` is used.
    """
    ensure_parent_dir(labels_outfile)
    seen = set()
    with open(labels_outfile, "w", encoding="utf-8") as outf:
        for taxonomy, _taxid in _iter_metadata_rows(metadata_files):
            if taxonomy in ("", "-"):
                continue
            for ranked_name, label in parse_gtdb_taxonomy(taxonomy):
                curie = f"{GTDB}:{ranked_name}"
                if curie in seen:
                    continue
                seen.add(curie)
                outf.write(f"{curie}\t{label}\n")


def build_gtdb_relationships(
    metadata_files, outfile, metadata_yaml, source_url="https://data.gtdb.ecogenomic.org/releases/latest/"
):
    """Write species-rank GTDB<->NCBITaxon equivalences from the GTDB metadata.

    The ``ncbi_species_taxid`` column is the NCBI taxonomy id GTDB assigns to a genome's species; link the
    species-rank GTDB CURIE to ``NCBITaxon:<taxid>`` so the GTDB species resolves into the NCBI taxon
    clique. Only species-rank taxa are linked (higher ranks have no NCBI taxid in the metadata). The
    mapping is many-to-one and absent for novel GTDB species; the taxon build lists ``GTDB`` in
    ``unique_prefixes`` so two GTDB species sharing an NCBI taxid are never merged (see module docstring).
    """
    ensure_parent_dir(outfile)
    seen = set()
    with open(outfile, "w", encoding="utf-8") as outf:
        for taxonomy, taxid in _iter_metadata_rows(metadata_files):
            if taxonomy in ("", "-") or taxid in ("", "-"):
                continue
            species = None
            for ranked_name, _label in parse_gtdb_taxonomy(taxonomy):
                if ranked_name.startswith(_SPECIES_RANK_PREFIX):
                    species = ranked_name
            if species is None:
                continue
            gtdb_curie = f"{GTDB}:{species}"
            ncbi_curie = f"{NCBITAXON}:{taxid}"
            edge = (gtdb_curie, ncbi_curie)
            if edge in seen:
                continue
            seen.add(edge)
            outf.write(f"{gtdb_curie}\teq\t{ncbi_curie}\n")

    write_concord_metadata(
        metadata_yaml,
        name="build_gtdb_relationships()",
        description=(
            "Extracts species-rank GTDB<->NCBITaxon equivalences from the GTDB bac120/ar53 metadata "
            f"files ({', '.join(metadata_files)}) using the ncbi_species_taxid column."
        ),
        sources=[
            {
                "type": "GTDB",
                "name": "GTDB bac120/ar53 metadata",
                "url": source_url,
            }
        ],
        concord_filename=outfile,
    )
