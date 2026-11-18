# UNII

The FDA's Unique Ingredient Identifiers, from the Global Substance Registration System (GSRS).
`pull_unii()` (`src/datahandlers/unii.py`) downloads two files from
<https://precision.fda.gov/uniisearch/archive>:

- `Latest_UNII_Names.txt`: names and synonyms, which become UNII's labels and synonyms.
- `Latest_UNII_Records.txt`: one row per UNII, with the substance's cross-references to other
  databases (PubChem, CAS, NCIt, RxNorm, NCBI Taxonomy, …), its InChIKey where it has a defined
  structure, and a `SUBSTANCE_TYPE` (`chemical`, `protein`, `mixture`, `polymer`, `nucleicAcid`,
  `structurallyDiverse`, …).

## How the chemical pipeline uses it

- **Identifiers** — `chemicals.write_unii_ids()` writes every UNII except organisms and crude
  organism-derived substances, which it recognises by a populated `NCBI`, `PLANTS`, `GRIN` or `MPNS`
  column (`UNII_ORGANISM_COLUMNS`).
- **Structure links** — UniChem's FDA source links a UNII to its InChIKey, which is how most UNIIs
  join their clique.
- **PubChem links** — `chemicals.write_unii_records_concords()` writes the records file's `PUBCHEM`
  column as the `UNII_PUBCHEM` concord. This is what joins a UNII that UniChem can't link by
  structure, such as a protein, a mixture or an oligonucleotide, to the PubChem record for the same
  substance. Polymers are skipped, because PubChem represents a polymer by its monomers. A value
  that isn't a canonical CID or a CAS number is skipped and counted in the concord's metadata YAML,
  and more than `UNII_RECORDS_MAX_MALFORMED_VALUES` of them in one column fails the rule. The same
  function writes the `RN` column as `UNII_CAS`, which the build does not use. Both decisions were
  measured against 2026jul22, and [records-xrefs/](./records-xrefs/README.md) holds the
  measurement.
- **Typing** — the DrugBank food-and-extract retype uses a UNII's NCIt class and plant flags
  (`read_unii_flags()`); see
  [`../DRUGBANK/food-and-extracts/`](../DRUGBANK/food-and-extracts/README.md).

The records file's other cross-reference columns (`RXCUI`, `NCIT`, `EPA_CompTox`, `DAILYMED`, …)
are not read as concords.
