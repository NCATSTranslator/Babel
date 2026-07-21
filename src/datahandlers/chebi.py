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
    # database_accession.tsv names its source and curation status by number only; source.tsv and
    # status.tsv are the lookup tables that turn those into "KEGG COMPOUND" / "PubChem Compound" and
    # "CHECKED" / "OK" / "SUBMITTED". Resolving by name rather than hardcoding the ids means a
    # renumbering fails loudly instead of silently changing which rows the ingest accepts.
    pull_via_ftp(
        "ftp.ebi.ac.uk",
        "/pub/databases/chebi/flat_files",
        "source.tsv.gz",
        decompress_data=True,
        outfilename="CHEBI/source.tsv",
    )
    pull_via_ftp(
        "ftp.ebi.ac.uk",
        "/pub/databases/chebi/flat_files",
        "status.tsv.gz",
        decompress_data=True,
        outfilename="CHEBI/status.tsv",
    )


def x(inputfile, labelfile, synfile):
    pass
