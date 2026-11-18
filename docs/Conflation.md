# Babel Conflation

Babel is designed to produce cliques of *identical* identifiers, but our users would sometimes like
to combine identifiers that are similar in some other way. Babel generates "conflations" to support
this.

Babel currently generates three conflations:

1. GeneProtein conflates gene with the protein transcribed from it.
   The gene identifier will always be returned.
2. DrugChemical conflates drugs with their active ingredients as a chemical. For each conflation,
   the identifiers are arranged in order of (1) preferred prefix order for the
   [ChemicalEntity Biolink type](https://biolink.github.io/biolink-model/ChemicalEntity/#valid-id-prefixes),
   followed by (2) within each prefix group: lower information content first, larger cliques first,
   and finally from the numerically smallest suffix to the numerically largest suffix.
3. ChemicalParent conflates chemicals that are one parent compound in different forms: charge
   (protonation) states, such as valproic acid and valproate, and salts and hydrates, such as
   fluoxetine hydrochloride. See [ChemicalParent](#chemicalparent) below.

## ChemicalParent

ChemicalParent groups chemical cliques by a *parent key* read off their `INCHIKEY:` members. Code:
`src/createcompendia/chemicalparent.py` and `src/createcompendia/inchi_components.py`.

### Charge states

An InChIKey has three blocks: a hash of the connectivity layer, a hash of the remaining layers
(stereochemistry, isotopes) with a standard flag and version character, and a single protonation
character (`N` for neutral). A clique's parent key is its InChIKey without the protonation block, so
cliques that differ only in protonation share one. This is rule 1 of
[#1173](https://github.com/NCATSTranslator/Babel/issues/1173).

The second block stays in the parent key on purpose, so stereoisomers (dexamethasone and
betamethasone) and isotope-labelled forms are never grouped. A clique whose InChIKeys have more than
one parent key is left out rather than guessed at.

### Salts and hydrates

A salt or hydrate is one record with several disconnected components (fluoxetine hydrochloride's
standard InChI is `C17H18F3NO.ClH`), so its InChIKey shares nothing with its parent's. Its parent
key is instead the parent key of the single component left after dropping counterions and solvents.
This is rule 3 of #1173.

- `rule chemicalparent_inchi_components` splits every multi-component InChI into components with
  RDKit. The InChIs come from UniChem's `structure.tsv.gz` and GtoPdb's `ligands.tsv`, the two files
  clique InChIKeys come from, so every clique key's InChI is present and from the same release.
  (PubChem's `CID-InChI-Key.gz` lacked 1.6% of 2025dec11's clique keys.) SMILES aren't used: the
  InChI is the exact string a clique's key hashes, while a source's SMILES may describe a different
  tautomer or charge. RDKit's InChI parser never returns on a few structures, so each chunk of work
  runs under a timeout that kills its worker. InChIs that time out, or that RDKit can't split, are
  counted in the rule's metadata and keep their own keys.
- [`input_data/chemical_parent_components.tsv`](../input_data/chemical_parent_components.tsv) is the
  reviewed list of components, each marked `drop` (a counterion or solvent) or `keep`. Anything not
  on the list is kept. Metal centres are `keep`: standard InChI disconnects metals, so cobalamin's
  cobalt and cisplatin's platinum would otherwise be stripped.
- `rule chemicalparent_salt_parents` maps a salt to its parent only when exactly one distinct
  component remains. If none remains (a bare counterion, or a salt whose every part is on the drop
  list, such as lysine hydrochloride), or several remain (a combination product or a metal complex),
  the salt keeps its own key. The mapping is keyed by the salt's own parent key, so every charge
  state of the salt follows it. A salt whose charge states resolve to different parents is left out
  and counted.

The list was built by review against 2025dec11. Of the 135,810 multi-component records in cliques
with a curated (non-PubChem, non-CAS) identifier, 94.0% resolve to one parent, 93.3% onto an
existing clique; no unreviewed component blocks more than 5 of them. See
[`docs/conflation/chemical-parent/`](conflation/chemical-parent/) for the review script and its
report. Re-run the review when a build adds sources.

### Ordering

A clique that reaches the parent key directly leads one that reaches it through a salt. A neutral
HCl salt's key also ends `-N`, so without this rule it could outrank the free base. Then the neutral
(`-N`) form leads charged ones, and the rest are ordered as in DrugChemical.

### Overlap with DrugChemical

ChemicalParent and DrugChemical can overlap. NodeNorm applies each conflation with one lookup on the
queried clique and does not follow one conflation into another. So with both turned on, two members
of a ChemicalParent group may still get different DrugChemical members. How often this happens for
charge states is measured in [`docs/conflation/chemical-parent/`](conflation/chemical-parent/).
NameRes has no ChemicalParent-conflated synonym file yet.

## How are conflations generated in Babel and used in NodeNorm?

Each conflation file is a JSON-Lines (JSONL) file, where every line is a JSON list of clique
identifiers, which are stored in Redis databases in NodeNorm. If a particular conflation is turned
on, NodeNorm will:

1. Normalize the input identifier to a clique identifier.
2. If the clique identifier is not part of any conflation, we return it as-is.
3. If the clique identifier is part of a conflation, we construct a new clique whose preferred
   identifier is the first identifier in the clique, and which consists of all the identifiers from
   all the cliques included in that conflation.

For how to turn each conflation on when querying, see the
[NodeNorm API documentation](https://github.com/NCATSTranslator/NodeNormalization/blob/main/documentation/API.md).

## How are types handled for conflated cliques?

Babel does not assign a type to any conflations. When NodeNorm is called with a particular
conflation turned on, it determines the types of a conflated clique by:

1. Starting with the most specific type of the first identifier in the conflation.
2. Adding all the supertypes of the most specific type for the first identifier in the conflation as
   determined by the [Biolink Model Toolkit](https://github.com/biolink/biolink-model-toolkit).
3. Add all the types and ancestors for all the other identifiers in the conflation without
   duplication.
