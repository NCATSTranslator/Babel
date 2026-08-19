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

Cliques still merge, in the other direction: **DOID cross-references GARD**, 2,196 distinct GARD
ids across its `hasDbXref` values (2,195 once normalized, below). Those xrefs already sit in
`intermediate/disease/concords/DOID`, and the disease prefix filter is the only thing that keeps
them out of `Disease.txt` today. Ingesting GARD (and passing `extra_prefixes=[GARD]`, below) turns
1,895 of them into labelled members of the DOID/MONDO cliques they were xrefed from; the remaining
14,319 registry terms that no other source maps join as single-identifier cliques.

Measured on the finished build: `Disease.txt` holds 16,513 distinct GARD identifiers across 16,479
cliques — 14,319 of them single-identifier, 2,160 sharing a clique with another vocabulary.

DOID also asserts 300 GARD ids the current registry no longer publishes. Those join their DOID
clique without a label, exactly like any other xref target Babel does not ingest — retired ids are
worth keeping, since data that still cites them normalizes to the right clique. (299 reach
`Disease.txt`; `GARD:10191` does not, because its only subject `DOID:1824` reaches neither disease
compendium — a pre-existing condition, absent from the `main` build too, and unrelated to GARD.)

## Local-id form: unpadded

The distribution zero-pads every local id to seven digits (`GARD:0006038` "Chikungunya fever"),
but DOID emits the **unpadded** form for all but 29 of its 2,196 distinct GARD xrefs (`GARD:6038`,
from [`DOID:0050012`](http://purl.obolibrary.org/obo/DOID_0050012) "chikungunya"); 28 carry the
registry's 7-digit padding (`GARD:0018564`, from
[`DOID:0061263`](http://purl.obolibrary.org/obo/DOID_0061263) "lethal congenital contracture
syndrome 7"), so DOID is internally inconsistent too. The 29th is a typo, below.

Babel standardizes on the unpadded form. `normalize_gard_curie()` in `src/datahandlers/gard.py`
strips leading zeros, and is applied in two places:

1. when parsing the registry CSV, so `labels`, `synonyms` and the `ids/GARD` file are all unpadded;
2. in `doid.build_xrefs()`, so DOID's padded xrefs match too.

Without this, `GARD:0006038` and `GARD:6038` are two identifiers for one disease: 1,886 rare
diseases would normalize to two conflicting cliques, and none of DOID's GARD xrefs would ever pick
up a registry label.

The registry's own web endpoint trims leading zeros the same way, so
`https://rarediseases.info.nih.gov/?gard_id=6038` and `?gard_id=0006038` both resolve — use that
form when linking a GARD CURIE from documentation (GARD is absent from the Biolink prefix map, so
there is no `get_biolink_prefix_map()` expansion for it).

### The one xref that is not padding

[`DOID:0061030`](http://purl.obolibrary.org/obo/DOID_0061030) "hemophilia" writes its GARD xref as
`GARD:0418` — four digits, so neither the unpadded form nor the registry's 7-digit padding.
Hemophilia is [`GARD:10418`](https://rarediseases.info.nih.gov/?gard_id=10418); `GARD:0418` is a
typo, and it unpads to `GARD:418` "Essential pentosuria", which
[`DOID:0111258`](http://purl.obolibrary.org/obo/DOID_0111258) "pentosuria" already xrefs. The two
cliques do not merge — both hold a MONDO identifier and MONDO is in `DISEASE_UNIQUE_PREFIXES`, so
`glom()` refuses the union — but the contested identifier goes to whichever clique claims it first,
and DOID's concord lists hemophilia's row first. Left alone, the hemophilia clique carries an
identifier labelled "Essential pentosuria" and pentosuria never gets its registry term;
[`mistyped-xref/clique-diff.csv`](mistyped-xref/clique-diff.csv) measures exactly that.

`input_data/doid_badxrefs.txt` drops the pair, using the same per-concord bad-xref mechanism as
MONDO/HP/MP/UMLS, and the typo is reported upstream as
[DiseaseOntology#1620](https://github.com/DiseaseOntology/HumanDiseaseOntology/issues/1620). It is
dropped rather than rewritten to `GARD:10418`: Babel reports upstream xrefs, it does not invent
them, and the correct edge arrives on its own once DOID fixes the typo. Restricting
`normalize_gard_curie()` to 7-digit local ids would also have unmerged the two, but by accident — it
would leave a dangling `GARD:0418` in the concord and silently swallow the next mistyped id instead
of recording it.

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
GARD can be dropped from `disease_extra_prefixes` in `config.yaml`. This is the same situation GTDB
is in for `biolink:OrganismTaxon` (PR #978 ships GTDB under the same `extra_prefixes` escape hatch).

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
| `extra_prefixes=[GARD]` | `disease_extra_prefixes` in `config.yaml`, read by `build_compendium` in `src/createcompendia/diseasephenotype.py` |
| Mistyped DOID xref | `input_data/doid_badxrefs.txt`, registered in `DEFAULT_BAD_XREFS` and the `disease_compendia` rule |
| Config lists | `disease_ids`, `disease_labelsandsynonyms`, `disease_extra_prefixes`, `gard_download_url` in `config.yaml` |

The `disease_gard_ids` rule is a simple `awk` transform of the labels file (every GARD term is a
Disease), mirroring the DOID/Orphanet ids rules.

## Source-impact report

Generated (synthetic mode) and committed at [`impact-report.md`](impact-report.md), with the two
committed reductions in [`impact-report/`](impact-report/). It was run against a complete local
`disease` intermediate set (all 11 `disease_ids` files and all 8 `disease_concords`), from the same
finished build the clique diffs below compare.

Summary:

- **16,214 identifiers** added (all `GARD:`, all `biolink:Disease`).
- **14,319 new cliques** -- one single-identifier clique per registry term that no other source
  maps (a 3.25% increase over the 440,647 pre-existing disease cliques; total goes to 454,966).
- **1,809 existing cliques contain GARD identifiers**, all of them via DOID's pre-existing xrefs
  rather than a GARD concord: GARD's ids file promotes CURIEs that were already in the clique to
  first-class typed identifiers, and gives them a label. **0 cliques merge** and no clique gains a
  structurally new identifier, so no existing clique is restructured.
- **0 cross-reference rows** contributed -- GARD has no concord of its own.
- **Section 4 is a worst-case (upper-bound) view:** it is computed before the Biolink per-class
  prefix filter runs, so the sample cliques are flagged "NOT emitted -- prefix not registered in
  Biolink Model for `biolink:Disease`". That flag is *exactly* why the build passes
  `extra_prefixes=[GARD]` (see above); with it, the identifiers are kept at `write_compendium`
  time. Registering GARD upstream removes both the flag and the need for `extra_prefixes`.
- Section 2's "Final compendium-assigned" line confirms all 16,214 GARD identifiers reach
  `Disease.txt` in the finished build, which is the check `extra_prefixes` exists to pass.

Regenerate after a typing or extraction change:

```bash
uv run source-impact-report --source GARD
```

## Build-vs-build clique diff

The impact report only walks after-cliques containing a GARD CURIE, so it cannot show a
before-clique that splits, shrinks, or loses its leader — and it cannot show *which* of two
competing cliques a new GARD identifier joined. [`clique-diff.md`](clique-diff.md) records two
`babel-clique-diff` runs that close both gaps: `main` vs this branch
([`on-addition/`](on-addition/), which confirms the addition is purely additive — 0 regrouped, 0
moved, 0 dropped, 0 leader changes) and this branch with vs without the bad-xref entry
([`mistyped-xref/`](mistyped-xref/), three rows isolating the hemophilia/pentosuria fix).
