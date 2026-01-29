# Babel

[![arXiv](https://img.shields.io/badge/arXiv-2601.10008-b31b1b.svg)](https://arxiv.org/abs/2601.10008)

<!--
Because this document is written like an FAQ, I want to allow headers to
end with punctuation, so I'm going to disable MD026.
--><!-- rumdl-disable MD026 -->

## Introduction

The [Biomedical Data Translator](https://ncats.nih.gov/translator) integrates
data across many data sources. One source of difficulty is that different data
sources use different vocabularies. One source may represent water as
[MESH:D014867](https://meshb.nlm.nih.gov/record/ui?ui=D014867), while another
may use the identifier
[DRUGBANK:DB09145](https://go.drugbank.com/drugs/DB09145). When integrating, we
need to recognize that both of these identifiers are identifying the same
concept.

Babel integrates the specific naming systems used in the Translator, creating
equivalent sets across multiple semantic types following the conventions
established by the [Biolink Model](https://github.com/biolink/biolink-model).
Each semantic type (such as
[biolink:SmallMolecule](https://biolink.github.io/biolink-model/SmallMolecule/))
requires specialized processing, but in each case, a JSON-formatted compendium
is written to disk. This compendium can be used directly, but it can also be
served by the
[Node Normalization service](https://github.com/TranslatorSRI/NodeNormalization)
or another frontend.

In certain contexts, differentiating between some related concepts doesn't make
sense: for example, you might not want to differentiate between a gene and the
protein that is the product of that gene. Babel provides different
[conflations](docs/Conflation.md) that group cliques on the basis of various
criteria: for example, the GeneProtein conflation combines a gene with the
protein that that gene encodes.

While generating these cliques, Babel also collects all the synonyms for every
clique, which can then be used by tools like
[Name Resolver (NameRes)](https://github.com/NCATSTranslator/NameResolution) to
provide name-based lookup of concepts.

## What do Babel outputs look like?

Three [Babel data formats](./docs/DataFormats.md) are available:

- Compendium files contain concepts (sets or "cliques" of equivalent
  identifiers), which include a preferred identifier, Biolink type, list of
  equivalent identifiers as well as other information about the concept (such as
  the descriptions, information content valuen and so on).
- Synonym files, which don't include the equivalent identifiers for each
  concept, but do include every known synonym for each concept. These files can
  be directly loaded into an Apache Solr database for querying. The
  [Name Resolver](https://github.com/NCATSTranslator/NameResolution) contains
  scripts for loading these files and provides a frontend that can be used to
  search for concepts by label or synonym, or to provide an autocomplete service
  for Babel concepts.
- Conflation files contain the lists of concepts that should be conflated when
  that conflation is turned on.

## How can I download Babel outputs?

You can find out about [downloading Babel outputs](docs/Downloads.md). You can
find a list of Babel releases in the [Releases list](./releases/README.md).

## How can I run Babel?

Babel is difficult to run, primarily because of its inefficient memory handling
-- we currently need around 500G of memory to build the largest compendia
(Protein and DrugChemical conflated information), although the smaller compendia
should be buildable with far less memory. We are working on reducing these
restrictions as far as possible. You can read more about
[Babel's build process](docs/RunningBabel.md), and please do contact us if you
run into any problems or would like some assistance.

We have [detailed instructions for running Babel](docs/RunningBabel.md), but the
short version is:

- We use [uv](https://docs.astral.sh/uv/) to manage Python dependencies. You can
  use the
  [Docker image](https://github.com/NCATSTranslator/Babel/pkgs/container/babel)
  if you run into any difficulty setting up the prerequisites.
- We use [Snakemake](https://snakemake.github.io/) to handle the dependency
  management.

Therefore, you should be able to run Babel by cloning this repository and
running:

```shell
$ uv run snakemake --cores [NUMBER OF CORES TO USE]
```

The [./slurm/run-babel-on-slurm.sh](./slurm/run-babel-on-slurm.sh) Bash script
can be used to start running Babel as a Slurm job. You can set the BABEL_VERSION
environment variable to document which version of Babel you are running.

## How can I deploy Babel outputs?

Information on [deploying Babel outputs](./docs/Deployment.md) is available.

## How can I access Babel cliques?

There are several ways of accessing Babel cliques:

- You can run the Babel pipeline to generate the cliques yourself. Note that
  Babel currently has very high memory requirements -- it requires around 500G
  of memory in order to generate the Protein clique. Information on
  [running Babel](docs/RunningBabel.md) is available.
- The NCATS Translator project provides the
  [Node Normalization](https://nodenorm.transltr.io/docs) frontend to
  "normalize" identifiers -- any member of a particular clique will be
  normalized to the same preferred identifier, and the API will return all the
  secondary identifiers, Biolink type, description and other useful information.
  You can find out more about this frontend on
  [its GitHub repository](https://github.com/TranslatorSRI/NodeNormalization).
- The NCATS Translator project also provides the
  [Name Lookup (Name Resolution)](https://name-lookup.transltr.io/) frontends
  for searching for concepts by labels or synonyms. You can find out more about
  this frontend at
  [its GitHub repository](https://github.com/TranslatorSRI/NameResolution).
- Members of the Translator consortium can also request access to the
  [Babel outputs](./docs/BabelOutputs.md) (in a
  [custom format](./docs/DataFormats.md)), which are currently available in
  JSONL, [Apache Parquet](https://parquet.apache.org/) or
  [KGX](https://github.com/biolink/kgx) formats.

## What is the Node Normalization service (NodeNorm)?

The Node Normalization service, Node Normalizer or
[NodeNorm](https://github.com/TranslatorSRI/NodeNormalization) is an NCATS
Translator web service to normalize identifiers by returning a single preferred
identifier for any identifier provided.

In addition to returning the preferred identifier and all the secondary
identifiers for a clique, NodeNorm will also return its Biolink type and
["information content" score](#what-are-information-content-values), and
optionally any descriptions we have for these identifiers.

It also includes some endpoints for normalizing an entire TRAPI message and
other APIs intended primarily for Translator users.

You can find out more about NodeNorm at its
[Swagger interface](https://nodenormalization-sri.renci.org/docs) or
[in this Jupyter Notebook](https://github.com/TranslatorSRI/NodeNormalization/blob/master/documentation/NodeNormalization.ipynb).

## What is the Name Resolution service (NameRes)?

The Name Resolution service, Name Lookup or
[NameRes](https://github.com/TranslatorSRI/NameResolution) is an NCATS
Translator web service for looking up preferred identifiers by search text.
Although it is primarily designed to be used to power NCATS Translator's
autocomplete text fields, it has also been used for named-entity linkage.

You can find out more about NameRes at its
[Swagger interface](https://name-resolution-sri.renci.org/docs) or
[in this Jupyter Notebook](https://github.com/TranslatorSRI/NameResolution/blob/master/documentation/NameResolution.ipynb).

## What are "information content" values?

Babel obtains information content values for over 3.8 million concepts from
[Ubergraph](https://github.com/INCATools/ubergraph?tab=readme-ov-file#graph-organization)
based on the number of terms related to the specified term as either a subclass
or any existential relation. They are decimal values that range from 0.0
(high-level broad term with many subclasses) to 100.0 (very specific term with
no subclasses).

## I've found a "split" clique: two identifiers that should be considered identical are in separate cliques

Please report this as an issue to the
[Babel GitHub repository](https://github.com/TranslatorSRI/Babel/issues). At a
minimum, please include the identifiers (CURIEs) for the identifiers that should
be combined. Links to a NodeNorm instance showing the two cliques are very
helpful. Evidence supporting the lumping, such as a link to an external database
that makes it clear that these identifiers refer to the same concept, are also
very helpful: while we have some ability to combine cliques manually if needed
urgently for some application, we prefer to find a source of mappings that would
combine the two identifiers, allowing us to improve cliquing across Babel.

## I've found a "lumped" clique: two identifiers that are combined in a single clique refer to different concepts

Please report this as an issue to the
[Babel GitHub repository](https://github.com/TranslatorSRI/Babel/issues). At a
minimum, please include the identifiers (CURIEs) for the identifiers that should
be split. Links to a NodeNorm instance showing the lumped clique is very
helpful. Evidence, such as a link to an external database that makes it clear
that these identifiers refer to the same concept, are also very helpful: while
we have some ability to combine cliques manually if needed urgently for some
application, we prefer to find a source of mappings that would combine the two
identifiers, allowing us to improve cliquing across Babel.

## How does Babel choose a preferred identifier for a clique?

After determining the equivalent identifiers that belong in a single clique,
Babel sorts them in the order of CURIE prefixes for that Biolink type as
determined by the Biolink Model. For example, for a
[biolink:SmallMolecule](https://biolink.github.io/biolink-model/SmallMolecule/#valid-id-prefixes),
any CHEBI identifiers will appear first, followed by any UNII identifiers, and
so on. The first identifier in this list is the preferred identifier for the
clique.

[Conflations](./docs/Conflation.md) are lists of identifiers that are merged in
that order when that conflation is applied. The preferred identifier for the
clique is therefore the preferred identifier of the first clique being
conflated.

- For GeneProtein conflation, the preferred identifier is a gene.
- For DrugChemical conflation, Babel uses the
  [following algorithm](https://github.com/NCATSTranslator/Babel/blob/f3ff2103e74bc9b6bee9483355206b32e8f9ae9b/src/createcompendia/drugchemical.py#L466-L538):
  1. We first choose an overall Biolink type for the conflated clique. To do
     this, we use a
     ["preferred Biolink type" order](https://github.com/NCATSTranslator/Babel/blob/f3ff2103e74bc9b6bee9483355206b32e8f9ae9b/config.yaml#L32-L50)
     that can be configured in [config.yaml](./config.yaml) and choose the most
     preferred Biolink type that is present in the conflated clique.
  1. We then group the cliques to be conflated by the prefix of their preferred
     identifier, and sort them based on the preferred prefix order for the
     chosen Biolink type.
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

For most Biolink types, the preferred label for a clique is the label of the
preferred identifier. There is a
[`demote_labels_longer_than`](https://github.com/NCATSTranslator/Babel/blob/master/config.yaml#L437)
configuration parameter that -- if set -- will cause labels that are longer than
the specified number of characters to be ignored unless no labels shorter than
that length are present. This is to avoid overly long labels when a more concise
label is available.

Biolink types that are chemicals (i.e.
[biolink:ChemicalEntity](https://biolink.github.io/biolink-model/ChemicalEntity/)
and its subclasses) have a special list of
[preferred name boost prefixes](https://github.com/NCATSTranslator/Babel/blob/f3ff2103e74bc9b6bee9483355206b32e8f9ae9b/config.yaml#L416-L426)
that are used to prioritize labels. This list is currently:

1. DRUGBANK
1. DrugCentral
1. CHEBI
1. MESH
1. CHEMBL.COMPOUND
1. GTOPDB
1. HMDB
1. RXCUI
1. PUBCHEM.COMPOUND

[Conflations](./docs/Conflation.md) are lists of identifiers that are merged in
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

## How can I contribute to Babel?

If you want to contribute to Babel, start with the
[Contributing to Babel](./CONTRIBUTING.md) documentation. This will provide
guidance on how the source code is organized, what contributions are most
useful, and how to run the tests.

## Who should I contact for more information about Babel?

You can find out more about Babel by
[opening an issue on this repository](https://github.com/TranslatorSRI/Babel/issues),
contacting one of the
[Translator SRI PIs](https://ncats.nih.gov/research/research-activities/translator/projects)
or contacting the
[NCATS Translator team](https://ncats.nih.gov/research/research-activities/translator/about).
