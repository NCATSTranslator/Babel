# MP mappings

## Mapping source

MP mappings in this integration are pulled exclusively from UberGraph xrefs using
`build_sets(..., set_type="xref")` from the MP root in disease/phenotype compendium assembly.
SSSOM mappings from the Mouse-Human Ontology Mapping Initiative are **intentionally not loaded**.
See "SSSOM history and known failure modes" below for the reasoning.

## Output format

The MP concord file is tab-separated triples:

- `<MP_CURIE>  xref  <OTHER_CURIE>`

and is written to:

- `babel_outputs/intermediate/disease/concords/MP`

## Current behavior

- Rows are generated from MP terms reachable by `rdfs:subClassOf` from `MP:0000001`.
- Only normalized CURIE-style xrefs are retained.
- No additional `other_prefixes` mapping is configured today — UberGraph's default xref output is
  trusted as-is. If review of the impact report shows xref namespaces that should be aliased
  (e.g. MSH → MESH), they can be added in a follow-up the same way `build_disease_obo_relationships`
  does for HPO.

## SSSOM history and known failure modes

A prior attempt to add MP (PR #300, branch `add-mammal-phenotype-ontology`, unmerged) combined
the UberGraph xref path above with SSSOM mapping sets from the
[Mouse-Human Ontology Mapping Initiative](https://github.com/mapping-commons/mh_mapping_initiative).
Seven SSSOM files were loaded with a confidence filter of 0.8 and an allowlist of
`skos:exactMatch`, `skos:closeMatch`, and `skos:relatedMatch`. That richer mapping set produced
controversial clique merges that could not be adjudicated without SME input, and the PR stalled.

Two concrete cases from that work, kept here as a regression watchlist:

- **`MP:0003342` "accessory spleen"** was cliqued with **`HP:0001748` "Polysplenia"**, a different
  human-phenotype term. The correct partner is `HP:0001747` "Accessory spleen". The error
  originated in an SSSOM "broad"-style mapping that conflated the two HP concepts. UberGraph
  alone does not assert this bridge, so the UberGraph-only path used in this PR avoids the
  failure — but a future SSSOM re-introduction must vet the broad-mapping predicate filter.

- **`MP:0001914` "hemorrhage"** was *not* cliqued with **`NCIT:C26791` "Hemorrhage"** even though
  the two concepts genuinely correspond. The bridge runs through EFO, and EFO is not loaded into
  UberGraph, so the equivalent xref is invisible to this pipeline. This is a coverage gap, not a
  correctness bug; a SSSOM path could close it but would have to be balanced against the
  accessory-spleen-class risk.

## How to use the impact report

The committed `impact-report.md` is the artefact intended to drive SME conversation about
revisiting SSSOM:

- Section 4 ("Clique impact") shows pure-new MP cliques (those without an HP/NCIT/MONDO partner),
  expanded existing cliques (MP joining an existing cluster), and any merges (MP bridging two
  previously-separate cliques). Sample merge entries are the most diagnostic — they're the
  candidates a reviewer should sanity-check against the actual concepts.
- If the sample merges look clean under UberGraph-only, SSSOM may be safe to add back with
  appropriate filtering.
- If sample merges include implausible bridges, that is itself useful evidence about which xref
  namespaces are over-promiscuous in MP's UberGraph profile and should be added to ignore lists.

This document should be revisited after that SME review.

## Caveats

- Mapping coverage depends on UberGraph content and can change across updates. Watch for shifts
  in MP↔MESH and MP↔SNOMED counts when MP is upgraded.
- Some endpoint responses may be transiently unavailable; tests treat server-side issues as xfail
  where appropriate.
