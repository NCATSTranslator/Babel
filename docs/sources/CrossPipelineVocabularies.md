# Vocabularies that span pipelines

Most prefixes belong to one pipeline: every `UBERON` identifier is anatomy's, every `CHEBI` one is
chemicals'. A few vocabularies name things of several kinds, so more than one pipeline writes an
`ids/<PREFIX>` file for them. This page covers how Babel keeps each of their identifiers in exactly
one compendium, and what to check when you change how one is split. Each source's own page has
the detail; this one collects what they have in common.

The invariant is the one in the root `AGENTS.md`: two compendia must never share an identifier.
NodeNorm answers one CURIE with one clique, so an identifier in two compendia gets whichever loaded
last ([#276](https://github.com/NCATSTranslator/Babel/issues/276)), and a clique leader in two
fails the build ("Build controls" in [`docs/Architecture.md`](../Architecture.md#build-controls)).

## Which vocabularies, and how each is split

A prefix is on this list when it appears in more than one `*_ids` list in `config.yaml`. To
regenerate the list after a change:

```bash
uv run python -c "
import yaml, collections
by = collections.defaultdict(list)
for key, prefixes in yaml.safe_load(open('config.yaml')).items():
    if key.endswith('_ids') and isinstance(prefixes, list):
        for prefix in prefixes: by[prefix].append(key.removesuffix('_ids'))
for prefix, pipelines in by.items():
    if len(pipelines) > 1: print(prefix, pipelines)"
```

| Prefix    | Pipelines                                                  | Split by                                                                 | Details                                                                                  |
|-----------|------------------------------------------------------------|--------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| `UMLS`    | anatomy, chemicals, disease, gene, process, protein, taxon | Semantic type, then the CUI's MeSH descriptor; leftovers to `umls.txt`   | [`UMLS/CuiFollowsMesh.md`](UMLS/CuiFollowsMesh.md), [`UMLS/Leftover.md`](UMLS/Leftover.md) |
| `MESH`    | anatomy, chemicals, disease, protein, taxon                | Tree number; any record with an NCBI Taxon registry number goes to taxon | [`MeSH/Ingestion.md`](MeSH/Ingestion.md#how-mesh-is-split-across-compendia)              |
| `GO`      | anatomy, process                                           | GO aspect (root term)                                                    | below                                                                                    |
| `NCIT`    | anatomy, disease                                           | Root term, with excluded branches                                        | below                                                                                    |
| `OMIM`    | disease, gene                                              | `mim2gene.txt` entry type                                                | below                                                                                    |
| `ENSEMBL` | gene, protein                                              | Gene vs protein stable ID                                                | below                                                                                    |

`tests/pipeline/conftest.py`'s `VOCABULARY_REGISTRY` lists the vocabularies the partitioning test
checks (see "Checks" below). ENSEMBL isn't in it, so its split is tested only on fixture rows
(`tests/createcompendia/test_protein.py`), not on real BioMart data
([#1248](https://github.com/NCATSTranslator/Babel/issues/1248)).

### GO

Anatomy takes [`GO:0005575`](http://purl.obolibrary.org/obo/GO_0005575) "cellular_component"
(`anatomy.ANATOMY_OBO_SOURCES`). Process takes
[`GO:0008150`](http://purl.obolibrary.org/obo/GO_0008150) "biological_process" and
[`GO:0003674`](http://purl.obolibrary.org/obo/GO_0003674) "molecular_function", with
[`GO:0007165`](http://purl.obolibrary.org/obo/GO_0007165) "signal transduction" typed as a
pathway (`processactivitypathway.write_go_ids()`). GO's three aspects don't share terms, so the
split is disjoint by construction.

### NCIT

Anatomy takes the subtrees under
[`NCIT:C12219`](http://purl.obolibrary.org/obo/NCIT_C12219) "Anatomic Structure, System, or
Substance", [`NCIT:C12508`](http://purl.obolibrary.org/obo/NCIT_C12508) "Cell" and
[`NCIT:C34070`](http://purl.obolibrary.org/obo/NCIT_C34070) "Cell Part", minus the branches
listed in `anatomy.write_ncit_ids()`'s `exclude` (genomic locations, chromosome bands, protein
domains and so on). Disease takes [`NCIT:C2991`](http://purl.obolibrary.org/obo/NCIT_C2991)
"Disease or Disorder" and [`NCIT:C3367`](http://purl.obolibrary.org/obo/NCIT_C3367) "Finding"
(`diseasephenotype.write_ncit_ids()`). NCIt allows several parents, so these subtrees aren't
disjoint by construction. The partitioning test is what shows they don't overlap.

Protein writes no `ids/NCIT` but concords NCIT twice (`NCIT_UMLS` and `NCIT_UniProtKB`), so an
NCIT identifier can reach Protein through a concord alone. Nothing filters those pairs against
anatomy's or disease's `ids/NCIT`, and anatomy's UMLS concord isn't filtered either; the resulting
duplicates are [#1126](https://github.com/NCATSTranslator/Babel/issues/1126).

### OMIM

Both pipelines read `mim2gene.txt`'s entry-type column. Gene takes `gene`
(`gene.write_omim_ids()`). Disease takes any type containing `phenotype`, which in the
2026-10-19 file means `phenotype` and `predominantly phenotypes`
(`diseasephenotype.write_omim_ids()`). Neither takes `moved/removed`. Retabulate the column when
OMIM adds a type: `gene/phenotype`, if it appeared, would go to disease.

```bash
grep -v '^#' babel_downloads/OMIM/mim2gene.txt | cut -f2 | sort | uniq -c
```

UMLS links disease CUIs to gene OMIM entries, so disease's UMLS concord accepts an OMIM (or NCIT)
partner only if disease's own `ids/OMIM` (or `ids/NCIT`) lists it: the `acceptable_identifiers`
argument to `umls.build_sets()` in `diseasephenotype.build_disease_umls_relationships()`.

### ENSEMBL

Gene takes each BioMart row's gene stable ID (`ENSG…` in human) and protein takes its protein
stable ID (`ENSP…`). Ensembl's yeast annotation reuses one systematic name as gene and protein ID,
so `protein.write_ensembl_protein_ids()` skips a protein ID equal to its gene ID and leaves it to
gene. Its docstring explains why gene wins.

## How to keep a shared vocabulary disjoint

In rough order of preference:

1. **Split at the ids file, on something the source itself states**: a tree number, a root term,
   a type column, an ID pattern. Then the split is a property of the source, and it can be
   checked by reading the ids files alone. The writers for one vocabulary live in different
   pipeline modules, so change them together. `chemicals.write_mesh_ids()` and
   `protein.write_mesh_ids()` each declare their own view of the MeSH D-trees, and a change to
   one needs a matching change to the other ([`MeSH/Ingestion.md`](MeSH/Ingestion.md)).
2. **When two signals disagree, decide once, for every pipeline.** UMLS semantic types and MeSH
   trees can put one concept in two pipelines. `rule umls_mesh_ownership` resolves that once, in
   `intermediate/umls/mesh_ownership.tsv`, which every MeSH-owning pipeline reads. A rule each
   pipeline applies on its own loses identifiers: a pipeline drops what another claims, but no
   pipeline is sure to add it. That failed draft is recorded in
   [`UMLS/CuiFollowsMesh.md`](UMLS/CuiFollowsMesh.md#the-rule). The same file gives taxon every
   MeSH record with an NCBI Taxon registry number, so a rule about one vocabulary can settle
   another's ownership too.
3. **Filter the concords as well as the ids files.** Leaving an identifier out of an `ids` file
   doesn't keep it out of that pipeline's compendium: a concord alone can put a CURIE there
   ([#1109](https://github.com/NCATSTranslator/Babel/issues/1109)). There are two filters:
   - `acceptable_identifiers` limits one concord's partners for a prefix to this pipeline's ids
     (disease's UMLS concord, above).
   - `umls.read_cuis_owned_elsewhere()` and `skip_pairs_owned_elsewhere()` drop any pair that
     names an identifier the ownership file gives to another pipeline, whichever concord it came
     from.

   `unique_prefixes` doesn't help here: it limits same-prefix identifiers within one clique, not
   across compendia.
4. **Relate across compendia with conflation, never with a shared identifier.** A gene and its
   protein, or a drug and its active ingredient, are different cliques in different compendia.
   [`docs/Conflation.md`](../Conflation.md) is how Babel links them.
5. **Let leftovers fall to `umls.txt`.** A CUI that no pipeline claims is written by
   `rule leftover_umls` as a single-identifier clique, so its label survives. That is a fallback
   for CUIs no pipeline claims, not a fix for one that two pipelines claim.

## Checks

- **`tests/pipeline/test_vocabulary_partitioning.py`** (`--pipeline`) builds every registered
  vocabulary's ids files and fails if an identifier is in two of them. Its `KNOWN_DUPLICATES`
  lists the UMLS and MeSH identifiers still accepted, under
  [#729](https://github.com/NCATSTranslator/Babel/issues/729) and
  [#730](https://github.com/NCATSTranslator/Babel/issues/730). Remove an entry once it's fixed. To
  check a new vocabulary, add its fixture to `conftest.py` and its prefix to `VOCABULARY_REGISTRY`.
- **`tests/pipeline/test_mesh.py`** checks MeSH's taxon rule over a real download.
- **Duplicate clique leaders fail the build**, unless
  `input_data/known_duplicate_clique_leaders.tsv` lists the leader with the issue that accepts it.
- **Duplicate members are reported only.** `reports/duckdb/duplicate_curies.tsv` lists every CURIE
  in more than one clique. A shared vocabulary that leaks through concords shows up here first.
  To count its rows by prefix:

  ```bash
  tail -n +2 babel_outputs/reports/duckdb/duplicate_curies.tsv | cut -f1 | cut -d: -f1 \
    | sort | uniq -c | sort -rn
  ```

The ids-file checks don't see identifiers that arrive through concords alone, such as NCIT in
Protein. Only a finished build's compendia and `duplicate_curies.tsv` show those.

## Adding a pipeline to a shared vocabulary

Before giving a second pipeline an `ids/<PREFIX>` file, or giving a new pipeline UMLS or MeSH:

- Decide what splits the identifiers, and write it in both writers' docstrings.
- If both pipelines can claim the same identifier, decide who owns it before any compendium is
  built: either split on a property the source states, or extend the ownership file. Don't make
  one pipeline defer to another by reading its ids file. That is the per-pipeline rule that
  `umls_mesh_ownership` replaced.
- Check every concord that can bring the prefix into the new pipeline, not only the one built from
  its ids file.
- Add the vocabulary to `VOCABULARY_REGISTRY`, and update the table above.
