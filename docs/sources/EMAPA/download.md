# EMAPA download behavior

## Source mechanism

EMAPA data is accessed through the live UberGraph SPARQL endpoint used by Babel OBO handlers.

No standalone EMAPA file download step is added in `datacollect.snakefile`. Instead, EMAPA IDs and xrefs are fetched during anatomy build rules that call UberGraph-backed helpers.

## Pipeline touchpoints

- ID extraction runs via `write_emapa_ids()` in `src/createcompendia/anatomy.py`.
- Concord extraction runs via `build_anatomy_obo_relationships()` in `src/createcompendia/anatomy.py`, which now includes an EMAPA root traversal.

## Expected artifacts

- `babel_outputs/intermediate/anatomy/ids/EMAPA`
- `babel_outputs/intermediate/anatomy/concords/EMAPA`
- `babel_outputs/intermediate/anatomy/concords/metadata-EMAPA.yaml`

## Failure modes

- UberGraph endpoint unavailable or timing out.
- UberGraph service-side query errors (transient HTTP 5xx).
- Upstream ontology graph changes that alter EMAPA subclass/xref counts.
