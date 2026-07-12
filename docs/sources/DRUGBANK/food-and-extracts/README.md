# DrugBank foods and extracts: typing DrugBank's foods as `biolink:Food`

[Issue #828](https://github.com/NCATSTranslator/Babel/issues/828)

DrugBank ships a large family of **food-and-extract products** — whole foods, pollens, plant
barks/roots/leaves, animal danders, molds, and dust used for allergy skin-testing and immunotherapy.
In Babel these default to `biolink:ChemicalEntity`, which is accurate but uselessly broad: the food
ones ([`DRUGBANK:DB10626`](https://go.drugbank.com/drugs/DB10626) "Trout",
[`DRUGBANK:DB10500`](https://go.drugbank.com/drugs/DB10500) "Almond") should be `biolink:Food`, and
the *extracts* ([`DRUGBANK:DB16536`](https://go.drugbank.com/drugs/DB16536) "Birch bark extract")
are processed materials, not defined chemicals.

The goal is to type **as many DrugBank food entries as `biolink:Food` as we safely can**. The two
signals we have (NCIt's Food/Seed classification and the UNII botanical flags) do that for 687
entries, plant and non-plant alike — NCIt Food covers
[`DRUGBANK:DB10623`](https://go.drugbank.com/drugs/DB10623) "Scallop",
[`DRUGBANK:DB10918`](https://go.drugbank.com/drugs/DB10918) "Venison",
[`DRUGBANK:DB14694`](https://go.drugbank.com/drugs/DB14694) "Beef liver" and
[`DRUGBANK:DB14233`](https://go.drugbank.com/drugs/DB14233) "Egg phospholipids" just as it covers
strawberries. What we deliberately leave behind is the set whose *only* organism evidence is an NCBI
Taxonomy cross-reference: that set contains real foods (lobster, flounder, mushroom) but also immune
globulins, antivenins and CAR-T therapies, and no signal we have separates them, so typing it would
declare things food that are definitely not food. It is deferred, with the evidence needed to sort
it out, to [#930](https://github.com/NCATSTranslator/Babel/issues/930).

Two further follow-ups: [#926](https://github.com/NCATSTranslator/Babel/issues/926) for the
food-vs-taxon question, and [#929](https://github.com/NCATSTranslator/Babel/issues/929) for a
`biolink:ProcessedMaterial` output to replace the interim extract type.

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

Each DrugBank entry carries a `UNII`, and the FDA UNII records (`Latest_UNII_Records.txt`) give each
UNII both an NCIt classification and cross-references to organism databases. Those are the bridge.

A DrugBank row is considered only if it has **no `Standard InChI Key`** (an extract/material, not a
defined molecule — a defined molecule extracted from a plant keeps its structure and stays a
chemical). Then:

1. It is treated as **food material** when either signal fires:
   - its UNII's NCIt class is under [`NCIT:C1949`](http://purl.obolibrary.org/obo/NCIT_C1949) "Food"
     or [`NCIT:C73913`](http://purl.obolibrary.org/obo/NCIT_C73913) "Seed" (Seed covers the
     nuts/grains NCIt files there — almond, cashew, sesame, wheat, oat). NCIt calls a food a food
     regardless of what it came from, so this signal is **not** plant-specific: scallop, perch,
     venison, beef liver and egg phospholipids all arrive this way;
   - **or** its UNII carries a botanical-database flag (USDA `PLANTS`, GRIN, or MPNS — see "Why the
     botanical flags but not NCBI" below), which reaches the plant materials NCIt has no food class
     for (barks, roots, pollens, herbs).

   Anything else — NCBI-only organisms and unflagged rows — is left as `ChemicalEntity` and deferred.
2. Among that material, a row whose name/synonyms contain an `extract` marker
   (`config.yaml: drugbank_extract_markers`) is a processed extract →
   **`biolink:ComplexMolecularMixture`** (bark/root/pollen extracts, herbal tinctures).
3. Any other food material → **`biolink:Food`** (whole fruits, roots, seeds, herbs, meats).

The `extract` check is applied **after** material identification and takes precedence over Food, so
an NCIt-food that is sold as an extract still lands in `ComplexMolecularMixture`.

`biolink:ComplexMolecularMixture` here is an **interim** type. The right long-term home for an
"extracted from a living organism" material is
[`biolink:ProcessedMaterial`](https://biolink.github.io/biolink-model/ProcessedMaterial/); adding it
as a Babel chemical output is tracked in
[#929](https://github.com/NCATSTranslator/Babel/issues/929), after which the extract rows flip from
`ComplexMolecularMixture` to `ProcessedMaterial`. "allergen" is **not** used as a signal (it was too
broad — it swept in NCBI-only danders/molds/insects and biologics); `extract` is the reliable
marker.

### Why the botanical flags but not NCBI

`read_plant_uniis` keys on the **botanical** UNII columns only — `PLANTS` / `GRIN` / `MPNS`. A UNII
in any of those denotes plant material (a whole plant or a plant part/extract), and a DrugBank plant
material with no structure is safely `Food`/extract.

The broader `NCBI` organism flag is deliberately **excluded** — not because NCBI-flagged entries
aren't food (many are), but because the flag says nothing either way. NCBI Taxonomy covers animals,
bacteria, fungi *and* the source organisms of **biologic drugs**, so retyping on it would declare
immune globulins, vaccine antigens, antivenins and CAR-T cell therapies to be food. That is a worse
error than leaving a food as `ChemicalEntity`, so the 481 NCBI-only structureless entries are listed
separately (see Snapshot) and deferred to
[#930](https://github.com/NCATSTranslator/Babel/issues/930), which has to recover the genuine foods
hiding there ([`DRUGBANK:DB10541`](https://go.drugbank.com/drugs/DB10541) "Lobster",
[`DRUGBANK:DB10531`](https://go.drugbank.com/drugs/DB10531) "Flounder",
[`DRUGBANK:DB10516`](https://go.drugbank.com/drugs/DB10516) "Casein" and
[`DRUGBANK:DB10544`](https://go.drugbank.com/drugs/DB10544) "Cultivated mushroom" are NCBI-flagged
animals/fungi, and no NCIt class they carry sits under Food/Seed). The snapshot file carries the
per-entry evidence for that triage.

## How it is wired

- `chemical_ncit_food_codes` (rule) queries UberGraph for the NCIt Food/Seed subtrees
  (`config.yaml: drugbank_food_ncit_roots`) → `ids/ncit_food_codes`.
- `chemical_drugbank_food_extracts` (rule) reads the DrugBank vocabulary CSV + the UNII
  records + those NCIt codes + `config.yaml: drugbank_extract_markers`, and writes
  `ids/DRUGBANK_food_extracts` (`DRUGBANK:xxx\tbiolink:Type`) —
  `datahandlers/drugbank.py:write_drugbank_food_extract_types`. The plant-flag set comes
  from the same UNII records file (`unii.py:read_plant_uniis`), so the rule needs no extra input.
- `chemicals.create_typed_sets` forces any clique containing one of those CURIEs to the given type,
  overriding the normal per-identifier type vote (the extracts carry no Babel type of their own, so
  a vote would leave them as `ChemicalEntity`). The retype is clique-level: it assumes an extract
  clique never also contains a genuine chemical, which holds because these are distinct UMLS/RXNORM
  concepts and none of them share a clique with a CHEBI/PubChem structure.
- `Food.txt` and the pre-existing `ComplexMolecularMixture.txt` are both in
  `config.yaml: chemical_outputs`, so **no new output type is needed** for this change. `RXCUI`
  members survive because the chemical build already passes `extra_prefixes=[RXCUI]`. These cliques
  flow through DrugChemical conflation and every export like any other chemical output, and
  conflation never re-types them, so the retype survives downstream.

## Snapshot

Two committed files in this directory, regenerated by `scripts/generate_csvs.py` (which imports the
production `classify_food_or_extract`, so the CSVs can't drift from the pipeline). They are built
from DrugBank vocabulary `5-1-13` (pinned — DrugBank downloads are currently blocked) and the
current FDA UNII records.

- **`food-and-extracts.csv`** — the retype changes, **687 entries** = **306 `biolink:Food`** (130
  via NCIt Food/Seed, 176 via a botanical flag) + **381 `biolink:ComplexMolecularMixture`** (the
  extracts). Columns:
  `drugbank_curie, label, unii, ncit, ncit_label, biolink_type, future_biolink_type, signal`.
  `future_biolink_type` is `biolink:ProcessedMaterial` on the extract rows (the #929 target), blank
  on Food rows; `signal` is the evidence that fired — `ncit-food`, `botanical-flag`, or `extract`.
- **`ncbi-only-drugbank-entries.csv`** — the **481** NCBI-only structureless entries left as
  `ChemicalEntity` for now (the review set for
  [#930](https://github.com/NCATSTranslator/Babel/issues/930)). Columns:
  `drugbank_curie, label, unii, unii_preferred_name, ncbitaxon, ncbitaxon_label, unii_ncit,
  unii_ncit_label, has_extract_marker`.

  The `ncbitaxon` columns are the point of the file: every one of the 481 has an NCBI taxon, and the
  taxon is the evidence that separates the three groups #930 has to tell apart — a food
  (`NCBITaxon:6706` "*Homarus americanus* (American lobster)"), a plant/animal material sold as an
  extract (`has_extract_marker` = `True`), and a biologic, whose taxon is its *source* organism and
  is usually `NCBITaxon:9606` "*Homo sapiens* (human)" or a livestock species. `unii_ncit` is often
  empty here (275 of 481 rows) — precisely the entries NCIt gives us no class for, hence no food
  signal. Fourteen taxon ids have no label, which is the usual sign of an id NCBI has since merged.

To regenerate after a UNII refresh: run the `chemical_ncit_food_codes` rule (or
`chemicals.write_ncit_descendant_codes`) to produce `ncit_food_codes`, then run
`scripts/generate_csvs.py`. It also needs `babel_downloads/NCIT/labels` and
`babel_downloads/NCBITaxon/labels` for the label columns; its module docstring has the exact
commands. Because DrugBank is pinned but the UNII records are re-downloaded fresh, exact membership
can drift slightly between refreshes.

## Known limitations

- **The `extract` marker is a proxy, so one category can split on wording.** A pollen listed as
  "*Genus species* pollen **extract**" lands in `ComplexMolecularMixture` while a bare "*Genus
  species* pollen" lands in `Food`, purely on incidental wording — and a plain food does the same:
  [`DRUGBANK:DB14242`](https://go.drugbank.com/drugs/DB14242) "Honey" is an extract only because one
  of its DrugBank synonyms is "Honey Extract". Tightening this (and the whole
  Food-vs-`biolink:OrganismTaxon` question) is deferred to
  [#926](https://github.com/NCATSTranslator/Babel/issues/926).
- **Non-food plant materials default to `Food`.** A botanically-flagged, non-extract material that
  is not actually eaten (e.g. [`DRUGBANK:DB00965`](https://go.drugbank.com/drugs/DB00965)
  "Ethiodized oil", a poppy-seed-oil contrast agent) becomes `Food`. This is still an improvement
  over `ChemicalEntity` and is acceptable interim; #926 covers the refinement.
- **NCBI-only entries are not retyped** (#930), including the genuine foods among them (lobster,
  flounder, casein, mushroom). This is the deliberate trade in the other direction: leave ~481
  entries under-typed rather than call an immune globulin a food.
- **Seven unflagged entries regress.** A handful of entries previously typed
  `ComplexMolecularMixture` via the old "allergen" match carry **no** organism flag at all and are
  not NCIt-food — "Pyrethrum extract", "Allergenic extract- beef liver", "Penicillium glaucum", and
  four `-lerbart` names. They fall outside both files and revert to `ChemicalEntity`; they can be
  picked up in #930 or by manual mapping.
