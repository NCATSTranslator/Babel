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
  row stands in for a link a source should supply, so say what would supply it. Each file has its
  own place for this; see its section below.
- **Name issues and PRs unambiguously.** Rows here come from both the `TranslatorSRI` and
  `NCATSTranslator` organizations, so a bare `#N` is ambiguous: in a `disease.txt` comment or a
  `drugchemical.tsv` note write `owner/repo#N` or the full URL, and in `drugchemical.tsv`'s `url`
  column always the full URL.

## `drugchemical.tsv`

`build_conflation()` reads it with `csv.DictReader` (`csv.excel_tab`: tab-separated, with a header
row) and groups by `subject` and `object` alone. The columns are `subject`, `predicate`, `object`,
`notes` and `url`.

- **Each row joins two whole cliques, not two CURIEs.** Both CURIEs are normalized to their clique
  leaders first, so every other member of either clique joins the conflation too.
- **A row can be skipped, and only the warning says so.** It is counted in the conflation
  metadata's `count_concords_skipped` and logged on every build when:
  - either CURIE is in no chemical compendium (it may have been retyped, say as a protein): the
    whole row is skipped, not just that CURIE;
  - both CURIEs are already in the same clique, so the row normalizes to a self-pair.
- **A row can also lose to another concord without any warning.** `build_conflation()` hands
  `glom()` the RxNorm and UMLS pairs first, then the manual rows, then the PubChem–RxNorm pairs,
  restricted by `drugchemical_unique_prefixes` in `config.yaml` (`INCHIKEY`). A pair whose merge
  would put two different `INCHIKEY` clique leaders in one conflation is dropped, so a manual row
  loses to an RxNorm or UMLS pair that got there first, and wins over a PubChem one.
- **Pin each identifier you need with its own row**, paired with a CURIE from the *other* clique.
  One that reaches the conflation only through a clique it happens to share today drops out when
  that clique is fixed. A row that repeats an existing cross-clique pair after normalization
  changes no grouping, so that kind of pin costs nothing; a row pairing two members of the same
  clique is a self-pair, skipped with a warning until the clique splits.
- **The predicate doesn't affect grouping**, but it is counted into the conflation metadata. Use
  `skos:exactMatch` only for the same substance, and `skos:closeMatch` or `skos:relatedMatch` for
  similar ones (a hydrate and its parent, an animal insulin and human insulin). Use
  `skos:narrowMatch` when the object is a more specific form of the subject (human insulin and one
  branded insulin glargine product), and `skos:broadMatch` the other way round.
- **`notes` says why the row exists; `url` links where it was reported.** Separate several links
  with `||`, as existing rows do.
- **Keep tabs and line breaks out of a note**: either one splits the row unless the note is
  quoted, and a split row loses its `url` without any error. Quote a note containing `"` with
  straight quotes doubled (`"Insulin and ""Insulin aspart"""`); a curly quote is not a CSV quote
  and needs no escaping.
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
- **Concord order decides which pair wins.** `glom()` applies the concords in `disease_concords`
  order, and `Manual` comes after `HP`, `MP`, `MONDO`, `MONDO_GARD`, `UMLS`, `DOID` and `EFO` but
  before `GARD_label`. So a manual row loses to an earlier source that already put a different
  MONDO, HP or MP term in either clique, and once applied it can block a later `GARD_label` pair
  that would bring in a second one. Neither shows up as a warning.
- **A CURIE whose prefix Biolink doesn't register for the clique's class is dropped from the
  output**, but only by `write_compendium()`, after it has already merged cliques in `glom()`. So
  the row's merge happens and the CURIE itself is missing from `Disease.txt` or
  `PhenotypicFeature.txt`, unless its prefix is in `disease_extra_prefixes_by_biolink_class` in
  `config.yaml`. Check with `get_biolink_model_toolkit(version).get_element(<class>).id_prefixes`
  (root `AGENTS.md`, "Biolink Model Usage").
- **A clique needs a typed member to be written at all.** `classify_disease_clique()` types a
  clique from its MONDO, then HP, then MP term, and otherwise by a vote over the members that
  appear in a disease ids file. A clique with none of those is dropped with a warning, so a row
  pairing two CURIEs that no ids file lists, and that join no typed clique, does nothing.
- **A pair naming a UMLS CUI that another pipeline owns is dropped** (root `AGENTS.md`, "A UMLS CUI
  follows its MeSH descriptor"). Check the build's `intermediate/umls/mesh_ownership.tsv` before
  pairing a CUI.
- **HP and MP never share a clique.** `split_mutually_exclusive_cliques()` runs once all concords
  are applied and peels MP out of any clique that also holds HP.
- To see what a row does before a build, replay `build_compendium()` over a finished build's
  `intermediate/` (`docs/sources/AGENTS.md`, "Replaying a pipeline function beats rebuilding").
