# NCBIGene synonym-field quoting

NCBI's `gene_info.gz` packs multiple values into two pipe-delimited free-text columns that Babel
reads as synonyms:

- `Synonyms` (column index 4) — the NCBI web-API `otheraliases` field.
- `Other_designations` (column index 13) — the NCBI web-API `otherdesignations` field.

Babel splits each on `|` and adds the pieces as synonyms
(`src/datahandlers/ncbigene.py:pull_ncbigene_labels_synonyms_and_taxa`).

## Why we're studying the quoting

[Issue #744](https://github.com/NCATSTranslator/Babel/issues/744) reported malformed synonyms:
NCBI wraps some comma-containing values in `''…''` and then splits the whole field on `|`, so a
value like `''cytochrome P450, family 706, polypeptide 2''` arrives as the dangling fragments
`''cytochrome P450`, `family 706`, `polypeptide 2''`. The fix drops fragments that start *or* end
with `''`.

But while validating that fix on the full file we found that a **trailing** `''` is *legitimate*
"double-prime" gene nomenclature — real `Symbol` values such as `U2B''`, `ycf1''`, `nrdB''`, and
`trnQ-TTG''` end in `''` and are not artifacts. So the same two-character sequence means two
different things depending on context, and "drop anything touching `''`" is probably too blunt
*inside* the pipe-split fields.

Before refining anything we want to characterize the quoting empirically. This directory is
**step 1**: just count what non-word/whitespace characters appear in these two columns and in what
combinations.

## What the analysis counts

`analyze_quoting.py` streams the raw `gene_info.gz`, examines the two columns **before** splitting
on `|`, and treats `-`/empty as empty. A "non-word/whitespace character" is any character `c` with
`not c.isalnum() and not c.isspace() and c != "_"` — i.e. punctuation/symbols, excluding Unicode
letters (Greek etc. in gene names) and digits.

For each column it writes three things to [`counts.json`](./counts.json):

- **`char_frequency`** — per-character histograms: `total_occurrences` (every non-word/whitespace
  character, summed across rows) and `rows_with_char` (rows containing at least one). The single
  quote `'` is included for completeness; note that `''` is a two-character sequence, so it shows up
  here as two `'` characters — the `''` semantics live in the tag analysis instead. The pipe `|` is
  the field delimiter and is included too.
- **`tag_row_counts`** — how many rows carry each independent boolean tag: `empty`, `has_pipe`,
  `has_comma`, `has_double_single_quote` (`''`), `has_lone_single_quote` (a `'` not part of any
  `''`), `has_double_quote` (`"`), `has_semicolon`, `has_paren`, `has_bracket`, `has_brace`,
  `has_backslash`, `has_other_nonword`.
- **`tag_combination_counts`** — for each non-empty row, the *combination* of quoting-relevant tags
  it carries, as a single key (e.g. `only_commas`, `commas_and_double_single_quotes`,
  `commas_and_single_quotes`). `none` counts non-empty rows with no quoting-relevant characters.
  The pipe delimiter is excluded from this view so multi-value rows don't all collapse into one
  bucket. This histogram is the one that reveals co-occurrence patterns.
- **`delimiter_consistency`** — whether `|` behaves as the sole, clean delimiter: multi-value
  (`rows_multi_value_pipe`) vs single-value (`rows_single_value_no_pipe`) rows; delimiter hygiene
  (`pipe_rows_with_empty_fragment` for `||`, `pipe_rows_spaced_or_padded`); *over*-splitting
  (`pipe_rows_with_double_single_quote_span`, where a `''` span's internal pipes are converted
  commas); and *under*-splitting (`no_pipe_rows_with_semicolon`, split into `separator_like` vs
  `within_name_like`, plus `no_pipe_rows_with_comma`).

## Regenerating

```bash
uv run python docs/sources/NCBIGene/quoting/analyze_quoting.py
```

Reads `babel_downloads/NCBIGene/gene_info.gz` (download it via the `get_ncbigene` Snakemake rule
if absent) and writes `counts.json` beside the script. Streaming, so it is safe on memory; a full
pass takes a few minutes. `--input` and `--output` override the paths.

## First findings

From a full run over **70,541,777** data rows (see [`counts.json`](./counts.json)). Counts were
cross-checked with an independent streaming pass.

### Both fields are mostly empty, and where present, mostly plain

- `Synonyms` (`otheraliases`) is empty (`-`) in **58.2M** rows (83%); only **12.3M** rows carry any
  alias.
- `Other_designations` (`otherdesignations`) is non-empty in **54.4M** rows (77%).
- In both, the two largest combination buckets are `none` and `only_other`, and that "other" is
  overwhelmingly *name* punctuation — `-` (hyphens), `.`, `:`, `/`, `(`/`)` — not quoting. For
  example `otheraliases` "other" characters are led by `.` (167k rows), `:` (80k), `\` (19k).

### Real quoting/separator characters are rare — and unevenly split between the two fields

- **Double quote `"`**: effectively unused — **0** rows in `otheraliases`, **106** rows in
  `otherdesignations` (out of 70M). NCBI does **not** use `"` to quote these fields.
- **Comma**: rare in `otheraliases` (**23** rows total) but common in `otherdesignations`
  (**2.75M** rows) — expected, since designations are descriptive phrases and aliases are symbols.
- **Semicolon**: **1,163** rows in `otheraliases`, **637k** in `otherdesignations`.
- **`''` (double single quote)**: **296** rows in `otheraliases`, **24,474** in `otherdesignations`.
- **Lone `'`** (a `'` not part of any `''`): **352** rows in `otheraliases`, **277k** in
  `otherdesignations`.

### The `''` in `otheraliases` marks a value NCBI split across pipe-fields (issue #744)

The single most useful cross-tab: in `otheraliases`, `''` and a comma **never** appear in the same
raw field (**0** rows — no `commas_and_double_single_quotes*` bucket exists for that column). Gene
`828367`'s raw `Synonyms` field shows the mechanism:

```text
''cytochrome P450|T12H17.100|T12H17_100|cytochrome P450|family 706|polypeptide 2|polypeptide 2''|subfamily A
```

Its `description` / `Other_designations` is `cytochrome P450, family 706, subfamily A, polypeptide
2`. NCBI took that comma-containing value, **split it on the commas into separate `|` fields**, and
wrapped the whole run in `''…''`. So in this field a `''` *pair* is the open/close marker of one
logical value that was fragmented across pipe-fields — the commas are gone, replaced by pipes, and
the leading `''cytochrome P450` / trailing `polypeptide 2''` are the two ends of that span. This is
the opposite of the naive reading (`''` quoting a comma-containing string kept intact); here the
commas are consumed by the split and `''` is the only surviving trace of the grouping.

Two consequences worth carrying into any #744 refinement:

- A **leading** `''` (open marker) and a **trailing** `''` (close marker) play different roles in
  the split-span, which is a cleaner signal than "touches `''`". Note also that the double-prime
  symbols that motivated the test change (`U2B''`, `ycf1''`) live in the `Symbol` column, not in
  these two fields — a separate phenomenon.
- `otherdesignations` behaves **differently**: there `''` and commas *do* co-occur (e.g. 459 rows
  are `commas_and_double_single_quotes`), so its `''` values retain their commas rather than being
  comma-split. The mechanism there is left to the follow-up below.

### Is `|` a consistent delimiter for multiple values? (`delimiter_consistency`)

Mostly, with two documented exceptions. Where `|` is used it is clean — empty fragments from `||`
are essentially nonexistent (**0** in `otheraliases`, **2** in `otherdesignations`) and
spaced/padded pipes are rare (**0** and **139**). But `|` is not always the *only* way multiple
values are joined:

- **Under-splitting via semicolon (`otherdesignations` only).** **624,799** designation rows join
  distinct designations with a `;` and no pipe at all — e.g. `ribosomal protein
  S2;uncharacterized protein`. That is 98.6% of the 633,842 no-pipe rows containing a `;` (only
  8,885 are within-name nomenclature). A plain `split("|")` keeps these as one combined synonym.
  In `otheraliases` this barely happens: of its 85 no-pipe `;` rows most are within-name
  (`PIP1;2`, `CYCLIN D3;3`), so aliases pipe-delimiting is effectively consistent.
- **Over-splitting via the `''` span (both fields, small).** **285** `otheraliases` rows and
  **1,999** `otherdesignations` rows have a `''`-wrapped value whose internal pipes are converted
  commas (the #744 mechanism above), so `split("|")` breaks one logical value into fragments.
- **Commas are *not* an alternative delimiter.** No-pipe comma rows are single values that contain
  commas (`succinate dehydrogenase, hydrophobic membrane anchor protein`), not lists — **2.2M** in
  `otherdesignations`, only **5** in `otheraliases`.

Net for Babel's ingest: `otheraliases` is safely pipe-delimited; `otherdesignations` needs
awareness that ~0.6M values are semicolon-joined (under-split) and a few thousand are `''`-spanned
(over-split).

### Most `''` is genuine double-prime nomenclature, not a #744 artifact

`double_prime_report.py` (output: [`double_prime_report.md`](./double_prime_report.md)) separates
`''` that could be a real name component from the #744 split-span markers. A `''` is a split
marker only when it sits at a pipe-fragment boundary as part of an open/close pair; anything else —
a value *ending* in `''` with no matching open marker, a `''` embedded mid-text, or a `''` in the
single-value `Symbol` columns — is a genuine double-prime candidate.

The result: **25,335** genuine `''` occurrences across **372** distinct tokens, versus only
**277** open/close split-span pairs (all in `otheraliases`; `otherdesignations` has *zero* split
markers). Double-prime is rare overall (0.036% of rows) — your intuition is right there — but where
it appears it is real, and it outnumbers the artifacts ~90:1. NCBI is ASCII-rendering the
typographic double-prime `″` as two apostrophes. Two classes dominate:

- **Protein-subunit double-prime (`″`):** `RNA polymerase beta'' subunit` (10,414 rows — the
  largest single token), `U2 small nuclear ribonucleoprotein B''`, PP2A `regulatory subunit B''`,
  `V-type proton ATPase ... subunit c''`, `transcription factor TFIIIB component B''` (BDP1), RNA
  pol `A''`/`E''`/`N''`. Triple/quadruple prime also occur (`SRP31'''`, `b''''`).
- **Chemical-position locants (`2″`, `3″`, `6″`…):** `...-6''-O-malonyltransferase`,
  `...2''-O-xylosyltransferase`, `APH(3'')`/`ANT(3'')` aminoglycoside enzymes, `ADP-ribose
  1''-phosphate phosphatase`, `diadenosine 5',5'''-tetraphosphate`.

Crucially, a **leading** `''` never begins a genuine name (double-prime is always a suffix or
internal locant), so a leading `''` reliably identifies the #744 open marker. That is the basis for
narrowing the fix (below).

## Deferred follow-up questions

Once we know which characters are present, the deeper questions (each a likely next script here):

- Is a literal single quote always escaped as `''`, or do lone `'` appear unescaped?
- Are `''` always paired within a single pipe-fragment, or do they span fragments (the #744 case)?
- Do `''…''`-quoted phrases ever contain characters that would otherwise be read as structure —
  embedded `|`, commas, semicolons, newlines, or backslash escape sequences like `\n`?
- **(Answered — see above.)** Distinguishing "leading `''`" from "trailing `''`" *does* cleanly
  separate artifacts from legitimate double-prime, so the #744 fix is narrowed to drop only leading
  open-marker fragments (and their paired trailing close-marker), keeping genuine trailing `''`.
- Should the ingest also split `otherdesignations` on `;` (or at least the `;uncharacterized
  protein` join pattern) so those ~0.6M semicolon-joined designations become individual synonyms?
