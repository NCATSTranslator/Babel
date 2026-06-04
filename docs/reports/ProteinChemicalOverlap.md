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

## Implementation

`src/reports/protein_chemical_overlap.py` (rule `generate_protein_chemical_overlap_report` in
`src/snakefiles/reports.snakefile`). The core function,
`generate_protein_chemical_overlap_report()`, takes explicit compendium, concord, and output paths
so it is straightforward to unit-test on small fixtures
(`tests/reports/test_protein_chemical_overlap.py`).
