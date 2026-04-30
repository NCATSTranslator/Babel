# Understanding Babel outputs

<!--
Because this document is written like an FAQ, I want to allow headers to
end with punctuation, so I'm going to disable MD026.
--><!-- rumdl-disable MD026 -->

This document explains *how and why* Babel constructs its outputs: how cliques are formed,
how preferred identifiers and labels are chosen, where descriptions and IC values come from,
and how to report errors. For a description of *what the output files look like*, see
[DataFormats.md](./DataFormats.md).

## How does Babel choose a preferred identifier for a clique?

After determining the equivalent identifiers that belong in a single clique,
Babel sorts them in the order of CURIE prefixes for that Biolink type as
determined by the Biolink Model. For example, for a
[biolink:SmallMolecule](https://biolink.github.io/biolink-model/SmallMolecule/#valid-id-prefixes),
any CHEBI identifiers will appear first, followed by any UNII identifiers, and
so on. The first identifier in this list is the preferred identifier for the
clique.

[Conflations](./Conflation.md) are lists of identifiers that are merged in
that order when that conflation is applied. The preferred identifier for the
clique is therefore the preferred identifier of the first clique being
conflated.

- For GeneProtein conflation, the preferred identifier is a gene.
- For DrugChemical conflation, Babel uses the
  [following algorithm](https://github.com/NCATSTranslator/Babel/blob/f3ff2103e74bc9b6bee9483355206b32e8f9ae9b/src/createcompendia/drugchemical.py#L466-L538):
    1. We group the cliques to be conflated by the prefix of their preferred identifier (e.g. CHEBI,
       UNII, PUBCHEM.COMPOUND), and sort these groups using the
       [ChemicalEntity prefix sort order from the Biolink Model](https://biolink.github.io/biolink-model/ChemicalEntity/#valid-id-prefixes).
    1. If there are multiple cliques with the same prefix in their preferred
       identifier, we use the following criteria to sort them:
        1. A clique with a lower information content value will be sorted before
           those with a higher information content or no information content at
           all.
        1. A clique with more identifiers are sorted before those with fewer
           identifiers.
        1. A clique whose preferred identifier has a smaller numerical suffix will
           be sorted before those with a larger numerical suffix.

## How does Babel choose a preferred label for a clique?

For most Biolink types, the preferred label for a clique is the label of the preferred identifier.
There is a
[`demote_labels_longer_than`](https://github.com/NCATSTranslator/Babel/blob/738f5e917e910847fac76ab13e847b15cf68b759/config.yaml#L420)
configuration parameter that -- if set -- will cause labels that are longer than the specified
number of characters to be ignored unless no labels shorter than that length are present. This is to
avoid overly long labels when a more concise label is available.

Biolink types that are chemicals (i.e.
[biolink:ChemicalEntity](https://biolink.github.io/biolink-model/ChemicalEntity/) and its
subclasses) have a special list of
[preferred name boost prefixes](https://github.com/NCATSTranslator/Babel/blob/f3ff2103e74bc9b6bee9483355206b32e8f9ae9b/config.yaml#L416-L426)
that are used to prioritize labels. This list is currently:

1. DRUGBANK
1. DrugCentral
1. CHEBI
1. MESH
1. GTOPDB

[Conflations](./Conflation.md) are lists of identifiers that are merged in
that order when that conflation is applied. The preferred label for the
conflated clique is therefore the preferred label of the first clique being
conflated.

## Where do the clique descriptions come from?

Currently, all descriptions for NodeNorm concepts come from
[UberGraph](https://github.com/INCATools/ubergraph/). You will note that
descriptions are collected for every identifier within a clique, and then the
description associated with the most preferred identifier is provided for the
preferred identifier. Descriptions are not included in NameRes, but the
`description` flag can be used to include any descriptions when returning
cliques from NodeNorm.

## What are "information content" values?

Babel obtains information content values for over 3.8 million concepts from
[Ubergraph](https://github.com/INCATools/ubergraph?tab=readme-ov-file#graph-organization)
based on the number of terms related to the specified term as either a subclass
or any existential relation. They are decimal values that range from 0.0
(high-level broad term with many subclasses) to 100.0 (very specific term with
no subclasses).

## Reporting incorrect Babel cliques

### I've found two or more identifiers in separate cliques that should be considered identical

Please report this "split" clique as an issue to the
[Babel GitHub repository](https://github.com/NCATSTranslator/Babel/issues). At a
minimum, please include the identifiers (CURIEs) for the identifiers that should
be combined. Links to a NodeNorm instance showing the two cliques are very
helpful. Evidence supporting the lumping, such as a link to an external database
that makes it clear that these identifiers refer to the same concept, are also
very helpful: while we have some ability to combine cliques manually if needed
urgently for some application, we prefer to find a source of mappings that would
combine the two identifiers, allowing us to improve cliquing across Babel.

<!-- rumdl-disable MD013 -->
### I've found two or more identifiers combined in a single clique that actually identify different concepts
<!-- rumdl-enable MD013 -->

Please report this "lumped" clique as an issue to the
[Babel GitHub repository](https://github.com/NCATSTranslator/Babel/issues). At a
minimum, please include the identifiers (CURIEs) for the identifiers that should
be split. Links to a NodeNorm instance showing the lumped clique is very
helpful. Evidence, such as a link to an external database that makes it clear
that these identifiers refer to the same concept, are also very helpful: while
we have some ability to combine cliques manually if needed urgently for some
application, we prefer to find a source of mappings that would combine the two
identifiers, allowing us to improve cliquing across Babel.
