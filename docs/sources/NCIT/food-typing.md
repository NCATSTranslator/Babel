# Typing foods from their NCIt classification

[Issue #935](https://github.com/NCATSTranslator/Babel/issues/935), generalizing
[#828](https://github.com/NCATSTranslator/Babel/issues/828)

The NCI Thesaurus classifies concepts as foods —
[`NCIT:C1949`](http://purl.obolibrary.org/obo/NCIT_C1949) "Food or Food Product" and
[`NCIT:C73913`](http://purl.obolibrary.org/obo/NCIT_C73913) "Seed", where NCIt files the nuts and
grains. [#828](https://github.com/NCATSTranslator/Babel/issues/828) used that classification to type
**DrugBank** food entries as `biolink:Food` (see
[`../DRUGBANK/food-and-extracts/README.md`](../DRUGBANK/food-and-extracts/README.md)). The same
evidence exists for concepts DrugBank never mentions — swordfish, capsicum, cranberry, corn — and
this is how they get typed too.

## NCIt CURIEs are not clique members, so the classification is *projected*

`NCIT` appears in neither `chemical_ids` nor `chemical_concords` (`config.yaml`), so no `NCIT:`
CURIE is a member of a chemical clique. "Type the NCIt identifiers and let everything
cross-referenced to them inherit it" therefore cannot work: there is nothing to inherit *from*. The
classification has to be projected onto identifiers that **are** clique members
(`chemicals.write_ncit_food_types` → `ids/ncit_food_types`, rule `chemical_ncit_food_types`):

- **UMLS** — `MRCONSO.RRF`'s `SAB=NCI` rows map an NCIt code to its CUI. 997 CUIs.
- **UNII** — the FDA UNII records' `NCIT` column. 286 UNIIs.
- **RxNorm** — nothing of its own: an `RXCUI` rides along in the same clique as the CUI it shares a
  concept with, and inherits the clique's type.

UNIIs that carry an **InChI Key** are skipped: a defined molecule is already typed from its
structure, and NCIt classifies plenty of defined molecules as foods (water, riboflavin, isoleucine,
beta carotene).

## The evidence is a vote, not an override

This is the part that matters, and it is why #935 could not simply reuse #828's mechanism.

`chemicals.create_typed_sets` used to *force* a clique's type whenever any member carried
food/extract evidence, skipping the type vote entirely. That is safe for #828, whose entries are
structureless by construction, but not here: NCIt calls **water** a food, and
[`UMLS:C0043047`](https://uts.nlm.nih.gov/uts/umls/concept/C0043047) "Water" duly carries food
evidence. Forcing it would retype water from `biolink:SmallMolecule` to `biolink:Food`.

So the evidence now joins the vote as an extra candidate, and `order` decides:

```text
Drug > MolecularMixture > SmallMolecule > Polypeptide > ComplexMolecularMixture > Food
     > ChemicalMixture > ChemicalEntity
```

`Food` sits **below** every structure-bearing type and **above** the uninformative
`ChemicalMixture`/`ChemicalEntity` it exists to improve on. The consequences:

- **Water stays a `SmallMolecule`.** Its clique votes `SmallMolecule` (from CHEBI and PubChem),
  which is more specific than the food evidence.
- **Swordfish becomes `Food`.** Its clique votes nothing but `ChemicalEntity`, which `Food` beats.
- **An extract stays an extract.** `ComplexMolecularMixture` outranks `Food`, so a DrugBank extract
  whose concept NCIt also calls a food (green tea) keeps the extract type.

The "no InChI Key" structure guard that #828 hard-codes is, in this design, an emergent property of
the ordering rather than a rule anyone has to remember. The UNII structure guard above is kept
anyway as a second belt: it costs one column read and keeps a structure-bearing UNII from claiming
`Food` in the rare clique that has no structure-typed member at all.

## The never-food veto still applies

`config.yaml: nonfood_ncit_roots` (imaging agents, antineoplastics) is subtracted from the food
codes before projection, so a concept NCIt classifies as a drug contributes no food evidence — the
same veto that keeps [`DRUGBANK:DB00965`](https://go.drugbank.com/drugs/DB00965) "Ethiodized oil"
out of `Food`. Keep those roots narrow, and see the DrugBank README for why
[`NCIT:C1909`](http://purl.obolibrary.org/obo/NCIT_C1909) "Pharmacologic Substance" is **not** among
them, and why the (much coarser) UMLS semantic types are not used for this at all.
