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

Babel's defence is `remove_overused_xrefs()`, which drops any target claimed by two or more
subjects; a disease source opts into it by joining `OVERUSE_FILTERED_CONCORDS` in
`src/createcompendia/diseasephenotype.py`. This tool is how you decide whether a source needs
that, and what it costs — run it **before** trusting a new source's xrefs, and again after a
filtering change to see what is left.

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
first token, rather than a curated SAB table — so it is generous by design and fine for an audit,
but not a source of authoritative labels. Only English (`LAT=ENG`) non-suppressed
(`SUPPRESS=N`) rows are used; a CURIE whose only strings are obsolete stays unlabelled, which is
itself worth noticing.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--concord` | required | Concord file to audit (`subject<TAB>predicate<TAB>object`). |
| `--out` | required | Where to write the CSV. Parent directories are created. |
| `--min-subjects` | `2` | Report a target claimed by at least this many subjects. The default matches `remove_overused_xrefs`, so the output is exactly the rows that filter would drop; raise it to see only the worst offenders. |
| `--downloads-root` | `babel_downloads` | Root holding the per-prefix `labels` files. |
| `--mrconso` | *(none)* | UMLS `MRCONSO.RRF`, used only for CURIEs with no per-prefix labels file. |

## Worked example

[`docs/sources/DOID/overused-xrefs.md`](../sources/DOID/overused-xrefs.md) is the case this tool
was built for: DOID's ICD-10 xrefs merged 61 hereditary spastic paraplegia subtypes into one
223-identifier clique, and 831 of its xref targets turned out to be overused. Its committed
`overused-targets.csv` is this tool's output.
