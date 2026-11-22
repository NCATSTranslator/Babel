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

`EMAPA` is in the Biolink Model's `id_prefixes` list for **both** `AnatomicalEntity` and
`GrossAnatomicalStructure`, so every EMAPA identifier this pipeline types survives
`write_compendium()`. All 8,078 reach a compendium: 2,787 in `AnatomicalEntity.txt` and 5,291 in
`GrossAnatomicalStructure.txt`.

The caveat is the two anatomy classes EMAPA is **not** registered for: `Cell` and
`CellularComponent`. `NodeFactory.create_node()` drops identifiers whose prefix is not permitted
for a clique's biolink class, silently — so an EMAPA term pulled into a cell or cellular-component
clique by a bad cross-reference disappears from every compendium, and a clique diff cannot see it
(a CURIE absent from both sides is not a difference). That is how
[`EMAPA:18428`](http://purl.obolibrary.org/obo/EMAPA_18428) "adrenal medulla" and
[`EMAPA:16112`](http://purl.obolibrary.org/obo/EMAPA_16112) "chorion" were being lost until
`input_data/anatomy_badxrefs.txt` broke the two merges responsible.

The source-impact report flags this class of loss per identifier with `would_be_added = false` /
`needs_biolink_registration = true`; see `docs/AddingNewSources.md`.

## Exclusions

No EMAPA-specific exclusion roots are currently configured.
