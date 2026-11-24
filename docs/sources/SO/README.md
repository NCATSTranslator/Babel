# SO — the Sequence Ontology, and why Babel does not ingest it

Babel does not ingest the [Sequence Ontology](http://www.sequenceontology.org/) (SO), and as of
November 2026 there is no plan to. This page records why, so the question doesn't have to be
reopened from scratch. In short, SO names *kinds* of sequence features and variants. The Biolink
Model already treats its most important terms as classes and predicates. The rest are finer types,
properties and lab artefacts, not entities that Translator KGs make statements about. SO would also
join nothing already in Babel.

The question is part of a wider one: should Babel emit general ontology classes that name a Biolink
class? See [#1273](https://github.com/NCATSTranslator/Babel/issues/1273). If that is settled in a
way that changes the reasoning below, update this page.

## How SO relates to the Biolink Model

The Biolink Model uses SO to *define* its classes, not as an identifier space for the things those
classes describe. No Biolink class lists `SO` in its `id_prefixes`, so `write_compendium()` would
drop every SO identifier as things stand. Instead, Biolink maps 16 of its classes and 5 of its
predicates to SO terms ([`biolink-so-mappings.csv`](biolink-so-mappings.csv)). Some examples:

- `biolink:Gene` is an exact match to [`SO:0000704`](http://purl.obolibrary.org/obo/SO_0000704)
  "gene".
- `biolink:NucleicAcidEntity` is an exact match to the SO root,
  [`SO:0000110`](http://purl.obolibrary.org/obo/SO_0000110) "sequence_feature".
- `biolink:SequenceVariant` is a close match to
  [`SO:0001060`](http://purl.obolibrary.org/obo/SO_0001060) "sequence_variant".
- `biolink:is_missense_variant_of` is an exact match to
  [`SO:0001583`](http://purl.obolibrary.org/obo/SO_0001583) "missense_variant".

So `SO:0000704` *is* the concept `biolink:Gene` stands for. A Babel clique for it would be a
`Gene`-typed node meaning "gene in general", next to NCBIGene records that are each one specific
gene.

`biolink:AccessibleDnaRegion` was mapped to
[`SO:0002231`](http://purl.obolibrary.org/obo/SO_0002231) "self_cleaving_ribozyme". The intended
term is [`SO:0002331`](http://purl.obolibrary.org/obo/SO_0002331) "accessible_DNA_region";
[biolink/biolink-model#1863](https://github.com/biolink/biolink-model/pull/1863) fixes it. Every
other SO ID in Biolink matches its SO label.

Biolink also ships an SSSOM file, `ncbitype-soterm-sssom-mapping.yaml`, that maps NCBI Gene's
`type_of_gene` values to SO terms (`protein-coding` →
[`SO:0000010`](http://purl.obolibrary.org/obo/SO_0000010) "protein_coding"). That is the shape in
which SO most naturally reaches Translator: as the *value* of a property of a gene or variant, not
as a node.

## What the rest of SO is

SO release 2026-08-07 has 2,409 live terms. [`so-term-buckets.csv`](so-term-buckets.csv) assigns
each one to the nearest ancestor that a Biolink class maps to, and splits the rest by SO's own
branches. Grouped:

| Group | Terms | Examples | What they are |
| --- | --- | --- | --- |
| Subtypes of a Biolink class | 570 | `antisense_lncRNA_gene` (Gene, 138); `alanyl_tRNA` (ncRNA, 116); `polycistronic_transcript` (Transcript, 104); `operator`, `enhancer` (RegulatoryRegion, 147); `coding_exon`; `C_to_T_transition` (Snv) | Finer *types* of things Biolink has a class for. Their instances are database records (Ensembl, RefSeq, NCBI Gene), not SO terms. |
| Other biological regions | 996 | `CpG_island`, `G_quartet`, `satellite_DNA`, `INR_motif`, `beta_turn_type_six_a`, `alanine` (a residue) | Motifs, repeats, protein secondary structure, residues and modified bases. Only the root `sequence_feature` is mapped. |
| Variant consequences | 238 | `missense_variant`, `stop_gained`, `5_prime_UTR_variant`, `2KB_upstream_variant` | How a variant relates to a gene or transcript. Translator says this with predicates. |
| Sequence attributes | 233 | `protein_coding`, `capped`, `circular`, `benign_variant`, `common_variant` | Properties, not entities. |
| Lab and assay artefacts | 250 | `contig`, `read_pair`, `match_part`, `BAC_end`, `PCR_product`, `morpholino_oligo`, `clone_insert_end` | Assembly, alignment and lab objects. |
| Karyotype variation | 82 | `aneuploid`, `hyperploid`, `chromosomal_inversion`, `compound_chromosome_arm` | Better covered as phenotypes and diseases (HP, MONDO). |
| Sequence alterations | 40 | `deletion`, `insertion`, `translocation`, `MNP` | Kinds of variants, not variants. |

176 terms have only an underscored label (`5_prime_UTR_uORF_frameshift_variant`) and no spaced
exact synonym. Name Resolver would need a label rewrite rule before it could find them by name.

## Why Babel does not ingest it

- **They are types, not things.** Each Biolink-mapped term heads a subtree of narrower types, and
  `antisense_lncRNA_gene` is a kind of gene, not a gene. Under the most permissive policy #1273
  could adopt (emit ontology classes typed by branch), about 140 "kind of gene" cliques would land
  in `Gene.txt` beside NCBIGene records. Consumers that treat a `Gene` node as one gene (gene-set
  tools, GeneProtein conflation, taxon assignment) would mishandle them.
- **Biolink already covers how Translator uses SO.** The common terms are classes, and the common
  variant consequences are predicates. A KG that needs "this gene is a lncRNA gene" needs a Biolink
  slot or subclass, not a Babel clique.
- **Nothing would join.** SO's own `hasDbXref`s are URLs, RNAMOD, PSI-MOD and LOINC codes, and
  none of them are equivalences. In UberGraph, only 22 xrefs from other ontologies point at SO (from
  RO, FBcv and GO), and none are equivalences either. All 2,409 terms would land as standalone
  cliques: deposited rather than joined (see "Prefer joining an existing clique" in
  [`AddingNewSources.md`](../../AddingNewSources.md)).
- **No Biolink class registers the prefix.** Shipping anyway would need `extra_prefixes=[SO]`
  against a class SO terms don't fit.

The same concepts *do* already reach Babel through NCIT, MeSH and UMLS, often under types that
don't fit them. MeSH "Exons" is a `ChemicalEntity`, UMLS "Missense Mutation" is a `Disease`, and
UMLS "Genome" is a `Gene`. That is tracked in
[#1274](https://github.com/NCATSTranslator/Babel/issues/1274). Adding SO would not fix it, because
there is no mapping to join SO terms to those cliques.

## What would change this

- **A KG uses SO terms as nodes**, and NodeNorm needs to normalize them. Variant consequences are
  the likeliest case. Neither ROBOKOP nor NodeNorm had any SO nodes in November 2026.
- **Biolink registers `SO`** in a class's `id_prefixes`, which would be Biolink saying SO terms are
  entities of that class.
- **#1273 settles on emitting general ontology classes** for classes like `Gene`.

If any of these happens, the analysis here is the starting point. Ingesting the terms is a plain
UberGraph walk from [`SO:0000110`](http://purl.obolibrary.org/obo/SO_0000110) "sequence_feature"
that keeps only `SO_` IRIs, because UberGraph places MRO, PR, CHEBI and Ensembl classes under it
too. The hard parts are the typing decision and the 176 underscored labels.

## Regenerating the tables

```bash
mkdir -p data/so-analysis
curl -sL -o data/so-analysis/so.obo http://purl.obolibrary.org/obo/so.obo
uv run python docs/sources/SO/scripts/bucket_so_terms.py \
    --so-obo data/so-analysis/so.obo \
    --buckets-out docs/sources/SO/so-term-buckets.csv \
    --mappings-out docs/sources/SO/biolink-so-mappings.csv
```

The script reads Biolink's SO mappings from the version in `config.yaml`, so a Biolink release that
fixes or adds a mapping changes both tables. The committed tables were generated with Biolink 4.4.3,
before #1863 merged, so they still show the `self_cleaving_ribozyme` mapping.
