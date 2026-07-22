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
(`Latest_UNII_Records.txt`), a UNII yields an NCIt class and organism/plant-database flags — all
three read in one pass by `unii.py:read_unii_flags`, which returns:

- `unii_to_ncit` → the substance's NCIt class CURIE (used to recognise NCIt Food/Seed).
- `plant_uniis` → UNIIs carrying the botanical flags `PLANTS`/`GRIN`/`MPNS`. A **reliable
  plant-material signal**.
- `organism_uniis` → UNIIs carrying any of `NCBI`/`PLANTS`/`GRIN`/`MPNS`. The `NCBI` flag alone is
  **not** reliable for "is a plant/food": NCBI Taxonomy also covers animals, bacteria, fungi, and
  biologic-drug source organisms (immune globulins, vaccine antigens, antivenins, CAR-T). Prefer the
  botanical subset (`plant_uniis`) when you want plants/foods.

A botanical flag means "plant material", not "food", so it must never overrule an NCIt class that
says the entry is a drug — hence `config.yaml: nonfood_ncit_roots`, the never-food veto
that keeps [`DRUGBANK:DB00965`](https://go.drugbank.com/drugs/DB00965) "Ethiodized oil" (a
poppy-seed-oil contrast agent) out of `biolink:Food`. Keep those roots narrow, and do **not** reach
for UMLS semantic types instead: they are far coarser than NCIt's classes here, and the
UNII→`MTHSPL` route calls almost every one of these products a "Pharmacologic Substance". The
reasoning, with counts, is in
[`food-and-extracts/README.md`](food-and-extracts/README.md).

## No `Standard InChI Key` ⇒ structureless extract/material

A DrugBank row with no InChI Key is an extract or whole-organism material, not a defined molecule:
it has no UniChem structure match, is absent from `ids/DRUGBANK`, and enters chemical cliques only
through the UMLS/RXNORM concords — inheriting `biolink:ChemicalEntity` from the clique. Rows *with*
an InChI Key are defined molecules that keep their normal chemical type. The Food/extract retype
keys off exactly this (`classify_food_or_extract`).

**That guard is now a redundant second layer, not the real protection.** It only filters the
DrugBank row itself; it says nothing about the clique that row later gloms into.
`chemicals.create_typed_sets` used to *force* the whole clique to the retyped value, and in
`babel-1.18` that shipped D-glucose, ergocalciferol and tocopherol as `biolink:Food` — a
structureless food row and a real small molecule had reached the same clique through UMLS/RxNorm.
The evidence is now a **vote** ranked by `config.yaml: chemical_type_order`, where `biolink:Food`
sits below every structure-bearing type, so a clique that votes `SmallMolecule` keeps it
(issue #935). When reasoning about which cliques a retype will touch, remember that glom is
transitive: two identifiers with no direct concord edge still share a clique via a third, so the
concords cannot answer the question — a finished build can.
