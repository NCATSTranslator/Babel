# UMLS semantic-type mappings

Every UMLS concept (CUI) is assigned a Biolink Model class based on its UMLS **semantic type**.
This document describes where those assignments live, how to change one, and how Babel tracks the
places where it deliberately disagrees with the Biolink Model.

## The single source of truth

All UMLS semantic-type to Biolink-class logic lives in
`src/datahandlers/umls/semantic_types.py`. The canonical key is the UMLS semantic-type **tree
number** (the `STN` column of `MRSTY.RRF`, e.g. `A1.4.1.2.1.7`), because the same tree-number style
of key is used across MeSH and UMLS partitioning and is what the historical partition maps used.

### SEMANTIC_NETWORK

`SEMANTIC_NETWORK` is a hardcoded table of all 127 UMLS semantic types: `TUI -> (tree_number,
name)`. The UMLS Semantic Network changes very rarely between releases, so it is embedded in the
module to keep it usable offline (unit tests do not need the multi-hundred-MB `MRSTY.RRF`). It is
the bridge between the tree numbers Babel uses internally and the TUIs the Biolink Model keys on
(`STY:T###`). Helpers: `tui_to_tree_number`, `tree_number_to_tui`, `tree_number_name`.

A `--pipeline` drift test (`tests/pipeline/test_umls.py::test_semantic_network_matches_mrsty`)
re-derives this table from the live `MRSTY.RRF` and fails if UMLS ever changes it, so we notice at
upgrade time. If it fails, regenerate `SEMANTIC_NETWORK` from `babel_downloads/UMLS/MRSTY.RRF`
(columns `TUI|STN|STY`) and review whether any partition assignment needs to change.

### UMLS_TYPE_MAP

`UMLS_TYPE_MAP` maps each tree number to a `UMLSTypeAssignment`:

- `biolink_type` — the Biolink class Babel **actually assigns** to CUIs of this type.
- `compendium` — which `createcompendia` module owns CUIs of this type (`"chemicals"`,
  `"protein"`, `"anatomy"`, `"diseasephenotype"`, `"process"`, `"taxon"`, `"gene"`), or `None` for a
  leftover-only entry.
- `proposed_biolink_type` — set this when Babel argues the Biolink **Model itself** should map this
  semantic type differently. Drives the redundancy test below. May equal `biolink_type` (we applied
  our preferred type and want the Model to follow) or differ (a proposal we have not yet applied).
- `issue` — a GitHub issue URL, required whenever `proposed_biolink_type` is set.
- `allow_xfail_when_adopted`, `note`.

The registry is validated at import: each tree number appears exactly once (so no tree number can be
claimed by two compendia), every Biolink class is a known `src/categories.py` constant, and every
proposed change carries a tracking issue.

## How the registry is consumed

- **Partition maps.** Each `createcompendia/*.py` `write_umls_ids()` calls
  `category_map_for("<compendium>")` to get its `{tree_number: biolink_type}` map and passes it to
  `umls.write_umls_ids()`. Per-compendium **blocklists** (e.g. chemicals excluding the protein
  trees, diseasephenotype's bad-CUI list) stay local to each module — they are component-specific
  exclusion logic, not type assignments.
- **Leftover catch-all.** `createcompendia/leftover_umls.py` types the residual CUIs (those no typed
  compendium claimed) with `resolve_biolink_types()`, which resolves each TUI registry-first and
  falls back to the Biolink Model's `get_element_by_mapping("STY:T###")` for the long tail Babel
  does not partition explicitly.

`gene.py` is intentionally **not** driven by the registry: it does a bespoke `MRCONSO` cross-check
on tree number `A1.2.3.5`. Its tree number is recorded in `UMLS_TYPE_MAP` for documentation only
(no `biolink_type`). The RxNorm path (`umls.write_rxnorm_ids`) classifies by RXNCONSO `TTY`, not by
a tree map, so it is also out of scope.

## Changing an assignment

Editing a partition assignment changes build output. The invariant from `CLAUDE.md` applies: no CUI
may move between compendia, and no CUI may be dropped. To change one:

1. Edit the `UMLSTypeAssignment` in `src/datahandlers/umls/semantic_types.py`.
2. Run `uv run pytest tests/datahandlers/test_umls_semantic_types.py -m unit -q`. The golden
   snapshot test will flag the change; update its expected value once you confirm the change is
   intended.
3. Verify no CUI moves compendium: regenerate the seven `ids/UMLS` outputs (the
   `umls_pipeline_outputs` fixture / `uv run pytest tests/pipeline/test_umls.py --pipeline`) and
   confirm `test_no_id_in_multiple_compendia` stays green and total CUI counts are sane.

A change that retypes a CUI within the *same* compendium's outputs (e.g. Disease ->
PhenotypicFeature inside diseasephenotype) moves no CUI between compendia but can still retype many
thousands of CUIs — treat it as a deliberate per-build experiment.

## Tracking disagreements with the Biolink Model

When Babel believes the Biolink Model maps a UMLS semantic type incorrectly:

1. Set `proposed_biolink_type` (the class we want the Model to use) and `issue` on the entry. You
   may or may not also change `biolink_type` (whether to actually apply our preferred type now is a
   separate, output-changing decision).
2. The network test `tests/datahandlers/test_umls_semantic_types.py::test_disagreement_still_needed`
   checks every such entry against the live Biolink Model at `config.yaml`'s `biolink_version`. As
   long as the Model disagrees, the entry is "still needed" and the test passes.
3. When a future Biolink release adopts `proposed_biolink_type`, the test fails (or xfails, if
   `allow_xfail_when_adopted`) with a message telling you to delete the now-redundant entry. This is
   the signal that we can drop the override and rely on the Model.

This is how we accumulate evidence for a Biolink Model pull request, then retire the local override
once it lands.

## Running the tests

```bash
uv run pytest tests/datahandlers/test_umls_semantic_types.py -m unit -q     # offline: maps, validation, resolver
uv run pytest tests/datahandlers/test_umls_semantic_types.py --network -v   # also: redundancy vs live Biolink
uv run pytest tests/pipeline/test_umls.py --pipeline --no-cov -v            # also: SEMANTIC_NETWORK drift vs MRSTY
```
