# EMAPA filtering and typing

## Root term

EMAPA extraction starts from:

- `EMAPA:0`

## Inclusion logic

`write_emapa_ids()` collects every EMAPA term reachable from the configured root and writes only
EMAPA-prefixed CURIEs to the anatomy IDs file.

EMAPA is a `part_of` partonomy rather than an `is_a` hierarchy, so the traversal walks `part_of`
(plus the few `is_a` links) — a `subClassOf` walk, as used for UBERON/GO/CL, reaches only a handful
of EMAPA terms.

## Type assignment

All EMAPA IDs emitted by `write_emapa_ids()` are typed as:

- `biolink:AnatomicalEntity`

This matches how EMAPA is currently used in anatomy compendium construction.

## Exclusions

No EMAPA-specific exclusion roots are currently configured.
