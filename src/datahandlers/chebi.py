from src.babel_utils import pull_via_ftp


def pull_chebi():
    pull_via_ftp("ftp.ebi.ac.uk", "/pub/databases/chebi/SDF", "chebi.sdf.gz", decompress_data=True, outfilename="CHEBI/ChEBI_complete.sdf")
    pull_via_ftp("ftp.ebi.ac.uk", "/pub/databases/chebi/flat_files", "database_accession.tsv.gz", decompress_data=True, outfilename="CHEBI/database_accession.tsv")


def x(inputfile, labelfile, synfile):
    pass
