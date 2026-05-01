# Babel documentation

This folder contains reference documentation for Babel, organized by audience.

## For Babel users — understanding and using outputs

| Document                               | Description                                                                                                                                                                                 |
|----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [Understanding.md](./Understanding.md) | How Babel constructs cliques, chooses preferred identifiers and labels, sources descriptions and IC values, and what split/lumped cliques are. Also covers how to report incorrect cliques. |
| [DataFormats.md](./DataFormats.md)     | Compendium, synonym, and conflation file format specification.                                                                                                                              |
| [Conflation.md](./Conflation.md)       | What conflations are, how GeneProtein and DrugChemical conflation work, and when to use them.                                                                                               |
| [Downloads.md](./Downloads.md)         | Where to download published Babel outputs and which formats are available.                                                                                                                  |

## For pipeline operators — running and deploying

| Document                             | Description                                                                             |
|--------------------------------------|-----------------------------------------------------------------------------------------|
| [RunningBabel.md](./RunningBabel.md) | Build instructions, configuration, Snakemake targets, and system requirements.          |
| [Deployment.md](./Deployment.md)     | Release checklist and deployment instructions for Node Normalization and Name Resolver. |
| [Babel.ipynb](./Babel.ipynb)         | Interactive Jupyter notebook demonstrating what running Babel looks like.               |

## For contributors and maintainers

| Document                             | Description                                                                                                                                                                                                                              |
|--------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [Architecture.md](./Architecture.md)        | Source code layout, data-flow narrative, key data structures (concord files, compendium JSONL), and key patterns (factory pattern, TSVSQLiteLoader, union-find, Biolink Model integration).                                              |
| [Development.md](./Development.md)          | Development workflow, how to obtain prerequisites, how to build individual compendia, known challenges, and ideas for improving the pipeline.                                                                                            |
| [Metadata.md](./Metadata.md)                | The `metadata.yaml` schema, the helpers in `src/metadata/provenance.py`, the recursive `combined_from` pattern, and the conventions for adding new metadata-emitting rules.                                                              |
| [Triage.md](./Triage.md)                    | **Part 1 (for users):** how to file a useful bug report, assign priority/impact/size, and track when your issue will be addressed. **Part 2 (for developers):** triage checklist, automated test syntax, and sprint planning heuristics. |
| [AddingSources/](./AddingSources/README.md) | Conventions and checklist for adding a new external data source to Babel: dry-run smoke test, metadata.yaml as the source of truth for counts, predicate policy, per-source documentation requirement.                                  |
| [sources/](./sources/)                      | Per-source documentation. Each subdirectory describes one external data source: its provenance, the identifiers it contributes, the cross-references it brings in, and any known integration concerns.                                  |
