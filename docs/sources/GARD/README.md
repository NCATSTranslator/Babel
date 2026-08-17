# GARD — NCATS Genetic and Rare Diseases registry

GARD is the NCATS Genetic and Rare Diseases information center's rare-disease registry. It is a
flat list of rare-disease terms -- each a `GARD:` CURIE with a preferred label and pipe-separated
synonyms -- distributed by NCATS as a single CSV. Babel ingests it as a `biolink:Disease` source in
the existing `disease` (`diseasephenotype`) pipeline.

## What GARD contributes

GARD is a **registry, not an ontology**: it carries no cross-references to other disease
vocabularies (no MONDO/DOID/UMLS/Orphanet mappings). It therefore contributes **identifiers and
labels/synonyms only** -- there is no GARD concord file. Every GARD term is typed
`biolink:Disease`, so each lands in `Disease.txt`.

Cliques still merge, in the other direction: **DOID cross-references GARD**, 2,187 distinct GARD
ids across its `hasDbXref` values (2,186 once normalized, below). Those xrefs already sit in
`intermediate/disease/concords/DOID`, and the disease prefix filter is the only thing that keeps
them out of `Disease.txt` today. Ingesting GARD (and passing `extra_prefixes=[GARD]`, below) turns
1,886 of them into labelled members of the DOID/MONDO cliques they were xrefed from; the remaining
14,328 registry terms that no other source maps join as single-identifier cliques.

DOID also asserts 300 GARD ids the current registry no longer publishes. Those join their DOID
clique without a label, exactly like any other xref target Babel does not ingest — retired ids are
worth keeping, since data that still cites them normalizes to the right clique.

## Local-id form: unpadded

