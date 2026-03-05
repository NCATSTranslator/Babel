# SQL Reports

Drop a `.sql` file in this directory to add a new report to the Babel pipeline.
The pipeline will automatically discover all `.sql` files here and run each one against
the Parquet output, writing results to `babel_outputs/reports/sql/<name>.tsv`.

## Available Views

Each SQL file may reference the following pre-registered views:

| View | Description | Key Columns |
|------|-------------|-------------|
| `Nodes` | One row per node (CURIE) with its label | `curie`, `label`, `filename` |
| `Cliques` | One row per clique with its leader and metadata | `clique_leader`, `preferred_name`, `biolink_type`, `filename` |
| `Edges` | One row per CURIE-to-clique membership edge | `curie`, `clique_leader`, `conflation`, `filename` |
| `Synonyms` | One row per synonym | `clique_leader`, `preferred_name`, `biolink_type`, `label`, `filename` |

All views are backed by Parquet files partitioned by `filename` (the semantic type,
e.g. `AnatomicalEntity`, `ChemicalEntity`). DuckDB reads them lazily with
`hive_partitioning=true`, so `WHERE filename = 'Gene'` is efficient.

## DuckDB Configuration (YAML Sidecar)

To control memory or thread limits for a specific query, create a YAML file with the
same base name as the `.sql` file. For example, for `my_report.sql` create
`my_report.yaml`:

```yaml
duckdb_config:
  memory_limit: "20G"
  threads: 2
  preserve_insertion_order: false
```

If no sidecar is present, the pipeline uses built-in defaults from `setup_duckdb()`.

## Example

`label_distribution.sql` counts how often each label length appears across all nodes:

```sql
WITH Lengths AS (
    SELECT curie, label, LENGTH(label) AS label_length FROM Nodes
),
Examples AS (
    SELECT curie, label, label_length,
        ROW_NUMBER() OVER (PARTITION BY label_length ORDER BY label) AS rn
    FROM Lengths
)
SELECT
    label_length,
    COUNT(*) AS frequency,
    MAX(CASE WHEN rn = 1 THEN curie ELSE NULL END) AS example_curie,
    MAX(CASE WHEN rn = 1 THEN label ELSE NULL END) AS example_label
FROM Examples
GROUP BY label_length
ORDER BY label_length ASC
```

Output goes to `babel_outputs/reports/sql/label_distribution.tsv`.

## Running

To run all SQL reports:

```bash
uv run snakemake --cores 1 all_sql_reports
```

To run a specific report (e.g. `label_distribution.sql`):

```bash
uv run snakemake --cores 1 babel_outputs/reports/sql/label_distribution.tsv
```

To force re-run after editing a SQL file or its sidecar:

```bash
uv run snakemake --forcerun run_sql_report --cores 1 all_sql_reports
```
