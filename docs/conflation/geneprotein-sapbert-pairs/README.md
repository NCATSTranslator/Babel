# What GeneProtein conflation adds to the SAPBERT training pairs

Babel writes three gene and protein files to `sapbert-training-data/`
([format](../../DataFormats.md#sapbert-training-data)): `Gene.txt.gz`, `Protein.txt.gz` and
`GeneProteinConflated.txt.gz`. The conflated file merges each gene with the proteins it encodes, so
it alone can pair a gene name with a protein name. Should a SAPBERT model train on those pairs, or
on gene names and protein names separately?
[#1263](https://github.com/NCATSTranslator/Babel/issues/1263) holds the decision. This directory
holds the measurements behind it.

[`scripts/analyze_cross_pairs.py`](scripts/analyze_cross_pairs.py) reads a finished build's Parquet
exports and describes every pair that only the conflated record can produce. It counts the whole
population of names, not the exporter's sample of 50 pairs per record. With `--filtered-pairs` it
also classifies each row of a `CURIE||name1||name2` file, such as a conflated export with the
`Gene` and `Protein` pairs removed.

## 2026jul22

Full tables: [`2026jul22.md`](2026jul22.md). The build has 16,006,131 conflation groups holding
19,193,730 proteins.

- **Nearly every protein-side name is an entry label.** `readlabels()` in
  `src/datahandlers/uniprotkb.py` labels a UniProtKB record with its entry name, protein name and
  source, for example `A0A9Y1QQF1_HUMAN Breast cancer type 1 susceptibility protein (trembl)`.
  Protein synonyms come only from PR and UMLS (`config.yaml: protein_synonyms`), so that label is
  a TrEMBL protein's only name. The names proteins have and their genes lack are 18,930,956 TrEMBL
  labels, 262,774 Swiss-Prot labels and 464,991 other names. The other names sit in 91,057
  groups, 0.6% of all groups.
- **So nearly every new pair contains an entry label.** Conflation makes 62.2M new pairs possible:
  50.1M of a gene name with a protein name, and 12.1M between two sibling proteins of one gene.
  At least 94.6% contain an entry label. In 34.8% of TrEMBL labels the protein name inside the
  label is already a name of the gene.
- **A gene with a well-named protein already shares a name with it.** Of the 91,057 groups with a
  protein-only name that is not an entry label, 88,750 also have a name the gene and a protein
  share. An identical string has one embedding, so the shared name already ties both sides
  together when they are trained separately. 2,307 groups, 63 of them human, have no shared name.
- **Generic names are common.** `uncharacterized protein` is a name in 2,192,215 groups and
  `hypothetical protein` in 1,634,366. 44,002 names are used by 100 or more groups.

The filtered file checked for #1263 agrees. Of its 52,803,002 rows, 87.3% pair a gene name with a
protein name and 11.3% pair two sibling proteins. The other 1.4% could also have been drawn for
`Gene.txt` or `Protein.txt`, because each export draws its own random 50 pairs per record. Of the
gene and protein rows, 96.3% have a TrEMBL entry label as the protein name.

These numbers favour training on `Gene` and `Protein` separately.

## What this does not show

- Whether a model trained with these pairs links gene and protein mentions better. Only a model
  evaluation can say; #1263 proposes one.
- Anything about a later build. The UniProtKB label code is unchanged on `main` since the
  `2026jul22` tag, but rerun the script before relying on these numbers for another build.
- Pairs with the preferred name. The exporter pairs a record's `names`, and uses the preferred
  name only for a record with a single name, so the script counts `names` alone.
- An exact count of sibling-protein pairs. It is slightly low for a gene whose proteins share a
  name with each other.

## Rerunning

The script needs four Parquet files of the build, in the layout the build publishes them:
`duckdb/parquet/filename=GeneProtein/Conflation.parquet`, `filename=Gene/Synonyms.parquet`,
`filename=Gene/Edge.parquet` and `filename=Protein/Synonyms.parquet`. For 2026jul22 they total
28 GB; download them from the published build first.

```bash
uv run python docs/conflation/geneprotein-sapbert-pairs/scripts/analyze_cross_pairs.py \
    --build-dir data/2026jul22 --workdir data/geneprotein-sapbert-pairs \
    --filtered-pairs <CURIE||name1||name2 file> \
    --output docs/conflation/geneprotein-sapbert-pairs/2026jul22.md
```

On a 32 GB laptop with `--memory-limit 22GB` the whole run, filtered file included, took two to
three minutes and left a 12 GB DuckDB file in `--workdir`. `--reuse` rebuilds the report from that
file without rebuilding its name tables. The examples section resolves its CURIEs with
`get_biolink_prefix_map()`, which fetches the Biolink prefix map.

The script relies on every conflation ID leading its own clique, which
[`../split-cliques/`](../split-cliques/README.md) checked for 2026jul22. Its first section counts
the conflation IDs with no synonym record, which is zero while that holds.
