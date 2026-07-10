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

- **EMAPA asserts no outgoing mapping triples at all**, so the concord file is empty in practice
  — a local `anatomy` build produces a zero-line
  `babel_outputs/intermediate/anatomy/concords/EMAPA`. This is not limited to `hasDbXref`:
  as of the 2026-07 UberGraph snapshot, EMAPA terms assert no `oboInOwl:hasDbXref` and no
  `skos:exactMatch`/`closeMatch`/`broadMatch`/`narrowMatch` either.
- EMAPA's links to the rest of the anatomy graph are asserted entirely **from the UBERON side**:
  UBERON asserts 4,356 `hasDbXref` triples pointing at EMAPA, covering 4,201 distinct UBERON
  terms and 4,330 distinct EMAPA terms. Because `build_sets()` keys its output file by the
  *subject's* prefix, those rows land in the `UBERON` concord, never the `EMAPA` one.
- Consequently `write_emapa_ids()` is the load-bearing half of this ingest: it contributes the
  ~8,000 EMAPA identifiers, and its `part_of` traversal is what makes them visible at all. The
  `hierarchy_predicate` plumbing on `build_sets()` / `get_subclasses_and_xrefs()` currently has
  no production effect for EMAPA, since there are no xrefs to walk to. It is retained (guarded
  by a `ValueError` and a unit test) so the ingest stays correct if EMAPA ever adds xrefs.
- 116 UBERON terms cross-reference more than one EMAPA term. Since `EMAPA` is listed in
  `anatomy_unique_prefixes`, each of those merges is deliberately blocked, and this is the single
  biggest driver of the before/after clique counts in the source-impact report. (Only 5 EMAPA
  terms are referenced from more than one UBERON term, so the asymmetry runs one way.)
- Mapping coverage depends on UberGraph content and can change across updates. If EMAPA ever
  starts asserting xrefs, revisit whether the concord should use a fail-closed
  `allowed_prefixes` allowlist (as MP does) rather than the fail-open `ANATOMY_OBO_IGNORE_LIST`.
- Some endpoint responses may be transiently unavailable; tests treat server-side issues as xfail
  where appropriate.
