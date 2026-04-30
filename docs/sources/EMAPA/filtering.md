# EMAPA filtering and typing

## Root term

EMAPA extraction starts from:

- `EMAPA:0`

## Inclusion logic

Babel uses `obo.write_obo_ids()` to collect subclasses from the configured root and writes only EMAPA-prefixed CURIEs to the anatomy IDs file.

## Type assignment

All EMAPA IDs emitted by `write_emapa_ids()` are typed as:

- `biolink:AnatomicalEntity`

This matches how EMAPA is currently used in anatomy compendium construction.

## Exclusions

No EMAPA-specific exclusion roots are currently configured.
