# DrugBank allergenic extracts: retyping foods and non-food allergens

[Issue #828](https://github.com/NCATSTranslator/Babel/issues/828)

DrugBank ships a large family of **allergenic-extract products** — whole foods, pollens, animal
danders, molds, mites, and dust used for allergy skin-testing and immunotherapy. In Babel these
default to `biolink:ChemicalEntity`, which is wrong: the food ones
([`DRUGBANK:DB10626`](http://identifiers.org/drugbank/DB10626) "Trout",
[`DRUGBANK:DB10571`](http://identifiers.org/drugbank/DB10571) "Strawberry",
[`DRUGBANK:DB10500`](http://identifiers.org/drugbank/DB10500) "Almond") should be `biolink:Food`
so downstream services can filter or treat foods differently, and the non-food ones
([`DRUGBANK:DB10351`](http://identifiers.org/drugbank/DB10351) "Cynodon dactylon pollen") are not
chemicals either.

## Why the obvious approaches don't reach these

- **Food ontologies (FoodOn/FooDB) don't help.** These extracts carry only a UNII and no chemical
  structure. FoodOn has no UNII/DrugBank cross-references; FooDB *foods* carry only
  ITIS/Wikipedia/NCBITaxon (only FooDB *compounds* carry UNII/DrugBank, and an extract is a food,
  not a compound). Ingesting a food ontology builds a "trout" clique keyed on NCBITaxon with no
  edge of any kind to `DRUGBANK:DB10626`.
- **Structure-based joins never reach them.** With no InChI Key there is no UniChem structure
  match, so these ids are absent from `ids/DRUGBANK` entirely. They enter chemical cliques only
  through the UMLS and RXNORM concords and inherit `ChemicalEntity` from the clique.
- **DrugBank's rich category data is un-downloadable** (DrugBank blocks the XML). We have only the
  CC-0 `drugbank vocabulary.csv` (`DrugBank ID, Accession Numbers, Common name, CAS, UNII,
  Synonyms, Standard InChI Key`).

## The signal we use

Each DrugBank entry carries a `UNII`, and the FDA UNII records
(`Latest_UNII_Records.txt`) give every UNII an NCIt classification. That is the bridge:

A DrugBank row is retyped only if it has **no `Standard InChI Key`** (an extract, not a defined
molecule — a genuine plant-derived small molecule keeps its structure and stays a chemical), and
then:

- **`biolink:Food`** if its UNII's NCIt class is under
  [`NCIT:C1949`](http://purl.obolibrary.org/obo/NCIT_C1949) "Food" or
  [`NCIT:C73913`](http://purl.obolibrary.org/obo/NCIT_C73913) "Seed". Seed is included because NCIt
  files nuts and grains (almond, cashew, sesame, wheat, oat) under Seed rather than Food. These NCIt
  subtrees hold only genuine foods — no biologics.
- **`biolink:ComplexMolecularMixture`** if it is not a food but its name/synonyms mention
  "allergen" (pollens, danders, molds, mites, dust).

Foods are checked first, so a food that also carries allergen text (e.g. "Peanut allergenic
extract") stays `biolink:Food`.

### Why not a plain organism flag

An earlier attempt used the UNII organism columns (`NCBI/PLANTS/GRIN/MPNS`, the same flags
`write_unii_ids` uses to drop "a plant or an eye of newt" from chemicals). That over-captures
badly — 1128 structureless DrugBank entries, including immune globulins, antithymocyte
immunoglobulin, and live-attenuated virus vaccines, which are biologic **drugs**, not foods. NCIt
classification cleanly separates the ~222 genuine allergenic-extract products from those biologics.

The full over-capture set is recorded in `organism-flag-overcapture.csv` in this directory: all
1128 structureless DrugBank rows whose UNII carries an organism flag. Its `current_ncit_retype`
column is the Biolink type the current NCIt approach assigns (blank = not retyped): 175 are genuine
foods the NCIt approach also catches, and the other **953 are the over-capture** the organism-flag
approach would wrongly retype as `biolink:Food`/`biolink:ComplexMolecularMixture`. This is why the
organism-flag check is deliberately **not** used to pick which DrugBank entries to retype — nothing
is being excluded by it, and switching to it would mis-retype those 953 biologics. (Because DrugBank
is pinned but the UNII records are re-downloaded fresh, the exact membership can drift slightly
between refreshes; the count above is against the UNII records current as of this file.)

### Why `biolink:ComplexMolecularMixture` for the non-food allergens

Pollen and dander are not foods, so `biolink:Food` is wrong for them, and they are not chemicals.
`biolink:ComplexMolecularMixture` is the closest existing Biolink class (a heterogeneous biological
extract). [`biolink:PhysicalEntity`](https://biolink.github.io/biolink-model/PhysicalEntity/) is
another candidate but is very generic and outside the chemical hierarchy. The likely long-term fix
is to ask the Biolink Model maintainers for a new class closely related to `biolink:Food` that
encompasses allergenic extracts; until then these live in `ComplexMolecularMixture`.

## How it is wired

- `chemical_ncit_food_codes` (rule) queries UberGraph for the NCIt Food/Seed subtrees
  (`config.yaml: drugbank_food_ncit_roots`) → `ids/ncit_food_codes`.
- `chemical_drugbank_allergenic_extracts` (rule) reads the DrugBank vocabulary CSV + the UNII
  records + those NCIt codes and writes `ids/DRUGBANK_allergenic_extracts`
  (`DRUGBANK:xxx\tbiolink:Type`) —
  `datahandlers/drugbank.py:extract_drugbank_allergenic_extract_types`.
- `chemicals.create_typed_sets` forces any clique containing one of those CURIEs to the given type,
  overriding the normal per-identifier type vote (the extracts carry no Babel type of their own, so
  a vote would leave them as `ChemicalEntity`). The retype is clique-level: it assumes an extract
  clique never also contains a genuine chemical, which holds because these are distinct UMLS/RXNORM
  concepts.
- Food cliques are written to a new `Food.txt` compendium (added to
  `config.yaml: chemical_outputs`); the non-food ones join the existing
  `ComplexMolecularMixture.txt`. `RXCUI` members survive because the chemical build already passes
  `extra_prefixes=[RXCUI]` (RXCUI is not in either class's Biolink `id_prefixes`). Because
  `Food.txt` is in `chemical_outputs`, these cliques flow through DrugChemical conflation and every
  export exactly like any other chemical output, and conflation never re-types them, so the retype
  survives downstream.

## Snapshot

`allergenic-extracts.csv` in this directory is the retype set from DrugBank vocabulary `5-1-13`
(the pinned version — DrugBank downloads are currently blocked, so this set is effectively frozen):
162 `biolink:Food` + 60 `biolink:ComplexMolecularMixture` = 222 entries. Columns:
`drugbank_curie, label, biolink_type, unii, ncit, signal` (`signal` is `ncit-food` or
`allergen-text`). The build regenerates the same set from the pinned inputs; the CSV is committed
for review and to make the classification auditable.

To regenerate after a DrugBank or UNII refresh, run the `chemical_ncit_food_codes` and
`chemical_drugbank_allergenic_extracts` rules and re-derive the CSV from
`ids/DRUGBANK_allergenic_extracts` joined against the vocabulary CSV.

## Known limitations

- **Foods with no UNII** are missed by the NCIt-food test and, if they carry allergen text, fall to
  `ComplexMolecularMixture` instead of `Food` (e.g. "Allergenic extract- beef liver", whose vocab
  row has an empty UNII). Few entries; acceptable given the type is still corrected off
  `ChemicalEntity`.
- **Bare non-food organism names with no "allergen" synonym** (a pollen listed only as
  "*Genus species* pollen" with no allergen text) are not retyped. Most such entries do carry
  allergen text, so coverage is high but not total.
