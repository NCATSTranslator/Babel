# Check concords

```bash
uv run babel-check-concords <file, directory or URL> [...]
```

Answers: **would any row of these concords fail the build's concord parser?**

Every concord reader in Babel goes through `read_concords()` / `parse_concord_line()` in
[`src/model/intermediates.py`](../../src/model/intermediates.py). A valid row is exactly three
tab-separated columns, none empty and none with whitespace around it. Anything else raises
`MalformedConcordRowError`, naming the file and line. Nothing skips a bad row. Concord readers used
to disagree on this: `glom_from_files()` skipped short rows, the protein loader crashed on them, the
metadata writer only logged a warning, and the DuckDB export dropped them.

That strictness only holds up if the concords a real build writes already pass. Run this tool:

- before tightening the parser, over a recent build, to see what the change would break;
- after changing a data handler that writes a concord, over its output;
- on any concord from outside the build before trusting it.

## Usage

Each argument is a concord file, a directory, or an `http(s)://` URL. A directory is searched for
files under any `concords/` directory, including a directory that is itself inside one (such as
`chemicals/concords/UNICHEM`). It skips the metadata sidecars (`metadata-<file>.yaml` and
`metadata.yaml`), using `is_metadata_sidecar()`, the same rule the DuckDB export uses. A URL ending
in `/` is treated as a web server's directory listing and crawled the same way, descending only
into subdirectories of the listing it started from. Files are streamed, not downloaded, so a whole
published build can be checked from a laptop:

```bash
uv run babel-check-concords babel_outputs/intermediate
uv run babel-check-concords https://stars.renci.org/var/babel/2025dec11/intermediate/
```

Output is one tab-separated line per file, plus the first rejected line of each kind. The tool
exits 1 if any row was rejected, and raises if it found no concord files at all:

```text
file    rows    rejected        reasons
…/disease/concords/EFO  28559   3       whitespace around a column: 3
#   first 'whitespace around a column' at line 4825: 'EFO:0011048\toboInOwl:hasDbXref\t MedDRA:10059516\n'
```

## What the 2025dec11 and 2026jul22 builds contained

The parser was made strict in the same change that added this tool. Before that, every reader split
`line.strip()`, which removes whitespace at the ends of a line. A padded *last* column, or a
trailing tab that made a fourth column, went through unnoticed.

[`check-concords-2025dec11.tsv`](check-concords-2025dec11.tsv) is the full scan of the 2025dec11
build's 52 concord files: 224,328,587 rows, 478 rejected, all coming from two writers.

| Concord | Rejected | What | Example |
|---------|----------|------|---------|
| `disease/concords/EFO` | 3 | xref literal with a leading space | `EFO:0011048` → `" MedDRA:10059516"` |
| `publications/concords/PMID_DOI` | 457 | DOI ending in a space | `PMID:2353318` → `"doi:10.1002/tera.1420410608 "` |
| `publications/concords/PMID_DOI` | 18 | DOI ending in a tab (a fourth column) | `PMID:9127676` → `"doi:10.1076/apab.104.7.814.13110\t"` |

Both come from the source data. EFO 3.95.0's `efo.owl` has
`<oboInOwl:hasDbXref> MedDRA:10059516</oboInOwl:hasDbXref>`, and 60 hasDbXref literals in that file
are padded; `EFOgraph.get_xrefs()` in `src/datahandlers/efo.py` now strips them before writing the
row. With the space gone, `opt_to_curie()` normalizes that xref's prefix to `MEDDRA:`, the same as
EFO's other 607 MedDRA xrefs. The DOIs come from the PubMed XML baseline those builds parsed. PubMed
is now read from a pubmed2db export instead, and `parse_pubmed2db_into_tsvs()` repairs or skips any
DOI containing whitespace before it reaches the concord (`docs/sources/PubMed/README.md`,
"Malformed DOIs").

Stripping EFO's padding turns the three rejected EFO rows into ordinary edges, so it could change
cliques. Checked against 2025dec11's concords and `Edge` tables, it changes at most one:

- `EFO:0010695` → `PMID:25167691` and `EFO:0007836` → `PMID:27149984` (each had a trailing space)
  change nothing. PMID is not a disease or phenotype prefix, the EFO concord already carries 6,204
  PMID xrefs, and no other disease concord row names either PMID, so neither can join two cliques.
- `EFO:0011048` "dermatological toxicity" → `MEDDRA:10059516` is the only EFO row naming that
  MedDRA term, so the overuse filter keeps it. 2025dec11 already had the two in one clique. In
  2026jul22, `MEDDRA:10059516` sits with `UMLS:C1167791` "Skin toxicity" through the UMLS concord,
  and no EFO row names `EFO:0011048`. So a build whose EFO still carries the xref adds
  `EFO:0011048` to that clique.

2026jul22 published no `intermediate/` tree, so it was cross-checked through its
`duckdb/Concord.parquet`, which keeps column values verbatim, queried in place as in
[`docs/DataFormats.md`](../DataFormats.md) ("Querying a published build without downloading it"):

```sql
SELECT regexp_replace(filename, '.*/intermediate/', '') AS concord, count(*) AS padded
FROM read_parquet('https://stars.renci.org/var/babel/<build>/duckdb/Concord.parquet')
WHERE regexp_matches(subj, '^\s|\s$') OR regexp_matches(pred, '^\s|\s$') OR regexp_matches(obj, '^\s|\s$')
   OR subj IS NULL OR pred IS NULL OR obj IS NULL
GROUP BY ALL;
```

It found the same two writers: 440 padded DOIs in `PMID_DOI` and 2 padded xrefs in `EFO`, and no
empty columns, across 51 files and 231,483,535 rows. It cannot show wrong-column-count rows,
because that build's export dropped them (see `docs/DataFormats.md`).
