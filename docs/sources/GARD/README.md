# GARD — NCATS Genetic and Rare Diseases registry

GARD is the NCATS Genetic and Rare Diseases information center's rare-disease registry. It is a
flat list of rare-disease terms -- each a `GARD:NNNNNNNN` CURIE with a preferred label and
pipe-separated synonyms -- distributed by NCATS as a single CSV. Babel ingests it as a
`biolink:Disease` source in the existing `disease` (`diseasephenotype`) pipeline.

## What GARD contributes

GARD is a **registry, not an ontology**: it carries no cross-references to other disease
vocabularies (no MONDO/DOID/UMLS/Orphanet mappings). It therefore contributes **identifiers and
labels/synonyms only** -- there is no GARD concord file. Every GARD term is typed
`biolink:Disease`, so each lands in `Disease.txt`. Because GARD provides no xrefs, a GARD term
that no other source already maps joins the build as a single-identifier clique (a new clique);
the source-impact report's "pure-new cliques" count reflects this.

## Biolink registration (the `extra_prefixes` escape hatch)

`GARD` is **not** in the Biolink Model's `disease` `id_prefixes` (verified against the pinned
`biolink_version` in `config.yaml`). `write_compendium` keeps only identifiers whose prefix is in
the clique type's `id_prefixes` and silently drops the rest, so without intervention every GARD
CURIE would vanish from `Disease.txt`. The disease compendium build therefore passes
`extra_prefixes=[GARD]` (the [documented escape hatch](../../AddingNewSources.md)) at the
`write_compendium` call site in `src/createcompendia/diseasephenotype.py` to keep the identifiers.

Registering GARD with the Biolink team for `biolink:Disease` is the long-term fix; once registered,
the `extra_prefixes=[GARD]` line can be dropped. This is the same situation GTDB is in for
`biolink:OrganismTaxon` (PR #978 ships GTDB under the same `extra_prefixes` escape hatch).

## Download

The GARD term list is a Salesforce ContentVersion download link configured as
`gard_download_url` in `config.yaml`. It is a query-string URL with no stable filename on the
server, so the `get_gard` rule (in `src/snakefiles/datacollect.snakefile`) calls
`src.datahandlers.gard.pull_gard()` directly rather than the shared `pull_via_urllib` helper.
Pin or repoint the URL in `config.yaml` when NCATS publishes a new version.

The CSV is UTF-8 with a BOM and CRLF line endings, with columns `ID,DisplayName,Synonyms,URL`.
The `URL` column (the rarediseases.info.nih.gov page) is read for reference only and is not
ingested -- the CURIE itself resolves via the Biolink prefix map.

## Wiring

| Concern | Location |
| --- | --- |
| Prefix constant | `src/prefixes.py` (`GARD = "GARD"`) |
| Data handler | `src/datahandlers/gard.py` |
| Download rule | `get_gard` in `src/snakefiles/datacollect.snakefile` |
| Labels/synonyms rule | `get_gard_labels_and_synonyms` in `src/snakefiles/datacollect.snakefile` |
| ids rule | `disease_gard_ids` in `src/snakefiles/diseasephenotype.snakefile` |
| `extra_prefixes=[GARD]` | `build_compendium` in `src/createcompendia/diseasephenotype.py` |
| Config lists | `disease_ids`, `disease_labelsandsynonyms`, `gard_download_url` in `config.yaml` |

The `disease_gard_ids` rule is a simple `awk` transform of the labels file (every GARD term is a
Disease), mirroring the DOID/Orphanet ids rules.

## Source-impact report

Generated (synthetic mode) and committed at [`impact-report.md`](impact-report.md), with full
detail in [`impact-report/`](impact-report/). The baseline intermediates were assembled from the
`2025dec11` published build snapshot (whose disease concords predate the MP-in-disease addition,
so MP's concord was rebuilt locally from UberGraph for the baseline); GARD's own intermediates
were built locally.

Summary:

- **16,214 identifiers** added (all `GARD:`, all `biolink:Disease`) and **16,214 new cliques** --
  one single-identifier clique per GARD term (a 6.72% increase over the 241,269 pre-existing
  disease cliques). Total cliques go from 241,269 to 257,483.
- **0 merges, 0 modified cliques, 0 cross-references** -- GARD has no concord and no other
  source xrefs GARD, so it cannot bridge or disturb any existing clique. The addition is purely
  additive.
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
