# Babel Analysis Scripts

This package contains standalone CLI scripts for analyzing Babel pipeline outputs.
Each script requires the DuckDB/Parquet export step to have completed first.

## Available Scripts

### `umls-report`

Reports on UMLS identifiers (`UMLS:C<digits>`) found across all compendia Parquet files.

```bash
uv run umls-report --help
uv run umls-report -o umls_report.csv
```

Produces a CSV with columns: `umls_id`, `url`, `filename`, `clique_leader`,
`clique_leader_prefix`, `biolink_type`.
