# Babel Downloads

Babel downloads are available at <https://stars.renci.org/var/babel/> with subdirectories for each release. Significant
releases are documented in the [Releases lists](../releases/README.md).

There are several different Babel outputs that we make available for download:

* The `compendia/`, `synonyms/` and `conflation/` files that are the core
  [Babel outputs](BabelOutputs.md).
* The `duckdb/` directory contains various DuckDB databases and Apache Parquet exports that can be
  used to query the Babel outputs more efficiently than searching through the individual JSON files.
* The `metadata/` directory contains metadata reports for every compendium file. It is generated
  from the metadata files for intermediate outputs for each file and is intended to capture all the
  provenance information for every Babel run, but currently only includes metadata on concords, not
  [individual identifiers](https://github.com/NCATSTranslator/Babel/issues/648).
* The `kgx/` directory contains the compendia files in the
  [Knowledge Graph Exchange (KGX) format](https://github.com/biolink/kgx).
* The `sapbert-training-data/` directory contains the training data for the
  [Babel-SAPBERT tool](https://github.com/renci-ner/sapbert).
* The `reports/` files are various reports generated to summarize the outputs.
  * `reports/content` directory contains JSON files summarizing the contents of the compendia files
    by prefix.
  * `reports/duckdb` directory contains reports generated from the DuckDB databases.
  * `reports/tables` consist of CSV tables that summarize the outputs and are used in the Babel
    paper.
* The `config.yaml` file used to generate the outputs.
* The `logs/` files are produced as the pipeline runs, although logs for runs that succeed are
  deleted to save space.
* The `intermediate/` files are produced as the pipeline runs, and may provide clues as to how the
  outputs were generated.
