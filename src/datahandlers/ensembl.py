import traceback

import apybiomart
import pandas

from src.babel_utils import make_local_name, get_config
from apybiomart import find_datasets, query, find_attributes
import os


# Note that Ensembl doesn't seem to assign its own labels or synonyms to its gene identifiers.  It appears that
# they are all imported from other sources.   Therefore, we will not generate labels or synonym files.  We
# do pull down data so that we can get the full list of ensembl identifiers though.

# In principle, we want to pull some file from somewhere, but ensembl, in all of its glory, lacks a list of
# genes that can be gathered without downloading hundreds of gigs of other stuff.  So, we'll use biomart to pull
# just what we need.
def pull_ensembl(complete_file):
    dataset_df = find_datasets()

    # dataset_url = "http://www.ensembl.org/biomart/martservice/biomart/martservice?type=datasets&mart=ENSEMBL_MART_ENSEMBL"
    # dataset_df = pandas.read_csv(dataset_url, sep='\t', header=None, index_col=False)

    skip_dataset_ids = set(get_config()['ensembl_datasets_to_skip'])

    cols = {"ensembl_gene_id", "ensembl_peptide_id", "description", "external_gene_name", "external_gene_source",
            "external_synonym", "chromosome_name", "source", "gene_biotype", "entrezgene_id", "zfin_id_id", 'mgi_id',
            'rgd_id', 'flybase_gene_id', 'sgd_gene', 'wormbase_gene'}

    # for ds in dataset_df[1]:
    for ds in dataset_df['Dataset_ID']:
        print(ds)
        if ds in skip_dataset_ids:
            print(f'Skipping {ds} as it is included in skip_dataset_ids: {skip_dataset_ids}')
            continue
        outfile = make_local_name('BioMart.tsv', subpath=f'ENSEMBL/{ds}')
        # Really, we should let snakemake handle this, but then we would need to put a list of all the 200+ sets in our
        # config, and keep it up to date.  Maybe you could have a job that gets the datasets and writes a dataset file,
        # but then updates the config? That sounds bogus.
        if os.path.exists(outfile):
            continue
        try:

            attributes_df = find_attributes(ds)
            # attributes_url = f"http://www.ensembl.org/biomart/martservice/biomart/martservice?type=attributes&dataset={ds}"
            # attributes_df = pandas.read_csv(attributes_url, sep='\t', header=None, index_col=False)

            # existingatts = set(attributes_df[0].to_list())
            existingatts = set(attributes_df['Attribute_ID'].to_list())
            attsIcanGet = cols.intersection(existingatts)

            # query_url = f"http://www.ensembl.org/biomart/martservice/biomart/martservice?type=attributes&dataset={ds}"
            # query_df = pandas.read_csv(attributes_url, sep='\t', header=None, index_col=False)

            df = query(attributes=list(attsIcanGet), filters={}, dataset=ds)
            df.to_csv(outfile, index=False, sep='\t')
        except Exception as exc:
            biomart_dir = os.path.dirname(outfile)
            print(f'Deleting BioMart directory {biomart_dir} so its clear it needs to be downloaded again.')
            os.rmdir(biomart_dir)

            raise exc
    with open(complete_file, 'w') as outf:
        outf.write(f'Downloaded gene sets for {len(f)} data sets.')


if __name__ == '__main__':
    # marts = apybiomart.find_marts()
    # print(marts.head())

    pull_ensembl("/tmp/asdfasdf.txt")
