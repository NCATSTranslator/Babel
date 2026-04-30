# EMAPA mappings

## Mapping source

EMAPA mappings are pulled from UberGraph xrefs using `build_sets(..., set_type=\"xref\")` in anatomy compendium assembly.

## Output format

The EMAPA concord file is tab-separated triples:

- `<EMAPA_CURIE>  xref  <OTHER_CURIE>`

and is written to:

- `babel_outputs/intermediate/anatomy/concords/EMAPA`

## Current behavior

- Rows are generated from EMAPA subclasses under `EMAPA:0`.
- Only normalized CURIE-style xrefs are retained.
- Prefixes in anatomy ignore-lists are excluded from output.

## Caveats

- Mapping coverage depends on UberGraph content and can change across updates.
- Some endpoint responses may be transiently unavailable; tests treat server-side issues as xfail where appropriate.
