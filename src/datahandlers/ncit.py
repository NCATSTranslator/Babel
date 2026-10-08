from src.babel_utils import pull_via_urllib
from src.ubergraph import UberGraph
from src.util import get_logger

logger = get_logger(__name__)


def write_ncit_descendant_codes(roots, outfile):
    """Write every NCIt CURIE that is-a descendant of any root in ``roots``, one per line.

    Used to enumerate the NCIt "Food"/"Seed" subtrees (and the never-food subtrees) so the DrugBank
    food-and-extract retype can recognise foods by their UNII's NCIt class (issue #828). Queries
    UberGraph, so the rule that calls it should carry ``retries``.
    """
    ug = UberGraph()
    codes = set()
    for root in roots:
        for row in ug.get_subclasses_of(root):
            codes.add(row["descendent"])
    logger.info(f"Found {len(codes)} NCIt descendants of {roots}")
    with open(outfile, "w") as outf:
        for code in sorted(codes):
            outf.write(f"{code}\n")


def read_ncit_code_set(codes_file):
    """Return the set of NCIt CURIEs in a one-CURIE-per-line file (see write_ncit_descendant_codes)."""
    with open(codes_file) as inf:
        return {line.strip() for line in inf if line.strip()}


def pull_ncit():
    # Currently, just pull a mapping we need.
    pull_via_urllib(
        "https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/Mappings/",
        "NCIt-SwissProt_Mapping.txt",
        subpath="NCIT",
        decompress=False,
    )
