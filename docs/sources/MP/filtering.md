# MP filtering and typing

## Root term

MP extraction starts from:

- `MP:0000001`

## Inclusion logic

`write_mp_ids()` collects every MP term reachable from the configured root via the default
`rdfs:subClassOf` walk and writes only MP-prefixed CURIEs to the disease/phenotype IDs file.

Unlike EMAPA (a `part_of` partonomy that requires a non-default hierarchy predicate), MP is a
standard `is_a` hierarchy, so the default `UberGraph.get_subclasses_of()` call reaches every term.

## Type assignment

All MP IDs emitted by `write_mp_ids()` are typed as:

- `biolink:PhenotypicFeature`

This reflects MP's role as a mammalian-phenotype counterpart to HPO. MP IDs are never promoted
to clique leader: `unique_prefixes` is `[MONDO, HP]`, so MONDO or HP always wins when present. MP
appears in `create_typed_sets`'s prefix-priority list only after MONDO and HP, so pure-new MP
cliques (those without a MONDO or HP partner) are typed as `biolink:PhenotypicFeature` directly
rather than via majority vote.

## Exclusions

No MP-specific exclusion roots are currently configured. The whole MP hierarchy below
`MP:0000001` is included.
