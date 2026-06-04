import gzip

from src.babel_utils import pull_via_urllib
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

# Expected header of reference.tsv.gz — shared by pull_unichem() (validated at
# download time) and filter_unichem() (validated again at filter time).
REFERENCE_HEADER = "UCI\tSRC_ID\tSRC_COMPOUND_ID\tASSIGNMENT\n"


def pull_unichem():
    """Download UniChem files."""
    pull_via_urllib(
        "http://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/",
        "structure.tsv.gz",
        decompress=False,
        subpath="UNICHEM",
        verify_gzip=True,
    )
    ref_path = pull_via_urllib(
        "http://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/",
        "reference.tsv.gz",
        decompress=False,
        subpath="UNICHEM",
        verify_gzip=True,
    )

    # Validate the header immediately after downloading so that get_unichem fails
    # (and Snakemake deletes its outputs) rather than letting filter_unichem fail
    # later on a file whose format has silently changed upstream.
    with gzip.open(ref_path, "rt") as f:
        header = f.readline()
    if header != REFERENCE_HEADER:
        raise RuntimeError(
            f"UniChem reference.tsv.gz has an unexpected header — the upstream format may have changed.\n"
            f"  Expected : {REFERENCE_HEADER!r}\n"
            f"  Got      : {header!r}"
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

        if header_line != REFERENCE_HEADER:
            raise ValueError(
                f"UniChem reference file {ref_file} has an unexpected header — "
                f"re-run get_unichem to re-download.\n"
                f"  Expected : {REFERENCE_HEADER!r}\n"
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