The distribution zero-pads every local id to seven digits (`GARD:0006038` "Chikungunya fever"),
but DOID emits the **unpadded** form for 2,164 of its 2,187 distinct GARD xrefs (`GARD:6038`, from
[`DOID:0050012`](http://purl.obolibrary.org/obo/DOID_0050012) "chikungunya"); the other 23 are
padded (`GARD:0418`, from
[`DOID:0061030`](http://purl.obolibrary.org/obo/DOID_0061030) "hemophilia"), so DOID is internally
inconsistent too. Normalizing collapses the two forms onto 2,186 distinct ids.

Babel standardizes on the unpadded form. `normalize_gard_curie()` in `src/datahandlers/gard.py`
strips leading zeros, and is applied in two places:

1. when parsing the registry CSV, so `labels`, `synonyms` and the `ids/GARD` file are all unpadded;
2. in `doid.build_xrefs()`, so DOID's 23 padded xrefs match too.

Without this, `GARD:0006038` and `GARD:6038` are two identifiers for one disease: 1,886 rare
diseases would normalize to two conflicting cliques, and none of DOID's GARD xrefs would ever pick
up a registry label.

## Biolink registration (the `extra_prefixes` escape hatch)

`GARD` is registered **neither** in the Biolink Model's `disease` `id_prefixes` nor in its prefix
map (both verified against the pinned `biolink_version` in `config.yaml`; the missing prefix-map
entry is why the impact report renders GARD CURIEs without a resolving link).
`write_compendium` keeps only identifiers whose prefix is in the clique type's `id_prefixes` and
silently drops the rest, so without intervention every GARD CURIE would vanish from `Disease.txt`
-- both the ~16k registry terms and the 2,186 that arrive via DOID's concord. The disease
compendium build therefore passes `extra_prefixes=[GARD]` (the
[documented escape hatch](../../AddingNewSources.md)) at the `write_compendium` call site in
`src/createcompendia/diseasephenotype.py`.

Registering GARD with the Biolink team for `biolink:Disease` is the long-term fix; once registered,
the `extra_prefixes=[GARD]` line can be dropped. This is the same situation GTDB is in for
`biolink:OrganismTaxon` (PR #978 ships GTDB under the same `extra_prefixes` escape hatch).

## Download

The GARD term list is a Salesforce ContentVersion download link configured as
`gard_download_url` in `config.yaml` and passed to the `get_gard` rule (in
`src/snakefiles/datacollect.snakefile`) as a `params` value, so repointing the URL retriggers the
download. It is a query-string URL with no stable filename on the server, so the rule calls
`src.datahandlers.gard.pull_gard()` directly rather than the shared `pull_via_urllib` helper.

Two guards keep a broken distribution from producing a green build with no rare diseases in it: the
download rejects a response whose `Content-Type` is not a CSV (an expired ContentVersion link
serves an HTML error page with HTTP 200, which `urllib` does not raise on), and the parser raises
if the `ID`/`DisplayName` headers are missing or if no term parses at all.

The CSV is UTF-8 with a BOM and CRLF line endings, with columns `ID,DisplayName,Synonyms,URL`. The
`URL` column (the rarediseases.info.nih.gov page) is not ingested: Babel handlers emit only
labels, synonyms, taxa and descriptions, and there is no per-identifier URL attribute file for it
to go in.

## Wiring

| Concern | Location |
| --- | --- |
| Prefix constant | `src/prefixes.py` (`GARD = "GARD"`) |
| Data handler | `src/datahandlers/gard.py` |
| Local-id normalization | `normalize_gard_curie()` in `src/datahandlers/gard.py`, also called from `src/datahandlers/doid.py` |
| Download rule | `get_gard` in `src/snakefiles/datacollect.snakefile` |
| Labels/synonyms rule | `get_gard_labels_and_synonyms` in `src/snakefiles/datacollect.snakefile` |
| ids rule | `disease_gard_ids` in `src/snakefiles/diseasephenotype.snakefile` |
| `extra_prefixes=[GARD]` | `build_compendium` in `src/createcompendia/diseasephenotype.py` |
| Config lists | `disease_ids`, `disease_labelsandsynonyms`, `gard_download_url` in `config.yaml` |

The `disease_gard_ids` rule is a simple `awk` transform of the labels file (every GARD term is a
Disease), mirroring the DOID/Orphanet ids rules.

## Source-impact report

Generated (synthetic mode) and committed at [`impact-report.md`](impact-report.md), with full
detail in [`impact-report/`](impact-report/). It was run against a complete local `disease`
intermediate set (all 10 `disease_ids` files and all 8 `disease_concords`), with GARD's own
intermediates and the DOID concord rebuilt from the current DOID release so the report reflects the
unpadded ids.

Summary:

- **16,214 identifiers** added (all `GARD:`, all `biolink:Disease`).
- **14,328 new cliques** -- one single-identifier clique per registry term that no other source
  maps (a 3.25% increase over the 440,990 pre-existing disease cliques; total goes to 455,318).
- **1,886 GARD identifiers land in 1,644 existing cliques**, all of them via DOID's pre-existing
  xrefs rather than a GARD concord: GARD's ids file promotes CURIEs that were already in the clique
  to first-class typed identifiers, and gives them a label. **0 cliques merge** and no clique gains
  a structurally new identifier, so no existing clique is restructured.
- **0 cross-reference rows** contributed -- GARD has no concord of its own.
- **Section 4 is a worst-case (upper-bound) view:** it is computed before the Biolink per-class
  prefix filter runs, so the sample cliques are flagged "NOT emitted -- prefix not registered in
  Biolink Model for `biolink:Disease`". That flag is *exactly* why the build passes
  `extra_prefixes=[GARD]` (see above); with it, the identifiers are kept at `write_compendium`
  time. Registering GARD upstream removes both the flag and the need for `extra_prefixes`.
- Section 2's "Final compendium-assigned" counts are blank because there are no local compendia
  on this machine (they require a full `disease` build); expected for a synthetic-only run.

Regenerate after a typing or extraction change:

```bash
uv run source-impact-report --source GARD
```
