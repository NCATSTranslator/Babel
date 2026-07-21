from src.babel_utils import pull_via_ftp


def pull_chebi():
    pull_via_ftp(
        "ftp.ebi.ac.uk",
        "/pub/databases/chebi/SDF",
        "chebi.sdf.gz",
        decompress_data=True,
        outfilename="CHEBI/ChEBI_complete.sdf",
    )
    pull_via_ftp(
        "ftp.ebi.ac.uk",
        "/pub/databases/chebi/flat_files",
        "database_accession.tsv.gz",
        decompress_data=True,
        outfilename="CHEBI/database_accession.tsv",
    )
    # database_accession.tsv names its source only by a numeric source_id; source.tsv is the lookup
    # table that turns that into "KEGG COMPOUND" / "PubChem Compound". Resolving by name rather than
    # hardcoding the ids means a renumbering fails loudly instead of silently emptying the ingest.
    pull_via_ftp(
        "ftp.ebi.ac.uk",
        "/pub/databases/chebi/flat_files",
        "source.tsv.gz",
        decompress_data=True,
        outfilename="CHEBI/source.tsv",
    )


def x(inputfile, labelfile, synfile):
    pass
