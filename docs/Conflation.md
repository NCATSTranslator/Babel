# Babel Conflation

Babel is designed to produce cliques of _identical_ identifiers, but our users would sometimes like
to combine identifiers that are similar in some other way. Babel generates "conflations" to support
this.

Babel currently generates two conflations:

1. GeneProtein conflates gene with the protein transcribed from it.
   The gene identifier will always be returned.
2. DrugChemical conflates drugs with their active ingredients as a chemical. For each conflation,
   the identifiers are arranged in order of (1) preferred prefix order for the
   [ChemicalEntity Biolink type](https://biolink.github.io/biolink-model/ChemicalEntity/#valid-id-prefixes),
   followed by (2) within each prefix group: lower information content first, larger cliques first,
   and finally from the numerically smallest suffix to the numerically largest suffix.

## How are conflations generated in Babel and used in NodeNorm?

Each conflation file is a JSON-Lines (JSONL) file, where every line is a JSON list of clique
identifiers, which are stored in Redis databases in NodeNorm. If a particular conflation is turned
on, NodeNorm will:

1. Normalize the input identifier to a clique identifier.
2. If the clique identifier is not part of any conflation, we return it as-is.
3. If the clique identifier is part of a conflation, we construct a new clique whose preferred
   identifier is the first identifier in the clique, and which consists of all the identifiers from
   all the cliques included in that conflation.

## Estimating a prospective DrugProtein conflation (issue #706)

Proteins and chemicals are built by separate pipelines, and the identifiers that could be either
(UMLS, MESH) are deliberately kept apart between them, so no compendium records a
protein-clique -> chemical-clique edge.
[Issue #706](https://github.com/NCATSTranslator/Babel/issues/706) asks whether we should
_optionally_ re-join them with a new **DrugProtein** conflation (for example, conflating insulin the
protein with insulin the chemical and specific insulin formulations). Before building it, we need to
quantify what it would look like.

The `drugprotein_conflation_estimate` rule (`src/reports/drugprotein_conflation_report.py`) produces
that estimate without changing any compendium. It reuses the bridge edges that already exist on
disk: the DrugChemical relationship concords
(`intermediate/drugchemical/concords/{RXNORM,UMLS,PUBCHEM_RXNORM}`) and the manual DrugChemical
concord. These are the only artifacts that relate a protein-pipeline concept and a chemical-pipeline
concept in the same edge. The rule resolves both endpoints of every bridge edge to their clique
leader (via the DuckDB `Edge.parquet` export), keeps the pairs that cross the protein/chemical
boundary, and merges them with the same `glom()` union-find the real conflations use. The kept pairs
are exactly the ones DrugChemical conflation discards today because one side is not a
ChemicalEntity.

It writes three files under `babel_outputs/reports/drugprotein/`:

- `summary.json` — counts of protein and chemical cliques bridged, the number of resulting merged
  cliques, a merged-clique size histogram, and a per-bridge-source breakdown.
- `bridge_edges.tsv.gz` — every cross-pipeline (protein leader, chemical leader, source) pair with
  labels; the reviewable artifact for the issue.
- `top_cliques.csv` — the largest prospective merged cliques with member CURIEs and labels, for
  sanity-checking (insulin and similar).

To produce the same estimate ad hoc against a finished build (for example on the HPC login node,
without re-running the pipeline), run `tools/drugprotein/run_first_cut.py`.

## How are types handled for conflated cliques?

Babel does not assign a type to any conflations. When NodeNorm is called with a particular
conflation turned on, it determines the types of a conflated clique by:

1. Starting with the most specific type of the first identifier in the conflation.
2. Adding all the supertypes of the most specific type for the first identifier in the conflation as
   determined by the [Biolink Model Toolkit](https://github.com/biolink/biolink-model-toolkit).
3. Add all the types and ancestors for all the other identifiers in the conflation without
   duplication.
