# LOINC

[LOINC](https://loinc.org) (Logical Observation Identifiers Names and Codes) is a terminology of
clinical observations — lab tests, clinical measurements, vital signs, survey items, and more. Babel
ingests the **clinical** subset as
[`biolink:ClinicalFinding`](https://biolink.github.io/biolink-model/docs/ClinicalFinding.html) in a
dedicated `clinicalfinding` pipeline (`src/createcompendia/clinicalfinding.py`,
`src/snakefiles/clinicalfinding.snakefile`).

> **⚠ Download is credential-gated — this source cannot be built or validated without a free LOINC
> account.** The full LOINC release (`loinc.csv`) is available only by logging in at
> <https://loinc.org/downloads>; it cannot be fetched anonymously. The `get_loinc` rule pulls it
> from `loinc_download_url` in `config.yaml` (an authenticated URL the operator supplies);
> alternatively, place `loinc.csv` manually at `babel_downloads/LOINC/loinc.csv` and the rule is
> skipped. **The unit tests use a synthetic fixture (see below) and do not validate against real
> LOINC data — run a real build with credentials before relying on this source.**

## What is ingested

`loinc.csv` is read **by column name** (robust to its ~100 columns and any reordering). Three
columns matter:

- `LOINC_NUM` — the code, emitted as `LOINC:<LOINC_NUM>`.
- `CLASSTYPE` — the authoritative primary key: `1`=Laboratory, `2`=Clinical, `3`=Claims attachments,
  `4`=Surveys. **v1 ingests `CLASSTYPE=2` (Clinical) only**; lab/claims/surveys are excluded (a
  deliberate, expandable choice).
- `LONG_COMMON_NAME` — the human-readable label.

`write_loinc_ids` writes `LOINC:<code>\tbiolink:ClinicalFinding`; `write_loinc_labels` writes
`LOINC:<code>\t<LONG_COMMON_NAME>`.

## Design notes (load-bearing)

- **Own pipeline, not a fold into `diseasephenotype`.** LOINC is registered for
  `biolink:ClinicalFinding` (it is the #1 prefix in that class's `id_prefixes` in the pinned Biolink
  Model), so **no `extra_prefixes`** is needed. In v1 LOINC has no concord linking it to
  HP/MP/MONDO, so its terms form **singleton cliques** (still useful — they normalize as
  `biolink:ClinicalFinding` with labels). If a LOINC↔ontology concord becomes available, LOINC
  should move into the `diseasephenotype` pipeline so the equivalences glom into the existing
  disease/phenotype cliques.
- **No concord in v1.** No comprehensive LOINC↔HP/EFO/UMLS equivalence source is identified; adding
  one is the main follow-up.

## Testing caveat — synthetic fixture

Because `loinc.csv` is credential-gated, `tests/data/loinc_sample.csv` is **synthetic**: the
documented LOINC Table Structure columns with placeholder codes (`1111-1`, …). It exercises the
parser mechanics (by-name column lookup, the `CLASSTYPE=2` filter, id/label emission) and asserts
**no** guarantee about real LOINC data. Validate against the real file (with credentials) before
use.

## Registration in the build

`clinicalfinding_labels` / `clinicalfinding_ids` / `clinicalfinding_outputs`
(`[ClinicalFinding.txt]`) in `config.yaml`; `ClinicalFinding.txt` is added to the `util.py`
compendium/synonym aggregators and `report_tables.py`, so it flows through the
DuckDB/KGX/Parquet/report exports. `reports/clinicalfinding_done` is in the top-level `all_outputs`.

## Related

- `src/datahandlers/loinc.py` — `write_loinc_ids`, `write_loinc_labels` (CLASSTYPE=2 filter, by-name
  columns).
- `src/createcompendia/clinicalfinding.py` — `build_compendia`, `compute_cliques_for_impact_report`.
- `tests/datahandlers/test_loinc.py` — synthetic-fixture unit tests.
