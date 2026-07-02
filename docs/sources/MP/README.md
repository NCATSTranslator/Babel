# MP source notes

MP (Mammalian Phenotype Ontology) is used in Babel as a disease/phenotype source for
mammalian — primarily mouse — phenotypes.

In this integration, Babel:

- extracts MP identifiers for disease/phenotype processing;
- exports MP xref concords from UberGraph;
- includes MP in disease/phenotype compendium merge inputs;
- keeps MP **disjoint from HP**: no clique may contain both an HP and an MP identifier (MP may
  still merge with non-HP disease ids such as MONDO/MESH). See [`disjointness.md`](disjointness.md)
  for the post-glom split that enforces this and the before/after clique impact;
- keeps MP **disjoint from EFO** as well, but by filtering EFO's untrusted direct EFO→MP xrefs out
  of `concords/EFO` at the source (`EFO_EXCLUDED_XREF_PREFIXES = [MP]`) rather than a post-glom
  split, since EFO term species-scope is ambiguous. See [`disjointness.md`](disjointness.md);
- tags every ingested MP identifier with the taxon
  [`NCBITaxon:40674`](http://purl.obolibrary.org/obo/NCBITaxon_40674) "Mammalia" via a
  `babel_downloads/MP/taxa` file, so each MP identifier carries a `t` field in the compendia. The
  taxa file is derived directly from the MP ids file (rule `disease_mp_taxa`, configured by
  `disease_phenotype_taxa` in `config.yaml`), so it covers exactly the identifiers Babel ingests.
  Because MP and HP are kept disjoint, an MP clique carries only
  [`NCBITaxon:40674`](http://purl.obolibrary.org/obo/NCBITaxon_40674) "Mammalia" (it never shares a
  clique with an HP identifier carrying
  [`NCBITaxon:9606`](http://purl.obolibrary.org/obo/NCBITaxon_9606) "Homo sapiens").

Related implementation files:

- `src/createcompendia/diseasephenotype.py`
- `src/snakefiles/diseasephenotype.snakefile`
- `config.yaml`

Additional source details are documented in:

- `download.md`
- `filtering.md`
- `mappings.md`
- `disjointness.md` (how MP is kept disjoint from HP, with the before/after clique impact)
- `impact-report.md` (auto-generated; see "Adding a new data source" in
  `CLAUDE.md` for how to regenerate it)
