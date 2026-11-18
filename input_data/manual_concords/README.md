# Manual concords

The files here hand Babel links that no source it ingests supplies. The two files are read by
different code and do different things, so check which one you are editing:

| File               | Read by                                                       | Effect                                                                  |
| ------------------ | ------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `drugchemical.tsv` | `build_conflation()` in `src/createcompendia/drugchemical.py` | Puts two chemical cliques in one DrugChemical conflation; no clique changes |
| `disease.txt`      | `rule disease_manual_concord` in `src/snakefiles/diseasephenotype.snakefile` | A concord that `glom()` applies like any other: it merges disease cliques |

## Before adding a row to either file

- **Look up each CURIE's clique in a finished build first** — the DuckDB `Edge` table, or Node
  Normalization with conflation off — never in the concords (root `AGENTS.md`, "Debugging"). A row
  acts on whole cliques, so what else those cliques hold is what you are really adding.
- **Record why the row exists, where it was reported, and what would make it redundant.** A manual
  row stands in for a link a source should supply, so say what would supply it.
- **Name issues and PRs as `owner/repo#N`**, or by full URL. Rows here come from both the
  `TranslatorSRI` and `NCATSTranslator` organizations, so a bare `#N` is ambiguous.

## `drugchemical.tsv`

`build_conflation()` reads it with `csv.DictReader` (tab-separated, with a header row) and groups by
`subject` and `object` alone.

- **Each row joins two whole cliques, not two CURIEs.** Both CURIEs are normalized to their clique
  leaders first, so every other member of either clique joins the conflation too. A CURIE in no
  chemical compendium is skipped with a warning.
- **Pin each identifier you need with its own row.** One that reaches the conflation only through
  a clique it happens to share today drops out when that clique is fixed. A row that repeats an
  existing pair after normalization changes no grouping, so pinning costs nothing.
- **The predicate doesn't affect grouping**, but it is counted into the conflation metadata. Use
  `skos:exactMatch` only for the same substance, and `skos:closeMatch` or `skos:relatedMatch` for
  similar ones (a hydrate and its parent, an animal insulin and human insulin).
- **The `notes` column is the only place for the row's reason.** Quote a note containing `"` with
  straight quotes doubled (`"Insulin and ""Insulin aspart"""`); a curly quote is not a CSV quote.
- **Keep the file's CRLF line endings**, so an edit doesn't rewrite every line.

## `disease.txt`

`rule disease_manual_concord` drops blank lines and lines starting with `#`, checks every other line
with `parse_concord_line()` (three tab-separated, non-empty, unpadded columns), and writes it to the
`disease/concords/Manual` concord. `build_compendium()` in `src/createcompendia/diseasephenotype.py`
then reads it like every other disease concord.

- **The reason goes in a `#` comment above the row.** There are no notes column and no trailing
  comments; group related rows under a heading comment, as the file already does.
- **The predicate is ignored.** Every row is an equivalence to `glom()`, so `oio:closeMatch` merges
  two cliques exactly as `xref` does.
- **Merges are transitive.** A row joins the two cliques its CURIEs are in, and everything already
  in them.
- **A row that would put two CURIEs of a restricted prefix in one clique is silently skipped.**
  `disease_unique_prefixes` in `config.yaml` restricts `MONDO`, `HP` and `MP`, and `glom()` drops
  any pair whose merge would hold two of the same one. You can't merge two MONDO terms here; if two
  cliques that each hold one should be one, that is a MONDO issue.
- **A pair naming a UMLS CUI that another pipeline owns is dropped** (root `AGENTS.md`, "A UMLS CUI
  follows its MeSH descriptor"). Check the build's `intermediate/umls/mesh_ownership.tsv` before
  pairing a CUI.
- **HP and MP never share a clique.** `split_mutually_exclusive_cliques()` runs once all concords
  are applied and peels MP out of any clique that also holds HP.
- To see what a row does before a build, replay `build_compendium()` over a finished build's
  `intermediate/` (`docs/sources/CLAUDE.md`, "Replaying a pipeline function beats rebuilding").
