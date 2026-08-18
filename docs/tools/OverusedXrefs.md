# Overused xrefs

```bash
uv run babel-overused-xrefs --concord <concord file> --out <csv> [--mrconso <MRCONSO.RRF>]
```

Answers: **which xref targets in this concord are claimed by so many subjects that they will fuse
unrelated cliques?**

Every concord row is handed to `glom()` as an equivalence assertion, so one target named by many
subjects merges all of them into a single clique. Many ontologies use `oboInOwl:hasDbXref` to mean
"this term is *about* that thing" rather than "is the same as", and classification vocabularies
make it worse: an ICD-10 billing code names a whole disease *family*, so every subtype that cites
it collapses together. See [`docs/sources/CLAUDE.md`](../sources/CLAUDE.md) ("An OBO `hasDbXref` is
not an equivalence").

Babel has two defences, and this tool is how you choose between them. `remove_overused_xrefs()`
drops any target claimed by two or more subjects, whatever its namespace; a disease source opts
into it by joining `OVERUSE_FILTERED_CONCORDS` in `src/createcompendia/diseasephenotype.py`. A
**categorical prefix exclusion** instead drops every row targeting a namespace, at the point the
concord is built (`DOID_EXCLUDED_XREF_PREFIXES`, `EFO_EXCLUDED_XREF_PREFIXES`,
`ubergraph.build_sets(ignore_list=…)`).

Overuse is a statistical proxy; a prefix rule is a statement about what the namespace *means*.
Reach for the exclusion when a whole vocabulary is the wrong kind of thing — ICD codes name
disease families, so no DOID→ICD xref is an equivalence no matter how few subjects cite it — and
for the overuse filter when a namespace is usually right but occasionally promiscuous. Run this
tool **before** trusting a new source's xrefs, and again after a filtering change to see what is
left. `--min-subjects 1 --target-prefixes …` enumerates exactly what a categorical exclusion
would drop, which is what makes a wholesale removal reviewable.

## Output

One row per (target, subject) pair — long format, so it sorts and filters in a spreadsheet without
unpacking a delimited cell:

```csv
target,target_label,target_prefix,subject_count,subject,subject_label
ICD10:G11.4,Hereditary spastic paraplegia,ICD10,60,DOID:0110764,hereditary spastic paraplegia 11
ICD10:G11.4,Hereditary spastic paraplegia,ICD10,60,DOID:0110782,hereditary spastic paraplegia 31
```

`subject_count` repeats on every row of a target so you can sort by it. Rows are ordered
most-claimed target first, then by target and subject, so a regenerated file diffs cleanly.

Read it by sorting on `subject_count` and scanning `subject_label`: a target whose subjects carry
many *different* names is one that will fuse unrelated concepts. Sixty rows reading "hereditary
spastic paraplegia 11", "…31", "Mast syndrome", "Troyer syndrome" against one code is the shape
you are looking for.

## Labels

Labels come from `babel_downloads/<PREFIX>/labels`, the same files the build uses. Prefixes Babel
*references* but never *ingests* — ICD-10, ICD-9, SNOMED — have no such file, and those are
exactly the promiscuous ones, so pass `--mrconso babel_downloads/UMLS/MRCONSO.RRF` to resolve them
from UMLS. Without it those cells are empty and the audit is a page of bare codes. The tool logs
how many CURIEs it could not label and their prefixes.

The MRCONSO match is a heuristic — code equality plus a `SAB` that starts with the CURIE prefix's
first token, upper-cased, rather than a curated SAB table — so it is generous by design and fine
for an audit, but not a source of authoritative labels. The upper-casing matters because a concord
prefix need not be spelled like its SAB: MONDO and HP write `orphanet:558`, and matching that
case-sensitively left every Orphanet row blank on a case-sensitive filesystem while looking correct
on macOS. `MIM:` is aliased to `SAB=OMIM`, which no prefix-of-SAB rule could bridge. Only English
(`LAT=ENG`) non-suppressed
(`SUPPRESS=N`) rows are used; a CURIE whose only strings are obsolete stays unlabelled, which is
itself worth noticing.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--concord` | required | Concord file to audit (`subject<TAB>predicate<TAB>object`). |
| `--out` | required | Where to write the CSV. Parent directories are created. |
| `--min-subjects` | `2` | Report a target claimed by at least this many subjects. The default matches `remove_overused_xrefs`, so the output is exactly the rows that filter would drop; raise it to see only the worst offenders, or set `1` to list every row. |
| `--target-prefixes` | *(all)* | Comma-separated target namespaces to restrict to, matched case-insensitively (e.g. `ICD10,ICD9,ICD0,ICD11`). With `--min-subjects 1`, this enumerates every row a categorical prefix exclusion would drop. |
| `--downloads-root` | `babel_downloads` | Root holding the per-prefix `labels` files. |
| `--mrconso` | *(none)* | UMLS `MRCONSO.RRF`, used only for CURIEs with no per-prefix labels file. |

## Worked example

[`docs/sources/DOID/mappings.md`](../sources/DOID/mappings.md) is the case this tool was built
for: DOID's ICD-10 xrefs merged 61 hereditary spastic paraplegia subtypes into one 223-identifier
clique. Both of its committed CSVs are this tool's output, and together they show the two
treatments a source's xrefs can get — `icd-targets.csv` (`--min-subjects 1 --target-prefixes
ICD10,ICD9,ICD0,ICD11`) enumerates the 6,420 rows a *categorical prefix exclusion* drops, while
`overused-targets.csv` (the default audit, run after that exclusion) is the record for the 533
targets whose overuse is still an open question.
