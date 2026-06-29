from pathlib import Path

from src.babel_utils import pull_via_urllib
from src.prefixes import OMIM


def pull_omim():
    return pull_via_urllib("https://www.omim.org/static/omim/data/", "mim2gene.txt", subpath="OMIM", decompress=False)


def pull_omim_labels(infile, labelsfile, synonymsfile=None):
    with open(infile) as inf, open(labelsfile, "w") as labelsf:
        for line in inf:
            if line.startswith("#"):
                continue
            chunks = line.rstrip("\n").split("\t")
            if len(chunks) >= 4 and chunks[1] == "gene" and chunks[3]:
                labelsf.write(f"{OMIM}:{chunks[0]}\t{chunks[3]}\n")

    # We don't have any synonyms, so we just create a blank one.
    if synonymsfile:
        Path(synonymsfile).touch()
