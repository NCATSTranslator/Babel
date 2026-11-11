# Linking a UMLS CUI to its UNII

A UNII with no structure (a biologic, polymer, oligonucleotide or mixture) had no link to its UMLS
CUI. UniChem matches on structure only, and the chemical UMLS concord reads MeSH, DrugBank and
RxNorm atoms. So the CUI and the UNII sat in separate cliques under the same name:
[`UMLS:C2716826`](https://uts.nlm.nih.gov/uts/umls/concept/C2716826) "taspoglutide" and
`UNII:2PHK27IP3B` "TASPOGLUTIDE".

`chemicals.build_umls_unii_relationships()` (`rule get_chemical_umls_unii_relationships`) writes
`chemicals/concords/UMLS_UNII` from two links that UMLS and FDA assert themselves:

- **SPL substance atoms.** An `SAB=MTHSPL`, `TTY=SU` atom's code is the substance's UNII.
- **NCIt.** An `SAB=NCI`, `TTY=PT` atom's code is an NCIt concept, and the FDA UNII record
  (`Latest_UNII_Records.txt`, column `NCIT`) names the NCIt concept of the same substance.

## Which atoms, and why

Tabulated over all of UMLS 2026AA (English atoms):

| MTHSPL term type | code | atoms | usable |
|---|---|---:|---|
| `DP`, `MTH_RXN_DP` (drug product) | SPL set id | 189,854 | no: a product, not a substance |
| `SU` (substance) | a UNII | 23,452 | yes |
| `SU` | `NOCODE` | 518 | no |
| `SU` | anything else | 20 | no: not in the UNII records |

For NCIt, only the preferred term is usable. Every NCIt code has exactly one `PT` atom (200,820
codes, 200,820 atoms), but `SY` and `BN` atoms put one code on many CUIs: NCIt `C422`
"Dexamethasone" reaches 62 CUIs through brand names such as "Decadron" and "Baycadron", which UMLS
keeps as separate concepts. Joining on every NCI atom linked `UNII:7S5I7G3JQL` to all 62.

## The guards

A concord pair is an equivalence, and glom() is transitive, so each of these exists to stop a pair
joining cliques that should stay apart:

1. **One-to-one over both routes together.** A pair is written only when the CUI reaches exactly one
   UNII and the UNII is reached by exactly one CUI. `UMLS:C0972333` "vardenafil hydrochloride"
   reaches the trihydrate's UNII through SPL and the anhydrous UNII through NCIt; writing both would
   join the two forms through the CUI. The count is taken before the ids-file filters, so an
   ambiguity involving a CUI or UNII outside chemicals still counts.
2. **Only CUIs in `chemicals/ids/UMLS` and UNIIs in `chemicals/ids/UNII`.** `write_unii_ids()`
   leaves out whole organisms, and a concord alone can put a CURIE into a compendium.
3. **Last in `chemical_concords`.** glom() applies concords in order, so every older link is made
   first and a `UMLS_UNII` pair can only join what they left apart.
4. **glom()'s INCHIKEY guard**, unchanged: a pair between two cliques that each carry a structure is
   refused.

## Measured against 2026jul22

[`umls-unii/2026jul22.md`](umls-unii/2026jul22.md), from `umls-unii/scripts/replay_umls_unii.py`,
runs the production function and judges each pair against the build's finished cliques. Of 32,733
candidate pairs, 20,453 are written; guard 1 drops 1,976 and guard 2 drops 10,304.

| effect of a written pair | pairs |
|---|---:|
| already in one clique | 9,615 |
| merges cliques | 10,357 |
| refused by the INCHIKEY guard | 481 |

The 10,357 merging pairs form 10,341 groups: 10,325 join two cliques and 16 join three. The largest
resulting clique has 131 identifiers. 2,518 groups have no structure on either side, and 7,822
attach a structureless clique to one with a structure. 9,197 of the merging pairs have the same name
once case and punctuation are removed.

[`umls-unii/2026jul22-merges-top-200.csv`](umls-unii/2026jul22-merges-top-200.csv) lists the pairs
most likely to be wrong, ranked: the one group that touches two structures, the three-clique groups,
then pairs whose names differ. What that review shows:

- The three-clique groups come from cliques that already hold two forms of a substance. The clique
  of [`CHEBI:27594`](http://purl.obolibrary.org/obo/CHEBI_27594) "carbon atom" already contains the
  CUIs for diamond and graphite, so their UNIIs join it. The concord extends an existing blur; it
  does not start one.
- The one group with two structures is an error already in the build: `UMLS:C0675992` "ginsenoside
  compound K" is in the clique of `UNII:A9RLM212CY` "CHLORDANE". The concord's pair for that CUI is
  refused by the INCHIKEY guard only if the chlordane pair is applied first, which sorted concord
  order ensures.
- Many name differences are unspecified against specific forms ("zinc sulfate" and "ZINC SULFATE,
  UNSPECIFIED FORM") or UMLS groupings looser than FDA's ("cellulose" and ".ALPHA.-CELLULOSE").

The replay judges each pair against cliques built without the concord, and `Drug.txt` and
`Food.txt` carry no INCHIKEY, so their cliques count as structureless. Confirm with
`babel-clique-diff` after the first build.

## What it does not link

- A CUI another pipeline claims. 5,901 candidate pairs have a CUI outside `chemicals/ids/UMLS`,
  mostly T116 "Amino Acid, Peptide, or Protein" CUIs in protein.
- An organism UNII (4,403 pairs).
- ChEMBL and GtoPdb records of the same biologics, which neither UMLS nor the UNII records name.
