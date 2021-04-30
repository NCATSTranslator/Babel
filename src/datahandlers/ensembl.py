from src.babel_utils import make_local_name
from apybiomart import find_datasets,query,find_attributes
import os

#Note that Ensembl doesn't seem to assign its own labels or synonyms to its gene identifiers.  It appears that
# they are all imported from other sources.   Therefore, we will not generate labels or synonym files.  We
# do pull down data so that we can get the full list of ensembl identifiers though.

#In principle, we want to pull some file from somewhere, but ensembl, in all of its glory, lacks a list of
# genes that can be gathered without downloading hundreds of gigs of other stuff.  So, we'll use biomart to pull
# just what we need.
def pull_ensembl(complete_file):
    f = find_datasets()
    cols = set(["ensembl_gene_id", "ensembl_peptide_id", "description", "external_gene_name", "external_gene_source",
                "external_synonym","chromosome_name","source","gene_biotype","entrezgene_id",
                "zfin_id_id",'mgi_id','rgd_id','flybase_gene_id','sgd_gene','wormbase_gene'])
    for ds in f['Dataset_ID']:
        print(ds)
        outfile = make_local_name('BioMart.tsv',subpath=f'ENSEMBL/{ds}')
        #Really, we should let snakemake handle this, but then we would need to put a list of all the 200+ sets in our
        # config, and keep it up to date.  Maybe you could have a job that gets the datasets and writes a dataset file,
        # but then updates the config? That sounds bogus.
        if os.path.exists(outfile):
            continue
        atts = find_attributes(ds)
        existingatts = set(atts['Attribute_ID'].to_list())
        attsIcanGet = cols.intersection(existingatts)
        df = query(attributes=attsIcanGet, filters={}, dataset=ds)
        df.to_csv(outfile,index=False,sep='\t')
    with open(complete_file,'w') as outf:
        outf.write(f'Downloaded gene sets for {len(f)} data sets.')

if __name__ == '__main__':
    pull_ensembl()
