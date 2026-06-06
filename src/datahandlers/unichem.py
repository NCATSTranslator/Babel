import gzip

from src.babel_utils import pull_via_wget
from src.prefixes import CHEBI, CHEMBLCOMPOUND, DRUGBANK, DRUGCENTRAL, GTOPDB, HMDB, KEGGCOMPOUND, PUBCHEMCOMPOUND, UNII

# global for this file
data_sources: dict = {
    "1": CHEMBLCOMPOUND,
    "2": DRUGBANK,
    "4": GTOPDB,
    "6": KEGGCOMPOUND,
    "7": CHEBI,
    "14": UNII,
    "18": HMDB,
    "22": PUBCHEMCOMPOUND,
    "34": DRUGCENTRAL,
}

# Expected header of reference.tsv.gz — validated by filter_unichem() at filter time.
# Note: upstream uses "ASSIGMENT" (missing 'N') — this matches the upstream typo exactly.
UNICHEM_REFERENCE_TSV_HEADER = "UCI\tSRC_ID\tSRC_COMPOUND_ID\tASSIGMENT\n"


def download_unichem_structure():
    """Download UniChem structure file. Format validation happens in filter_unichem."""
    pull_via_wget(
        "http://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/",
        "structure.tsv.gz",
        decompress=False,
        subpath="UNICHEM",
        verify_gzip=True,
    )


def download_unichem_reference():
    """Download UniChem reference file. Format validation happens in filter_unichem."""
    pull_via_wget(
        "http://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/",
        "reference.tsv.gz",
        decompress=False,
        subpath="UNICHEM",
        verify_gzip=True,
    )


def filter_unichem(ref_file, ref_filtered):
    """Filter UniChem reference file to those sources we're interested in."""
    srclist = [str(k) for k in data_sources.keys()]
    try:
        rf_handle = gzip.open(ref_file, "rt")
    except (OSError, gzip.BadGzipFile) as e:
        raise RuntimeError(f"Cannot open UniChem reference file {ref_file}: {e}") from e

    with rf_handle, open(ref_filtered, "w") as out:
        try:
            header_line = rf_handle.readline()
        except EOFError as e:
            raise RuntimeError(f"UniChem reference file {ref_file} is truncated (could not read header): {e}") from e

        if header_line != UNICHEM_REFERENCE_TSV_HEADER:
            raise ValueError(
                f"UniChem reference file {ref_file} has an unexpected header — "
                f"examine the file and update UNICHEM_REFERENCE_TSV_HEADER in src/datahandlers/unichem.py if the format has changed.\n"
                f"  Expected : {UNICHEM_REFERENCE_TSV_HEADER!r}\n"
                f"  Got      : {header_line!r}"
            )
        out.write(header_line)

        for line_num, line in enumerate(rf_handle, start=2):
            x = line.rstrip().split("\t")
            if len(x) < 4:
                raise ValueError(
                    f"UniChem reference file {ref_file} line {line_num}: "
                    f"expected ≥4 tab-separated columns, got {len(x)}: {line!r}"
                )
            if x[1] in srclist and x[3] == "1":
                # Only use rows with assignment == 1 (current), not 0 (obsolete)
                # As per https://chembl.gitbook.io/unichem/definitions/what-is-an-assignment
                out.write(line)
