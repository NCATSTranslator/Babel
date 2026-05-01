# MP Integration: Validation Findings

A standalone memo recording quality and correctness concerns surfaced while reviewing
[PR #300][pr-300] before merge. This file captures the *intent* and *known risks* at
the time MP was added; once the PR has been merged and the resulting compendium has
been validated under normal operations, this file may be deleted (information is
derivable from the standing reports under `babel_outputs/reports/` and
`babel_outputs/metadata/`) or kept as an artefact.

The empirical numbers below come from running the `get_hp_mp_concord` rule on
`master`-branch SSSOM files at SHA `3f3eeb05af9b600976b97185c5f5d8211a85df2c` of
`mh_mapping_initiative`. Re-run the rule and read `metadata-HP_MP.yaml` for the latest
counts; do not paste counts back into this file.

## Resolved during integration review

Two pipeline-blocking wiring gaps in PR #300 (flagged by the GitHub Copilot reviewer
on 2026-04-30) were fixed as part of this work:

1. **Missing `disease_mp_ids` rule.** `write_mp_ids()` was defined but no Snakemake
   rule called it, so `${intermediate_directory}/disease/ids/MP` would never be
   produced. Added a `disease_mp_ids` rule mirroring `disease_hp_ids` in
   `src/snakefiles/diseasephenotype.snakefile`.
2. **`MP` missing from `generate_dirs_for_labels_and_synonyms_prefixes`.** `MP` was in
   `disease_labelsandsynonyms` but the generic `get_obo_labels` / `get_obo_synonyms`
   rules are driven by a separate prefix list, so `${download_directory}/MP/labels`
   and `${download_directory}/MP/synonyms` would never be produced. Added `MP` to that
   list in `config.yaml`.

Both bugs were verified by `uv run snakemake --dry-run disease`, which previously
failed DAG resolution and now succeeds.

A third issue, not flagged by the reviewer, was also fixed:

3. **Broken `sssom` import.** `linkml 1.9.3` (pulled in transitively by `sssom 0.4.17`)
   references `linkml_runtime.linkml_model.linkml_files.Format.JSON`, which was
   removed in `linkml-runtime 1.10.0`; importing `sssom` therefore failed under the
   resolved versions. The fix was to add a `linkml>=1.10` constraint at the lock
   level, which causes `sssom` to resolve down to `0.4.11` (the version that does
   not depend on the `linkml` package directly, only on `linkml-runtime`). After the
   change `from sssom import parsers` succeeds and `get_hp_mp_concord` runs.

## Mapping-quality concerns from the PR author

Both examples are from <https://github.com/NCATSTranslator/Babel/pull/300>; reviewers
can confirm them through the linked tooling.

### Hemorrhage duplicated

[`MP:0001914 "hemorrhage"`][mp-hemorrhage] and
[`NCIT:C26791 "hemorrhage"`][ncit-hemorrhage] describe the same concept but stay in
separate cliques. The mapping exists in EFO but UberGraph does not load EFO, so the
bridge is invisible to Babel.

### Accessory spleen mis-cliqued

[`MP:0003342 "accessory spleen"`][mp-accessory-spleen] gets cliqued with
[`HP:0001748 "Polysplenia"`][hp-polysplenia] instead of the correct
[`HP:0001747 "Accessory spleen"`][hp-accessory-spleen]. This is an upstream mapping
error that propagates into Babel through the SSSOM imports.

The PR author argued these are tolerable because (a) MP is never a clique leader when
sharing a clique with MONDO or HP, and (b) MP is not surfaced by autocomplete (which
filters to MONDO/HP). Both points still hold, but they are arguments for *deferring*
the fix, not for ignoring it. Future work on MP should track these cases explicitly.

## Filter-policy concerns surfaced by the metadata report

After running `get_hp_mp_concord` once, `metadata-HP_MP.yaml` made several non-obvious
behaviours visible. Each is a candidate for a follow-up decision; this section
documents the *current* behaviour and the *trade-off*.

### Pistoia mappings drop to zero

