import csv

from pronto.utils.io import decompress

from src.babel_utils import make_local_name, pull_via_ftp, pull_via_urllib
from src.metadata.provenance import write_metadata
from src.prefixes import HGNCFAMILY

def pull_hgncfamily():
    # As per https://www.genenames.org/download/gene-groups/#!/#tocAnchor-1-2
    pull_via_urllib('https://storage.googleapis.com/public-download-files/hgnc/csv/csv/genefamily_db_tables/',
                    'family.csv',
                    decompress=False,
                    subpath=HGNCFAMILY)

def pull_labels(infile, labelsfile, descriptionsfile, metadata_yaml):
    with open(infile, 'r') as inf, open(labelsfile, 'w') as labelsf, open(descriptionsfile, 'w') as descriptionsf:
        reader = csv.DictReader(inf)
        for row in reader:
            id = f"{HGNCFAMILY}:{row['id']}"
            name = row['name']
            description = row['desc_comment']
            # There is also a 'desc_label' field, but this seems to be pretty similar to 'name'.
            labelsf.write(f'{id}\t{name}\n')

            if description and description != "NULL":
                descriptionsf.write(f'{id}\t{description}\n')

    write_metadata(
        metadata_yaml,
        typ='transform',
        name='HGNC Gene Family labels',
        description='Labels extracted from HGNC GeneFamily CSV download',
        sources=[{
            'type': 'download',
            'name': 'HGNC Gene Family',
            'url': 'https://storage.googleapis.com/public-download-files/hgnc/csv/csv/genefamily_db_tables/family.csv',
            'description': 'HGNC GeneFamily CSV download'
        }]
    )
