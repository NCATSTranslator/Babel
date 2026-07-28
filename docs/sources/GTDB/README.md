# GTDB

[GTDB](https://gtdb.ecogenomic.org) (the Genome Taxonomy Database) is a standardized,
phylogenetically consistent taxonomy for bacterial and archaeal genomes. Babel ingests it as a taxon
vocabulary
([`biolink:OrganismTaxon`](https://biolink.github.io/biolink-model/docs/OrganismTaxon.html)) in the
existing `taxon` pipeline, alongside NCBITaxon/MeSH/UMLS.

The handler is `src/datahandlers/gtdb.py`; the rules are `get_gtdb_bac120` / `get_gtdb_ar53`
(download, `src/snakefiles/datacollect.snakefile`) and `gtdb_labels` / `gtdb_ids` /
`get_gtdb_relationships` (`src/snakefiles/taxon.snakefile`).

## What is ingested

GTDB's `bac120_metadata.tsv.gz` (bacteria) and `ar53_metadata.tsv.gz` (archaea) carry one row per
genome. Two columns are read **by name** (robust to column reordering):

- `gtdb_taxonomy` — the classification string, e.g.
  `d__Bacteria;p__Pseudomonadota;...;s__Enterobacter hormaechei_C`.
- `ncbi_species_taxid` — the NCBI taxonomy id GTDB assigns to that genome's species.

Every rank in `gtdb_taxonomy` becomes a GTDB CURIE: the local part is the rank-prefixed name with
spaces replaced by underscores (`GTDB:s__Enterobacter_hormaechei_C`), matching the Bioregistry
`gtdb` pattern `^[cdfgops]__\S+$`. The label is the name with the rank prefix removed and original
spacing kept ("Enterobacter hormaechei_C"). Species-rank taxa are linked `eq` to
`NCBITaxon:<ncbi_species_taxid>` so a GTDB species resolves into the same clique as its NCBI
equivalent; higher ranks (domain..genus) have no NCBI taxid in the metadata and are exposed as
labeled singletons.

## Design constraints (load-bearing)

- **`extra_prefixes=[GTDB]`.** GTDB is not in the Biolink Model's `organism taxon` `id_prefixes`
  (`[NCBITaxon, MESH, UMLS]`), so `write_compendium` would silently drop every GTDB CURIE; the taxon
  build passes `extra_prefixes=[GTDB]` (the documented escape hatch). Filing GTDB with the Biolink
  team is the long-term fix.
- **`GTDB` is a `unique_prefixes` entry.** The GTDB↔NCBI species mapping is many-to-one (several
  GTDB species can share one `ncbi_species_taxid`). Listing `GTDB` as unique means two GTDB species
  can never be merged through a shared NCBI taxid — at most one GTDB species joins a given NCBITaxon
  clique, the rest stay singletons. Which species wins is first-genome-in-file-order (deterministic
  but arbitrary). This is conservative: it avoids incorrect merges at the cost of linking only one
  GTDB species per NCBI taxid.
- **Prefix casing.** Babel uses the display-cased prefix `GTDB`; Bioregistry's preferred prefix is
  lowercase `gtdb`. GTDB is not yet in the Biolink Model, so there is no conflict — reconcile the
  casing if it is registered upstream.

## Caveats

- **License:** GTDB is CC-BY-SA-4.0 (share-alike) — confirm this is acceptable for Babel's
  downstream redistribution before release.
- **Novel species:** GTDB species clusters with no NCBI equivalent (and many higher-rank taxa) form
  standalone cliques; they still get labels but no NCBI linkage.
- **Reproducibility:** `gtdb_metadata_url_prefix` defaults to GTDB's `releases/latest/`; pin a
  specific release (e.g. `.../releases/release232/232.0/`) for a reproducible production build.

## Registration in the build

`GTDB` is in `taxon_labels`, `taxon_ids`, and `taxon_concords` in `config.yaml`; the GTDB concord
flows through the taxon compendium (`OrganismTaxon.txt`) and hence the DuckDB/KGX/Parquet/report
exports like every other taxon source.

## Related

- `src/datahandlers/gtdb.py` — `parse_gtdb_taxonomy`, `write_gtdb_labels`,
  `build_gtdb_relationships`.
- `src/createcompendia/taxon.py` — `build_compendia` (`extra_prefixes=[GTDB]`, `GTDB` in
  `unique_prefixes`).
- `tests/datahandlers/test_gtdb.py` — offline unit tests over `tests/data/gtdb_metadata_sample.tsv`
  (verbatim, all 113 metadata columns).
