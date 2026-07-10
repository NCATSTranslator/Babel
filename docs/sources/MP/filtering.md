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

This reflects MP's role as a mammalian-phenotype counterpart to HPO. `classify_disease_clique`
(used by both `create_typed_sets` and the source-impact report) still checks prefixes in the order
MONDO, then HP, then MP, so a clique carrying any of those always takes that prefix's declared
type over a majority vote; a pure-MP clique (no MONDO/HP partner) is typed as
`biolink:PhenotypicFeature` directly through this same precedence.

MP can still be promoted to clique leader (preferred identifier). Since MP and HP are kept
disjoint (see [`disjointness.md`](disjointness.md)), no clique can contain both, so HP never
competes with MP for leadership. In the Biolink Model's `id_prefixes` order for
`biolink:PhenotypicFeature`, MP ranks below HP, EFO, NCIT, UMLS, and MEDDRA but above ZP, SNOMEDCT,
MESH, and the rest — so MP wins leadership of any `PhenotypicFeature` clique that lacks an
EFO/NCIT/UMLS/MEDDRA partner (which, for the MP-bearing cliques MP itself contributes, is most of
them).

## Exclusions

No MP-specific exclusion roots are currently configured. The whole MP hierarchy below
`MP:0000001` is included.
