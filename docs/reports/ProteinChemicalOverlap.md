# Protein/Chemical overlap report

Babel keeps the chemical compendia (`biolink:ChemicalEntity` and its subtypes — `SmallMolecule`,
`Drug`, `MolecularMixture`, `ChemicalMixture`, `ComplexMolecularMixture`, `Polypeptide`) separate
from the protein compendium (`biolink:Protein`). A large family of biomedical concepts straddles
that boundary, though: complex chemicals that are proteins (human insulin), grouping concepts
(hemoglobins, insulins), formulations, and amino-acid sequences. Many source vocabularies
cross-reference a chemical identifier to a protein identifier as if they were the same thing, and
deciding whether — and how — to combine those concepts is an open question for the Translator
community (see Babel issues #706, #662, #667, #440, #513, #276).

This report inventories exactly those crossings so the discussion can be grounded in the actual
data. It is the empirical input to the "list of mappings that would be applied if we combined
proteins and chemicals" called for in issue #706, and a generalization of the UMLS-only report
proposed in issue #667.

## What it computes

The report streams the chemical and protein compendia and every concord (cross-reference) file used
to build them. For each concord edge it asks: did the two endpoints land in *different* cliques, one
on the chemical side and one on the protein side? Those boundary-crossing edges are the
cross-references that *would* merge a chemical clique with a protein clique if we acted on them.

Two discriminators are attached to every crossing to help triage it:

- **`chem_has_inchikey`** — whether the chemical clique contains an `INCHIKEY` structure. A
  structurally-defined small molecule that is cross-referenced to a protein is usually a *bug* (the
  classic example is `CHEBI:24536` "Pepsin" actually being hexachlorocyclohexane). The genuine
  "protein-as-chemical" cases (prothrombin, hemoglobin) characteristically have **no** InChIKey, so
  this single flag separates "probably wrong" from "probably the real philosophical case."
- **`prot_reaches_gene`** — whether the protein clique is GeneProtein-conflated. If it is, merging
  it with a chemical would make that chemical normalize all the way to a *gene* — the confusing
  downstream effect that motivated issue #662.

## Outputs

All files are written under `babel_outputs/reports/protein_chemical/`.

### `bridges.tsv`

One row per boundary-crossing concord edge — the raw evidence. Columns include the source concord
and predicate that asserted the edge, the bridging subject/object CURIEs and which side the subject
was on, and, for each side, the clique leader, label, Biolink type, and clique size, plus
`chem_has_inchikey`, `prot_reaches_gene`, and whether the two leaders share a label (`label_match`).

### `candidate_pairs.tsv`

The bridges deduplicated to unique (chemical clique leader, protein clique leader) pairs, with the
supporting sources, predicates, and example edges aggregated and a `support_edge_count`. This is the
SSSOM-able list of mappings that a DrugProtein conflation (#440) would apply, sorted by how much
evidence supports each pair.

### `duplicate_curies.tsv`

CURIEs that ended up in *both* a chemical clique and a protein clique — the same identifier
duplicated across two cliques (#276/#513). This is scoped to CURIEs that are referenced by a
concord, since those are the cross-reference-induced duplicates relevant here and that scope keeps
the report's memory bounded. For the exhaustive across-the-whole-build duplicate list, query the
DuckDB `Edge` table instead (one CURIE appearing under two `clique_leader`s).

### `summary.tsv`

Per-source counts — bridge edges, distinct candidate pairs, and the InChIKey and gene-reaching
splits — with a `TOTAL` row. This is the quick overview: it shows at a glance which sources are
asserting the most chemical/protein crossings and how many of those involve a structurally-defined
chemical or a gene-conflated protein.

## Running it

The report is wired into the reports Snakefile and runs as part of the standard reports target once
the compendia, conflations, and intermediate concords exist:

```bash
uv run snakemake -c all --rerun-incomplete babel_outputs/reports/protein_chemical/summary.tsv
```

Because it only needs the final compendia, the GeneProtein conflation, and the concord files (all of
which persist as intermediate build artifacts), it can be run against a downloaded build without
rerunning the pipeline — see the intermediate-file download note in `CLAUDE.md`.

## Future work: conflation-chain impact simulator

This report says *which* protein and chemical cliques a merge would combine. It does not say what
the merge would *do* downstream — and that is the question that actually blocks consensus (see
issues #662 and #654). If a chemical clique is merged into a protein clique, and that protein is
already GeneProtein-conflated, then a chemical CURIE ends up normalizing all the way to a *gene*.
The `prot_reaches_gene` column flags where this can happen, but it does not show the concrete
result.

A follow-up tool — a conflation-chain impact simulator (tracked in issue #829) — would close that
gap. Given a candidate
mapping (the `candidate_pairs.tsv` produced here, or a curated/filtered subset of it) plus the
existing `GeneProtein.txt` and `DrugChemical.txt` conflations, it would simulate the *combined*
effect of a hypothetical DrugProtein conflation layered on top of the conflations we already ship,
and report, for a probe set of CURIEs, what each one normalizes to **before vs. after** the merge.

The point is to make the scary cases concrete before anything ships. For example: `DRUGBANK:DB00062`
"Albumin human" is a chemical today; after a DrugProtein merge it would join `UniProtKB:P02768`,
which is GeneProtein-conflated to `NCBIGene:213` ALB — so a drug CURIE would resolve to a gene. A
before/after table over the worked examples is the artifact a committee can actually vote on.

### Sketch

- **Inputs:** `candidate_pairs.tsv` (optionally filtered — e.g. drop `chem_has_inchikey` pairs as
  likely bugs, or keep only `label_match` / high-`support_edge_count` pairs); `GeneProtein.txt`;
  `DrugChemical.txt`; and a probe CURIE list (the worked examples from #440, #654, and gglusman's
  set in #440 — prothrombin, hemoglobin, collagen, collagenase, pepsin, albumin, rituximab,
  cetuximab).
- **Output:** one row per probe CURIE — its current clique leader/type, and its post-merge clique
  leader/type — with a flag when a chemical now reaches a gene, or when two previously distinct
  concepts collapse into one.
- **Directionality knob:** support both the protein-centric framing of #706 (the merged clique
  presents as a `biolink:Protein` that contains chemical IDs) and the alternative of inverting the
  GeneProtein order discussed in #654, so the committee can compare them on the same probes.
- **Reuse:** `geneprotein.merge()` / `gpkey()` ordering, the DrugChemical conflation logic, and the
  DuckDB `Edge` table for fast "which clique contains CURIE X" lookups. A curated probe set should
  be promoted into the `ResolvesWith` / `DoesNotResolveWith` BabelTest fixture started in #513, so
  every proposed option can be scored against the same canonical cases.

## Implementation

`src/reports/protein_chemical_overlap.py` (rule `generate_protein_chemical_overlap_report` in
`src/snakefiles/reports.snakefile`). The core function,
`generate_protein_chemical_overlap_report()`, takes explicit compendium, concord, and output paths
so it is straightforward to unit-test on small fixtures
(`tests/reports/test_protein_chemical_overlap.py`).
