# MP download behavior

## Source mechanism

MP data is accessed through the live UberGraph SPARQL endpoint used by Babel OBO handlers.

No standalone MP file download step is added in `datacollect.snakefile`. Instead, MP IDs and xrefs
are fetched during disease/phenotype build rules that call UberGraph-backed helpers.

## Pipeline touchpoints

- ID extraction runs via `write_mp_ids()` in `src/createcompendia/diseasephenotype.py`.
- Concord extraction runs via `build_disease_obo_relationships()` in
  `src/createcompendia/diseasephenotype.py`, which now includes an MP root traversal.

## Expected artifacts

- `babel_outputs/intermediate/disease/ids/MP`
- `babel_outputs/intermediate/disease/concords/MP`
- `babel_outputs/intermediate/disease/concords/metadata-MP.yaml`

## Failure modes

- UberGraph endpoint unavailable or timing out.
- UberGraph service-side query errors (transient HTTP 5xx).
- Upstream ontology graph changes that alter MP term/xref counts.
