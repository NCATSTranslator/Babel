# EMAPA mappings

## Mapping source

EMAPA mappings are pulled from UberGraph xrefs using `build_sets(..., set_type=\"xref\")` in anatomy
compendium assembly.

## Output format

The EMAPA concord file is tab-separated triples:

- `<EMAPA_CURIE>  xref  <OTHER_CURIE>`

and is written to:

- `babel_outputs/intermediate/anatomy/concords/EMAPA`

## Current behavior

- Rows are generated from EMAPA terms reachable by `part_of` from `EMAPA:0` (EMAPA is a
  partonomy, so the xref walk uses `part_of` rather than `subClassOf`).
- Only normalized CURIE-style xrefs are retained.
- Prefixes in anatomy ignore-lists are excluded from output.

## Caveats

- EMAPA asserts no `hasDbXref` annotations in current UberGraph snapshots, so the concord file is
  empty in practice. EMAPA's links to the rest of the anatomy graph are instead asserted from the
  UBERON side (UBERON cross-references many EMAPA terms).
- Mapping coverage depends on UberGraph content and can change across updates.
- Some endpoint responses may be transiently unavailable; tests treat server-side issues as xfail
  where appropriate.
