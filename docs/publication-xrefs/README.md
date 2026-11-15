# Publication xrefs

**Nothing is equivalent to a publication except another publication.** Ontologies cite the paper a
term was curated from as `oboInOwl:hasDbXref`, in the same shape as a mapping, and every concord row
reaches `glom()` as an equivalence assertion whatever the source meant by it. So a concord row
with a publication on one side and anything else on the other always says something false: that a
disease, phenotype or process *is* a paper.

## The build control

- `rule check_for_publication_xrefs` (`src/snakefiles/duckdb.snakefile`) runs
  `src.reports.duckdb_reports.check_for_publication_xrefs()` over the build's
  `duckdb/Concord.parquet` and writes every row with a publication CURIE on exactly one side to
  `reports/duckdb/publication_xrefs.tsv` (`concord`, `subject`, `predicate`, `object`). A
  publication is any of `PUBLICATION_PREFIXES`: PMID, PMC and doi — the prefixes Babel's own
  Publication compendium uses — plus PMCID, matched case-insensitively. Rows with a publication on
  both sides, such as `publications/concords/PMID_DOI`, are fine and not reported.
- `rule assert_no_unexpected_publication_xrefs` raises for every row of that report not in
  `input_data/known_publication_xrefs.tsv`, and refuses an allowlist row that names no issue. Like
  the duplicate-clique-leader check (`docs/Architecture.md`, "Build controls"), the report is
  written first, and the failure stops `reports/duckdb/done` and `rule all` while every other output
  completes.

## Fixing a failure

Drop the publication prefixes where the concord is written, as these do:

| Concord | Exclusion | Record |
|---|---|---|
| `disease/concords/EFO` | `diseasephenotype.EFO_EXCLUDED_XREF_PREFIXES` | `docs/sources/EFO/pmid-xrefs/` (#1199) |
| `disease/concords/HP` | `diseasephenotype.HP_XREF_IGNORE_PREFIXES` | `docs/sources/HP/pmid-xrefs/` (#1201) |
| `process/concords/GO` | `processactivitypathway.GO_XREF_IGNORE_PREFIXES` | [`../sources/GO/publication-xrefs.md`](../sources/GO/publication-xrefs.md) |

For an `ubergraph.build_sets()` concord that is its `ignore_list` (upper-case entries, since it
compares upper-cased prefixes); for a source with its own handler, its exclusion argument. Before
dropping, record the rows and check what dropping them does to cliques — each record above has a
replay or an argument for why none is needed. Allowlist a row only when an issue accepts it for now.

## What 2026jul22 contained

[`publication_xrefs-2026jul22.tsv`](publication_xrefs-2026jul22.tsv) is
`check_for_publication_xrefs()` over the 2026jul22 build's `Concord.parquet`: 6,110 rows.

| Concord | Rows | Example |
|---|---|---|
| `disease/concords/EFO` | 6,106 (6,105 PMID, 1 doi) | `EFO:0010817` → `PMID:32546850` |
| `disease/concords/HP` | 2 | `HP:0032417` "Periglomerular fibrosis" → `PMID:32866505` |
| `process/concords/GO` | 2 | `GO:0052165` → `PMID:28805743` |

None had merged two cliques: an overuse filter removed the papers several terms of one source cite,
and `write_compendium()` dropped the rest, since no class those compendia hold registers a
publication prefix. But the first paper two sources both cited would have merged their cliques
through it, with nothing in the build to say so.

To regenerate it against another build:

```bash
uv run python -c '
import src.reports.duckdb_reports as d
d.check_for_publication_xrefs("<build>/duckdb/Concord.parquet", "publication_xrefs.duckdb",
                              "publication_xrefs-<build>.tsv", {"memory_limit": "8GB"})'
```

A remote `https://` path to a published build's `Concord.parquet` works too, without downloading
it (about two minutes for 2026jul22).
