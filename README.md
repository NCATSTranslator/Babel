# Babel

## Introduction

The [Biomedical Data Translator](https://ncats.nih.gov/translator) integrates data across many data sources.  One
source of difficulty is that different data sources use different vocabularies.
One source may represent water as MESH:D014867, while another may use the
identifier DRUGBANK:DB09145.   When integrating, we need to recognize that 
both of these identifiers are identifying the same concept.

Babel integrates the specific naming systems used in the Translator, 
creating equivalent sets across multiple semantic types, and following the
conventions established by the [biolink model](https://github.com/biolink/biolink-model).  It checks these conventions
at runtime by querying the [Biolink Model service](https://github.com/TranslatorIIPrototypes/bl_lookup).  Each semantic type (such as 
chemical substance) requires specialized processing, but in each case, a 
JSON-formatted compendium is written to disk.  This compendium can be used 
directly, but it can also be served via the [Node Normalization service](https://github.com/TranslatorIIPrototypes/NodeNormalization).

We anticipate that the simple approach taken here will soon be overtaken by
more advanced probabilistic procedures, so caution should be taken in building
strong dependencies against the Babel code.

## Configuration

Babel requires Python 3.11 or later.

Before running, edit `config.json` and set the `babel_downloads` and `babel_output` directories.  Do not edit the
remaining items, which are used to control the build process.

Also, if building the disease/phenotype compendia, there are two files that 
must be obtained with the user's UMLS license.  In particular `MRCONSO.RRF` 
and `MRSTY.RRF` should be placed in `/babel/input_data/private`.

## Building Compendia

Compendia building is managed by snakemake.  To build, for example, the anatomy related compendia, run

```snakemake --cores 1 anatomy```

Currently, the following targets build compendia:
* anatomy
* chemical
* disease
* gene
* protein
* genefamily
* taxon
* process
* geneprotein

Each target builds one or more compendia corresponding to a biolink model category.  For instance, the anatomy target 
builds compendia for `biolink:AnatomicalEntity`, `biolink:Cell`, `biolink:CellularComponent`, and `biolink:GrossAnatomicalStructure`.

## Build Process

The information contained here is not required to create the compendia, but may be useful to understand.  The build process is 
divided into two parts:

1. Pulling data from external sources and parsing it independent of use
2. Extracting and combining entities for specific types from these downloaded data sets.

This distinction is made because a single data set, such as MESH may contain entities of many different types and may be 
used by many downstream targets.

### Pulling Data

The datacollection snakemake file coordinates pulling data from external sources into a local filesystem.  Each data source 
has a module in `src.datahandlers`.  Data goes into the babel_downloads directory, in subdirectories named by the curie prefix
for that data set.  If the directory is misnamed and does not match the prefix, then labels will not be added to the identifiers
in the final compendium.

Once data is assembled, we attempt to create 2 extra files for each data source: `labels` and `synonyms`.   `labels` is a two
column tab-delimited file. The first column is a curie identifier from the data source, and the second column is the label
from that data set.  Each entity should only appear once in the `labels` file.
The `labels` file for a data set does not subset the data for a specific purpose, but contains all 
labels for any entity in that data set.  

`synonyms` contains other lexical names for the entity and is a 3-column tab-delimited file, with the second column
indicating the type of synonym (exact, related, xref, etc..)

### Creating compendia

The individual details of creating a compendium vary, but all follow the same essential pattern.  

First, we extract the identifiers that will be used in the compendia from each data source that will contribute, and
places them into a directory.  For instance, in the build of the chemical compendium, these ids are placed into 
`/babel_downloads/chemical/ids`. Each file is a two column file containing curie identifiers in column 1, and the biolink
category for that entity in column 2.  

Second, we create pairwise concords across vocabularies.  These are places in e.g. `babel_downloads/chemical/concords`. 
Each concord is a 3 column file of the format

`<curie1> <relation> <curie2>`

While the relation is currently unused, future versions of babel may use the relation in building cliques.

Third, the compendia is built by bringing together the ids and concords, pulling in the categories from the id files, 
and the labels from the label files.

Fourth, the compendia is assessed to make sure that all of the ids in the id files made into one of the possibly multiple 
compendia.  The compendia are further assessed to locate large cliques and display the level of vocabulary merging.

## Building with Docker

You can build this repository by running the following Docker command:

```
$ docker build .
```

It is also set up with a GitHub Action that will automatically generate and publish
Docker images to https://github.com/TranslatorSRI/Babel/pkgs/container/babel.

**Known issue**: if you want to use `git fetch` from this Docker image, you need
to manually remote the Basic authentication command from `.git/config` before it
will work. We're tracking this at https://github.com/TranslatorSRI/Babel/issues/119.

## Running with Docker

You can also run Babel with [Docker](https://www.docker.com/). There are
two directories you need to bind or mount from outside the container:

```
$ docker run -it --rm --mount type=bind,source=...,target=/home/runner/babel/input_data/private --mount type=bind,source=...,target=/home/runner/babel/babel_downloads --entrypoint /bin/bash ggvaidya/babel
```

These two directories should be set up as following:
* `babel/input_data/private` is used to store some input files
  that you will need to download yourself:
    * `MRCONSO.RRF` and `MRSTY.RRF`: parts of the UMLS release, need to be downloaded from [the UMLS download website](https://www.nlm.nih.gov/research/umls/licensedcontent/umlsknowledgesources.html).
* `babel/babel_downloads` is used to store data files downloaded during Babel assembly.

The script `scripts/build-babel.sh` can be used to run `snakemake` with a few useful settings (although just running
`snakemake --cores 5` should work just fine.)

## Deploying with Kubernetes

The `kubernetes/` directory has example Kubernetes scripts for deploying Babel to a Kubernetes cluster. You need to
create three resources:
* `kubernetes/babel-downloads.k8s.yaml` creates a Persistent Volume Claim (PVC) for downloading input resources from
  the internet.
* `kubernetes/babel-outputs.k8s.yaml` creates a PVC for storing the output files generated by Babel. This includes
  compendia, synonym files, reports and intermediate files.
* `kubernetes/babel-private.k8s.yaml` creates a PVC for storing the private files (see `babel/input_data/private`
  described above). Once this PVC has been set up, you will need to copy those private files into it yourself.
* `kubernetes/babel.k8s.yaml` creates a pod running the latest Docker image from ggvaidya/babel. Rather than running
  the data generation automatically, you are expected to SSH into this pod and start the build process by:
  1. Creating a [screen](https://www.gnu.org/software/screen/) to run the program in. You can start a Screen by
     running:

     ```shell
     $ screen
     ```
  2. Starting the Babel build process by running:
    
     ```shell
     $ snakemake -c5 --verbose
     ```
  
     Ideally, this should produce the entire Babel output in a single run. You can also add `--rerun-incomplete` if you
     need to restart a partially completed job.

     To help with debugging, the Babel image includes .git information. You can switch branches, or fetch new branches
     from GitHub by running `git fetch origin-https`.
 
  3. Press `Ctrl+A D` to "detach" the screen. You can reconnect to a detached screen by running `screen -r`.
     You can also see a list of all running screens by running `screen -l`.
  4. Once the generation completes, all output files should be in the `babel_outputs` directory.
