# NCBIGene synonym-field quoting

NCBI's `gene_info.gz` packs multiple values into two pipe-delimited free-text columns that Babel
reads as synonyms:

- `Synonyms` (column index 4) — the NCBI web-API `otheraliases` field.
- `Other_designations` (column index 13) — the NCBI web-API `otherdesignations` field.

Babel splits each on `|` and adds the pieces as synonyms
(`src/datahandlers/ncbigene.py:pull_ncbigene_labels_synonyms_and_taxa`).

## Why we're studying the quoting

[Issue #744](https://github.com/NCATSTranslator/Babel/issues/744) reported malformed synonyms:
NCBI wraps some comma-containing values in `''…''` and then turns their internal commas into `|` —
the same character that delimits the column — so the value's pieces arrive as separate fragments.
The fix drops fragments that start *or* end with `''`.

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

- **Semicolon-joined values (`otherdesignations` only).** **624,799** designation rows join
  multiple values with a `;` and no pipe at all — e.g. `ribosomal protein S2;uncharacterized
  protein`. That is 98.6% of the 633,842 no-pipe rows containing a `;` (only 8,885 are within-name
  nomenclature). A plain `split("|")` keeps these as one combined synonym. Whether that matters is
  examined in "Should the semicolon be a delimiter too?" below — mostly it should not.
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

### Should the semicolon be a delimiter too? (No.)

The ~624,799 semicolon-joined `otherdesignations` rows look at first like distinct designations
that a `split("|")` fails to separate, but examining the text *after* each `;` shows otherwise:

- **95.8%** of these rows are *isoform enumerations* — every segment is the **same base name** with
  only a different trailing enumerator: `X isoform 1;X isoform 2;X isoform 3;…`. The `;` separates
  isoforms of one protein, not two different designations.
- The post-`;` text is **highly variable, not a shared boilerplate tag**: 96,114 distinct
  last-segment strings, and the 20 most common cover only 7.3%. The top entries are exactly the
  isoform pattern (`uncharacterized protein isoform 2`, `… isoform 3`, plain `uncharacterized
  protein`, …). So neither "it's one tag we should strip" nor "these are distinct useful synonyms"
  holds.
- Only ~4.2% (~26k rows) have genuinely different base names across the `;`, and there the extra
  segment is usually a low-value generic (`uncharacterized protein`, `hypothetical protein`).
- Segment counts run from 2 (the majority) up to **50**.

**Decision: do not split `otherdesignations` on `;`.** Splitting would mostly manufacture
near-duplicate `X isoform N` synonyms rather than surface new distinct names, and the genuinely
different minority gains little. The only real cost of leaving it joined is that high-isoform genes
produce a long, non-matching combined synonym; if that ever matters the better lever is collapsing
the isoform enumeration (keep the base name once), not treating `;` as a delimiter.

## Can the quoted value be reconstructed? No

It is tempting to read `''…''` as ordinary quoting — the pieces between the markers are one value,
so rejoin them with `", "` and recover the original synonym. **That does not work.** 276 rows carry
an open marker in `Synonyms`; 265 of those also have a close marker and a `Full_name` to check
against, and **zero** of them rejoin to it. (`double_prime_report.py` computes this; see the
"Can the quoted value be reconstructed by rejoining the span?" section of the generated report.)

The verbatim row for gene 828367 (`CYP706A2`), the one reported in #744:

```text
Synonyms[4]  : ''cytochrome P450|T12H17.100|T12H17_100|cytochrome P450|family 706|
               polypeptide 2|polypeptide 2''|subfamily A
Full_name[11]: cytochrome P450, family 706, subfamily A, polypeptide 2
```

Four things break the "rejoin the span" model:

- **The pieces are not contiguous.** `T12H17.100` and `T12H17_100` are genuine, unrelated aliases
  sitting *inside* the span. Rejoining everything between the markers gives
  `cytochrome P450, T12H17.100, T12H17_100, cytochrome P450, family 706, polypeptide 2` — garbage.
- **The order is meaningless.** The fragment list looks like set-iteration order, so the pieces of
  the quoted value are scattered rather than adjacent.
- **The commas became pipes.** A `|` separating two aliases is indistinguishable from a `|` that
  was a comma inside one alias, so the span cannot be delimited by structure alone.
- **Both a quoted and an unquoted copy** of the first and last piece are present (`''cytochrome
  P450` *and* a bare `cytochrome P450`; `polypeptide 2` *and* `polypeptide 2''`).

**This costs us nothing, because the value is not lost.** The correct, properly comma-formatted
string is carried by `Full_name_from_nomenclature_authority` and `Other_designations`, both of
which Babel already reads and emits as synonyms. So `cytochrome P450, family 706, subfamily A,
polypeptide 2` is captured regardless.

What *does* remain is junk: the bare comma-pieces (`family 706`, `subfamily A`, …) still come
through as standalone synonyms — roughly a thousand of them across the 276 rows. They are not
malformed, just meaningless. Tracked in
[issue #932](https://github.com/NCATSTranslator/Babel/issues/932), whose proposed fix is to drop
any `Synonyms` fragment that exactly matches a `", "`-piece of the row's `Full_name`.

## Deferred follow-up questions

Once we know which characters are present, the deeper questions (each a likely next script here):

- Is a literal single quote always escaped as `''`, or do lone `'` appear unescaped?
- Do `''…''`-quoted phrases ever contain characters that would otherwise be read as structure —
  embedded `|`, commas, semicolons, newlines, or backslash escape sequences like `\n`?
- **(Answered — see above.)** Distinguishing "leading `''`" from "trailing `''`" *does* cleanly
  separate artifacts from legitimate double-prime, so the #744 fix is narrowed to drop only leading
  open-marker fragments (and their paired trailing close-marker), keeping genuine trailing `''`.
- **(Answered — No; see "Can the quoted value be reconstructed?" above.)** The `''…''` span cannot
  be rejoined into the original synonym: its pieces are interleaved with genuine aliases and
  reordered (0 of the 265 checkable rows rejoin). The value survives via `Full_name` instead.
- **(Answered — No; see "Should the semicolon be a delimiter too?" above.)** The ~0.6M
  semicolon-joined designations are 95.8% isoform enumerations of the same base name, so splitting
  on `;` would mostly produce near-duplicate synonyms. Left joined.
