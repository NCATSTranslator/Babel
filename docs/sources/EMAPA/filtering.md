# EMAPA filtering and typing

## Root term

EMAPA extraction starts from:

- [`EMAPA:0`](http://purl.obolibrary.org/obo/EMAPA_0) "Anatomical structure"

## Inclusion logic

`write_emapa_ids()` collects every EMAPA term reachable from the configured root and writes only
EMAPA-prefixed CURIEs to the anatomy IDs file.

EMAPA is a `part_of` partonomy rather than an `is_a` hierarchy, so the traversal walks `part_of`
(plus the few `is_a` links) — a `subClassOf` walk, as used for UBERON/GO/CL, reaches only a handful
of EMAPA terms.

## Type assignment

`write_emapa_ids()` assigns one biolink type per CURIE (written in column 2 of the anatomy
IDs file):

- Terms at or below [`EMAPA:35949`](http://purl.obolibrary.org/obo/EMAPA_35949) "organ" or
  [`EMAPA:35868`](http://purl.obolibrary.org/obo/EMAPA_35868) "tissue" — including the two
  roots themselves — are typed as `biolink:GrossAnatomicalStructure`. Gross typing takes
  precedence when a term falls under both subtrees.
- Every other EMAPA term defaults to `biolink:AnatomicalEntity`.

The gross/anatomical subtrees are found the same way the root set is: the `part_of` closure
(plus the few `is_a` links) of each root.

### Biolink Model registration caveat

`EMAPA` is in the Biolink Model's `id_prefixes` list for `AnatomicalEntity` but **not** for
`GrossAnatomicalStructure`. `NodeFactory.create_node()` drops identifiers whose prefix is not
permitted for a clique's biolink class, so EMAPA terms typed as gross are not written to the
compendium until `EMAPA` is added to `GrossAnatomicalStructure`'s `id_prefixes`. The
source-impact report flags these with `would_be_added = false` /
`needs_biolink_registration = true`; see `docs/AddingNewSources.md`.

## Exclusions

No EMAPA-specific exclusion roots are currently configured.
