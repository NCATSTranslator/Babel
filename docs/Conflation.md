# Babel Conflation

Babel is designed to produce cliques of _identical_ identifiers, but our users would sometimes like
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
3. ChemicalParent conflates chemicals that are the same structure in different charge
   (protonation) states, such as valproic acid and valproate. See
   [ChemicalParent](#chemicalparent) below.

## ChemicalParent

An InChIKey has three blocks: a hash of the connectivity layer, a hash of the remaining layers
(stereochemistry, isotopes) with a standard flag and version character, and a single protonation
character (`N` for neutral). ChemicalParent groups every chemical clique whose `INCHIKEY:` agrees
with another clique's in the first two blocks and differs only in the protonation character. The
neutral (`-N`) clique leads each group; the rest, or all of them when no member is neutral, are
ordered as in DrugChemical. Code: `src/createcompendia/chemicalparent.py`.

The second block stays in the grouping key on purpose, so stereoisomers (dexamethasone and
betamethasone) and isotope-labelled forms are never grouped. A clique whose InChIKeys have more than
one parent key is left out rather than guessed at. This is rule 1 of
[#1173](https://github.com/NCATSTranslator/Babel/issues/1173); that issue's stereo-unspecified and
salt rules would extend this conflation later.

ChemicalParent and DrugChemical can overlap. NodeNorm applies each conflation with one lookup on the
queried clique and does not follow one conflation into another, so with both turned on, two charge
states may still get different DrugChemical members. How often this happens in a build is measured
in [`docs/conflation/chemical-parent/`](conflation/chemical-parent/). NameRes has no
ChemicalParent-conflated synonym file yet.

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
