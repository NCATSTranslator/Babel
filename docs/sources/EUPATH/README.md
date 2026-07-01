# EUPATH via the manual compendium

`EUPATH` is not yet a normal downloaded/parsed Babel source. Babel currently exposes EUPATH
through the manual compendium described in [`../MANUAL/README.md`](../MANUAL/README.md).

This is the current hand-curated EUPATH entry:

- [`EUPATH:0009259`](http://purl.obolibrary.org/obo/EUPATH_0009259)
  "Shannon-indexed alpha diversity data"
- Biolink type: `biolink:ClinicalFinding`

Its synonyms currently come from the `alternatives` list in `input_data/manual_terms.ndjson`.

## Where it lives

- `input_data/manual_terms.ndjson` — the current EUPATH line is maintained here
- `config.yaml` — `manual_prefixes: [EUPATH]`
- `src/createcompendia/manual.py` — parses the term and builds the clique
- `src/snakefiles/manual.snakefile` — builds the manual compendium outputs

## How EUPATH names are surfaced

When the manual rules run, Babel generates the per-prefix files that the normal synonym pipeline
expects:

- `babel_downloads/EUPATH/labels`
- `babel_downloads/EUPATH/synonyms`

The preferred label is written to both files; every listed alternative is written to the
`synonyms` file as `HAS_EXACT_SYNONYM`.

## How EUPATH reaches final outputs

The EUPATH term is emitted only when the manual compendium is opted in with
`--config unstable=true`.

That build path produces:

- `babel_outputs/compendia/Manual.txt`
- `babel_outputs/synonyms/Manual.txt`
- `babel_outputs/metadata/Manual.txt.yaml`

The EUPATH term currently forms a singleton clique, but the manual schema also supports optional
`equivalents` for future multi-CURIE manual cliques.

## Future work

If EUPATH needs broader coverage, a dedicated source ingest may eventually replace or supplement
this path. Until then, additional EUPATH entries can be added by appending new lines to
`input_data/manual_terms.ndjson`.
