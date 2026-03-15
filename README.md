# Babel

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18489042.svg)](https://doi.org/10.5281/zenodo.18489042)
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

## Using Babel outputs

### What do Babel outputs look like?

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

### How can I download Babel outputs?

You can find out about [downloading Babel outputs](docs/Downloads.md). You can
find a list of Babel releases in the [Releases list](./releases/README.md).

### How can I deploy Babel outputs?

Information on [deploying Babel outputs](./docs/Deployment.md) is available.

### How can I access Babel cliques?

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
- Play around with the [Babel Downloads](./docs/Downloads.md) (in a
  [custom format](./docs/DataFormats.md)), which are currently available in
  JSONL, [Apache Parquet](https://parquet.apache.org/) or
  [KGX](https://github.com/biolink/kgx) formats.

### What is the Node Normalization service (NodeNorm)?

The Node Normalization service, Node Normalizer or
[NodeNorm](https://github.com/TranslatorSRI/NodeNormalization) is an NCATS
Translator web service to normalize identifiers by returning a single preferred
identifier for any identifier provided.

In addition to returning the preferred identifier and all the secondary
identifiers for a clique, NodeNorm will also return its Biolink type and
["information content" score](./docs/Understanding.md#what-are-information-content-values), and
optionally any descriptions we have for these identifiers.

It also includes some endpoints for normalizing an entire TRAPI message and
other APIs intended primarily for Translator users.

You can find out more about NodeNorm at its
[Swagger interface](https://nodenormalization-sri.renci.org/docs) or
[in this Jupyter Notebook](https://github.com/TranslatorSRI/NodeNormalization/blob/master/documentation/NodeNormalization.ipynb).

### What is the Name Resolver (NameRes)?

The Name Resolver, Name Lookup or
[NameRes](https://github.com/TranslatorSRI/NameResolution) is an NCATS
Translator web service for looking up preferred identifiers by search text.
Although it is primarily designed to be used to power NCATS Translator's
autocomplete text fields, it has also been used for named-entity linkage.

You can find out more about NameRes at its
[Swagger interface](https://name-resolution-sri.renci.org/docs) or
[in this Jupyter Notebook](https://github.com/TranslatorSRI/NameResolution/blob/master/documentation/NameResolution.ipynb).

## Understanding Babel outputs

For a detailed explanation of how Babel constructs cliques, chooses preferred identifiers and
labels, sources descriptions, and calculates information content values — as well as guidance on
reporting incorrect cliques — see [docs/Understanding.md](./docs/Understanding.md).

## Running Babel

### How can I run Babel?

Babel requires significant memory — around 500 GB to build the largest compendia (Protein and
DrugChemical conflated), though smaller compendia need far less. It uses
[uv](https://docs.astral.sh/uv/) for Python dependency management and
[Snakemake](https://snakemake.github.io/) for build orchestration. See
[docs/RunningBabel.md](docs/RunningBabel.md) for detailed instructions, configuration, and
Slurm job setup.

## Contributing to Babel

If you want to contribute to Babel, start with the
[Contributing to Babel](./CONTRIBUTING.md) documentation. This will provide
guidance on how the source code is organized, what contributions are most
useful, and how to run the tests. For a deeper look at the development
workflow and ideas for improving it, see [Developing Babel](./docs/Development.md).

## Contact information

You can find out more about Babel by
[opening an issue on this repository](https://github.com/TranslatorSRI/Babel/issues),
contacting one of the
[Translator DOGSLED PIs](https://ncats.nih.gov/research/research-activities/translator/projects)
or contacting the
[NCATS Translator team](https://ncats.nih.gov/research/research-activities/translator/about).


<!-- Automated minor fix for issue #607 -->
