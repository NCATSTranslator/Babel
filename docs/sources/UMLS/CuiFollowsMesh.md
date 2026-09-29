# A UMLS CUI follows its MeSH descriptor

Babel types UMLS CUIs and MeSH descriptors independently: each pipeline's `write_umls_ids()`
selects CUIs by UMLS semantic type (`umls.write_umls_ids()`, `src/datahandlers/umls.py`), and each
pipeline's `write_mesh_ids()` selects descriptors by MeSH tree number (`mesh.write_ids()`, see
[`MESH/Ingestion.md`](../MESH/Ingestion.md)). Each pipeline's UMLS concord (`umls.build_sets()`)
then links every CUI it claims to that CUI's MeSH descriptor and DrugBank ingredient. When the two
selections disagree about a CUI, the concord dragged another pipeline's descriptor into this
pipeline's clique, and the same identifiers ended up in two compendia, often leading a clique in
both. Two examples from the 2026jul22 build (issues [#276], [#308], [#1123]):

- [`UMLS:C0000608`](https://uts.nlm.nih.gov/uts/umls/concept/C0000608) "Aminocaproic Acid" is
  T116 "Amino Acid, Peptide, or Protein", so protein claimed it; its descriptor
  [`MESH:D015119`](https://meshb.nlm.nih.gov/record/ui?ui=D015119) "Aminocaproic Acid" is in a
  chemical D-tree, so chemicals claimed that. `protein/concords/UMLS` linked the two, and the
  descriptor (with `DRUGBANK:DB00513`) was in both `Protein.txt` and `SmallMolecule.txt`. 15,658
  MeSH descriptors and 1,145 DrugBank IDs were duplicated this way, and 891 MeSH descriptors led a
  clique in both `ChemicalEntity.txt` and `Protein.txt`.
- [`UMLS:C0242726`](https://uts.nlm.nih.gov/uts/umls/concept/C0242726) "Plant Roots" is T002
  "Plant", so taxon claimed it; [`MESH:D018517`](https://meshb.nlm.nih.gov/record/ui?ui=D018517)
  "Plant Roots" is in anatomy's A18 tree. 36 descriptors led a clique in both `AnatomicalEntity.txt`
  and `OrganismTaxon.txt`, and 18 MeSH `SCR_Chemical` virus records in `ChemicalEntity.txt` and
  `OrganismTaxon.txt`.

Downstream, Redis NodeNorm served whichever compendium loaded last, and NodeNorm-ES merged the two
cliques into one document whose `type` listed both Biolink classes
([biothings/NodeNormalizationAPI#41](https://github.com/biothings/NodeNormalizationAPI/issues/41)).

## The rule

MeSH placement is the tie-breaker. `umls.apply_mesh_ownership()` runs inside `write_umls_ids()`
after the semantic-type blocklist, for every pipeline in `config.yaml`'s
`umls_mesh_owning_pipelines` (anatomy, chemicals, disease, protein, taxon):

1. A CUI whose descriptors are all claimed by *other* pipelines' `ids/MESH` and none by this one is
   **dropped** here.
2. A CUI whose descriptor this pipeline's `ids/MESH` claims, and no other pipeline's does, is
   **added** here, typed as that descriptor (the first own-claimed descriptor in sorted order),
   whether its semantic types put it elsewhere or nowhere.
3. A CUI whose descriptors both this and another pipeline claim (a descriptor MeSH cross-lists in
   two trees, such as [`MESH:D013171`](https://meshb.nlm.nih.gov/record/ui?ui=D013171)
   "Spores, Bacterial" in B05 and A11, or a CUI with one descriptor on each side), or that no
   pipeline claims, is left as its semantic types decided. Rule 2 must not fire here: the first
   draft added such a CUI to every pipeline that claimed the descriptor, which put 47 CUIs into two
   pipelines' `ids/UMLS` and failed `test_no_id_in_multiple_compendia`.

"Descriptor" means the MeSH atoms `build_sets()` concords: English, unsuppressed `SAB=MSH` atoms
whose term type is in `umls.MESH_CONCORD_TTYS` (`MH`, `NM`, `HT`, `QAB`). Both functions read that
constant, so a CUI moves exactly when its descriptor would be dragged; a CUI with only entry-term
atoms (`C0000005` → `D012711` via `PEP`/`ET`) is neither concorded nor moved.

Each `*_umls_ids` Snakemake rule therefore takes `MRCONSO.RRF`, its own `ids/MESH` and the other
four pipelines' `ids/MESH` as inputs (`util.mesh_ids_inputs()`). The MeSH ids rules depend only on
`mesh.nt`, so nothing waits on another pipeline's compendium.

Gene and process write an `ids/UMLS` but no `ids/MESH`, so they are not on the list, but they take
all five `ids/MESH` files as "foreign" and drop a CUI whose descriptor one of the five claims (30
CUIs against UMLS 2026AA, e.g. `UMLS:C1413234` "CD68 gene", which UMLS also gives the protein
descriptor `MESH:D000097382` "CD68 Molecule"). Without that, rule 2 would add the CUI to the
descriptor's pipeline while gene or process still claimed it by semantic type.

Rule 2 is deliberately unconditional. A CUI that no pipeline's semantic types selected but whose
descriptor a pipeline owns used to fall to the leftover compendium (`umls.txt`) as a lone clique,
separated from the descriptor it stands for; now it joins that descriptor's clique. Against
2026jul22 this adds about 4,900 such CUIs to chemicals (T121 "Pharmacologic Substance" and T123
"Biologically Active Substance" CUIs of chemical descriptors) and 191 to disease, of which 150 are
T033 "Finding" CUIs of C-tree descriptors. The disease pipeline still does not map T033 by
semantic type (see the comment in `diseasephenotype.write_umls_ids()` and issue #569): only a
Finding CUI that *is* a disease descriptor's own concept joins it.

## What it changes, measured before a build

`scripts/replay_mesh_ownership.py` in `cui-follows-mesh/` runs the production writers with and
without the rule against a local UMLS download and a published build's ids files, and predicts which
duplicate leaders the rule resolves by finding the `<pipeline>/concords/UMLS` edge that dragged each
one. Its output for 2026jul22 is [`cui-follows-mesh/2026jul22.md`](cui-follows-mesh/2026jul22.md).
In short:

| pipeline  | dropped | added  | net     |
|-----------|--------:|-------:|--------:|
| anatomy   |      25 |    142 |    +117 |
| chemicals |     964 | 20,686 | +19,722 |
| disease   |      14 |    191 |    +177 |
| protein   |  15,749 |  1,107 | -14,642 |
| taxon     |      53 |     15 |     -38 |
| gene      |      12 |      0 |     -12 |
| process   |      18 |      0 |     -18 |

Of the 969 MeSH descriptors that led a clique in two compendia, the rule resolves 949. The other
20 are descriptors cross-listed in two trees (rule 3), which no UMLS rule can decide; they are the
rows of `input_data/known_duplicate_clique_leaders.tsv`, awaiting a stated priority between the
pipelines ([#730], [#1123]). glom() is transitive, so the prediction is confirmed with
`babel-clique-diff` after the first build.

The replay needs the build's `ids/MESH` and `ids/UMLS` files (exported from its
`Identifier.parquet`, see "Querying a published build in place" in
[`docs/DataFormats.md`](../../DataFormats.md)), its `duplicate_clique_leaders.tsv`, its
`Concord.parquet` and a local UMLS download; it takes about five minutes.

## What it does not fix

- `protein/concords/UMLS_UniProtKB` is a downloaded mapping, not keyed on `protein/ids/UMLS`, so a
  re-homed CUI that also maps to a UniProtKB accession still joins a UniProtKB-led Protein clique
  (the 16 protein drugs in [#308]; where they belong is [#849]).
- Identifiers no ids file claims that two pipelines' concords both reach (NCIT through UMLS xrefs
  into Anatomy and Protein, OMIM through Gene and Disease) are the member-level residue in
  `reports/duckdb/duplicate_curies.tsv`.
- The 18 MeSH `SCR_Chemical` virus records (e.g.
  [`MESH:C000719044`](https://meshb.nlm.nih.gov/record/ui?ui=C000719044) "H3N1 virus") now take
  their T005 CUIs into chemicals, because that is where MeSH's own record class puts them. If that
  reads as wrong in the clique diff, the fix is in `taxon.write_mesh_ids()`, not here.

## The control

`assert_no_unexpected_duplicate_clique_leaders()` (`src/reports/duckdb_reports.py`) fails the
build when `reports/duckdb/duplicate_clique_leaders.tsv` has a row that is not in
`input_data/known_duplicate_clique_leaders.tsv`; see "Build controls" in
[`docs/Architecture.md`](../../Architecture.md).

[#276]: https://github.com/NCATSTranslator/Babel/issues/276
[#308]: https://github.com/NCATSTranslator/Babel/issues/308
[#730]: https://github.com/NCATSTranslator/Babel/issues/730
[#849]: https://github.com/NCATSTranslator/Babel/issues/849
[#1123]: https://github.com/NCATSTranslator/Babel/issues/1123
