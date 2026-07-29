# LOINC

[LOINC](https://loinc.org) (Logical Observation Identifiers Names and Codes) is a terminology of
clinical observations — lab tests, clinical measurements, vital signs, survey items, and more. Babel
ingests the **clinical** subset as
[`biolink:ClinicalFinding`](https://biolink.github.io/biolink-model/docs/ClinicalFinding.html) in a
dedicated `clinicalfinding` pipeline (`src/createcompendia/clinicalfinding.py`,
`src/snakefiles/clinicalfinding.snakefile`).

> **ⓘ Anonymous download by default.** LOINC's official full release (`loinc.csv`) requires a free
> account at <https://loinc.org/downloads> and cannot be fetched anonymously. When
> `loinc_download_url` is empty (the default), the `get_loinc` rule falls back to the **Tuva
> Project's public S3 mirror** — the same LOINC release (104k+ codes, same `CLASSTYPE` semantics)
> redistributed as a headerless CSV at no credential cost. To use the official authenticated
> `loinc.csv` instead, set `loinc_download_url` to its directory-prefix URL; or place `loinc.csv`
> manually at `babel_downloads/LOINC/loinc.csv` and the rule is skipped on reruns. **Both formats —
> headered (official) and headerless (Tuva mirror) — are unit-tested.**

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

## Testing — synthetic fixtures for both formats

Two fixtures exercise the parser:

- `tests/data/loinc_sample.csv` — **headered** (official `loinc.csv` format) with placeholder codes
  (`1111-1`, …) and the documented LOINC Table Structure columns. Validates by-name column lookup,
  the `CLASSTYPE=2` filter, dedup, and RFC-4180 comma quoting.
- `tests/data/loinc_tuva_sample.csv` — **headerless** (Tuva mirror format) with positional columns
  (col 0 = `LOINC_NUM`, col 2 = `LONG_COMMON_NAME`, col 11 = `CLASSTYPE`). Validates that
  `_loinc_has_header` detects the format and `_iter_clinical_loinc` switches to positional access.

Both assert **no** guarantee about real-world LOINC data — they exercise parser mechanics only.

## Anonymous download (no credentials)

The Tuva Project (`https://thetuvaproject.com/terminology/loinc`) mirrors the LOINC release on a
public AWS S3 bucket:

```text
https://tuva-public-resources.s3.amazonaws.com/versioned_terminology/latest/loinc.csv_0_0_0.csv.gz
```

Downloaded as a gzip, decompressed, and renamed to `loinc.csv`, this headerless CSV contains the
same 104,672 LOINC codes and `CLASSTYPE` values as the official release — just with a different
(on-disk, headerless) layout. The `_loinc_has_header` helper detects this layout and switches
`_iter_clinical_loinc` to positional column access (col 0 / 2 / 11).

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
