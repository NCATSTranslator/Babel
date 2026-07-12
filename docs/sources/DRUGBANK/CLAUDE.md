# CLAUDE.md — docs/sources/DRUGBANK/

Agent notes for ingesting DrugBank. The data handler is `src/datahandlers/drugbank.py`; DrugBank
CURIEs are typed in the chemical pipeline (`src/createcompendia/chemicals.py`). Task narratives live
in subdirectories — see [`food-and-extracts/README.md`](food-and-extracts/README.md) for the
Food/extract retype (#828, with follow-ups #929/#926/#930).

## Only the CC-0 vocabulary CSV is usable

DrugBank blocks the full XML download (drug categories, ATC codes, targets, structured provenance),
so Babel has **only** `drugbank vocabulary.csv`: `DrugBank ID, Accession Numbers, Common name, CAS,
UNII, Synonyms, Standard InChI Key`. Any typing or attribute work must be built from those seven
columns — you cannot lean on DrugBank categories. The vocabulary is also effectively **frozen**
(downloads blocked; pinned at `5-1-13`), so its retype sets are stable enough to commit as audit
artifacts.

## The UNII column is the bridge to typing

`extract_drugbank_labels_and_synonyms` discards the `UNII` column, but that column is the key to
enriching DrugBank entries. Cross-referenced against the FDA UNII records
(`Latest_UNII_Records.txt`), a UNII yields an NCIt class and organism/plant-database flags — see the
readers in `src/datahandlers/unii.py`:

- `read_unii_ncit` → the substance's NCIt class CURIE (used to recognise NCIt Food/Seed).
- `read_plant_uniis` → the botanical flags `PLANTS`/`GRIN`/`MPNS`. A **reliable plant-material
  signal**.
- `read_organism_uniis` → any of `NCBI`/`PLANTS`/`GRIN`/`MPNS`. The `NCBI` flag alone is **not**
  reliable for "is a plant/food": NCBI Taxonomy also covers animals, bacteria, fungi, and
  biologic-drug source organisms (immune globulins, vaccine antigens, antivenins, CAR-T). Prefer the
  botanical subset (`read_plant_uniis`) when you want plants/foods.

## No `Standard InChI Key` ⇒ structureless extract/material

A DrugBank row with no InChI Key is an extract or whole-organism material, not a defined molecule:
it has no UniChem structure match, is absent from `ids/DRUGBANK`, and enters chemical cliques only
through the UMLS/RXNORM concords — inheriting `biolink:ChemicalEntity` from the clique. Rows *with*
an InChI Key are defined molecules that keep their normal chemical type. The Food/extract retype
keys off exactly this (`classify_food_or_extract`), and the clique-level force-retype in
`chemicals.create_typed_sets` overrides that inherited `ChemicalEntity` type for the whole clique.