`mp_hp_pistoia.sssom.tsv` contributes 1671 mapping rows. The `get_hp_mp_concord`
filter throws all 1671 away: 1670 are dropped because their `confidence` value is
≤ 0.8 (Pistoia's confidence column ranges roughly 0.22–0.75) and the one remaining
row uses `owl:equivalentClass`, which is not in the predicate allowlist. Net result:
**zero Pistoia rows reach the concord file.**

That outcome is consistent with the conservative filter, but it means the line
"Pistoia expert curation" in the snakefile is functionally inactive. Three options for
follow-up:

- **Lower the confidence threshold** (e.g. to 0.7) for Pistoia specifically, since
  Pistoia's confidence values reflect upstream curator judgement rather than an
  automated score and 0.8 may be an artefact of the threshold being a single global
  number.
- **Add `owl:equivalentClass` to the predicate allowlist** for SSSOM-derived concords.
  This would not change much — only one Pistoia row uses it after the confidence
  cut — but it is consistent with how `get_subclasses_and_exacts` already treats
  `owl:equivalentClass`.
- **Remove Pistoia from the input list** until a more informed decision is made about
  threshold, so that future readers do not misread the snakefile as implying Pistoia
  is being used.

The first option is the lowest-risk; the third is the most honest. We left Pistoia
in the list to keep the source code aligned with the original PR's intent and to make
the filter-driven exclusion visible in `metadata-HP_MP.yaml`.

### MGI broad/narrow predicates dropped

The MGI-consolidated file (`mp_hp_mgi_all.sssom.tsv`) contributed about half of all
written rows after filtering. The dropped predicates were `skos:broadMatch` and
`skos:narrowMatch` (about 750 rows combined), which is the correct decision: a broad
or narrow match is *asymmetric*, and treating it as equivalence in `glom()` would
silently merge cliques across category boundaries. No action needed beyond noting it.

### IMPC files lean heavily on `closeMatch`

For four of the five IMPC files (`eye`, `pat`, `owt`, `xry`), the dominant kept
predicate is `skos:closeMatch`, not `skos:exactMatch`. If the predicate allowlist were
ever tightened to `exactMatch`-only — a frequent default in other SSSOM consumers — we
would lose almost all IMPC mappings. Anyone considering a global predicate-policy
tightening should re-check this assumption first.

### `sssom:NoTermFound` rows

A meaningful fraction (40 of 188 in `pat_impc`, 21 of 33 in `owt_impc`, 2 of 57 in
`xry_impc`) of IMPC rows are `sssom:NoTermFound` placeholders for which IMPC has not
yet identified a corresponding HP term. The filter correctly drops them.

## Recommended additional pre-merge checks

The following were *not* done as part of this work, but should happen before the
disease/phenotype compendium is rebuilt with MP for production use:

- Run the `disease` target end-to-end on a clean intermediate directory and inspect
  the resulting `babel_outputs/metadata/PhenotypicFeature.txt.yaml` and
  `babel_outputs/metadata/Disease.txt.yaml` for unexpected clique counts or leader
  shifts.
- Sample N MP-only cliques (e.g. 50–100 randomly chosen) and verify their labels
  against the [MGI MP browser][mgi-mp-browser] to spot any label drift between
  UberGraph and the upstream ontology.
- Verify that no clique that previously had a MONDO or HP leader has shifted to MP
  as a leader. The clique builder uses preferred-prefix order `[MONDO, HP, MP]`, so
  this *should* be impossible — the check is a sanity control on the builder.
- Compare the `prefix_counts` block of `metadata-HP_MP.yaml` against the same block
  in `metadata-MONDO.yaml` and `metadata-UMLS.yaml` to confirm the new HP-MP edges
  do not introduce any structurally surprising prefix pairs (everything should be
  `(HP, MP)` by construction).

## Disposition

Once these checks have been run and are satisfactory:

- If everything looks clean, this file can be **deleted**. The standing
  `metadata.yaml` files and the `babel_outputs/reports/` summaries will continue to
  reflect the actual state of the integration.
- If there are residual issues that need long-lived tracking, this file should be
  **kept** and updated with the new findings, or the issues should be promoted to
  GitHub issues.

## References

[pr-300]: https://github.com/NCATSTranslator/Babel/pull/300
[mp-hemorrhage]: https://www.informatics.jax.org/vocab/mp_ontology/MP:0001914
[ncit-hemorrhage]: https://nodenormalization-sri.renci.org/1.5/get_normalized_nodes?curie=NCIT%3AC26791&conflate=true&drug_chemical_conflate=false&description=false
[mp-accessory-spleen]: https://www.informatics.jax.org/vocab/mp_ontology/MP:0003342
[hp-polysplenia]: https://monarchinitiative.org/HP:0001748
[hp-accessory-spleen]: https://monarchinitiative.org/HP:0001747
[mgi-mp-browser]: https://www.informatics.jax.org/vocab/mp_ontology
